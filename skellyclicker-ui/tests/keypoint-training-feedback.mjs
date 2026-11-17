import {chromium, expect} from '@playwright/test';

// Run against the UI dev server. Exercise the opened-folder Training component.
const browser = await chromium.launch({channel:'msedge', headless:true});
const origin = process.argv[2]??'http://127.0.0.1:5176';
try {
  const page = await browser.newPage();
  const config=await fetch((process.env.SKELLYCLICKER_TEST_BACKEND_URL??'http://127.0.0.1:8006')+'/api/training/configuration').then(r=>r.json());
  const run = {id:'recording-run', epochs:10, status:'running', validation_frames:[3]};
  let snapshot = {run_id:run.id, graph:config.graph,sequence:1, status:'running', elapsed_seconds:15,
    operations:[{operation_id:'prepare_trainer', status:'running', unit:'steps',completed:2,total:4,
      detail:'Creating the DeepLabCut training dataset'}], metrics:[], previews:[]};
  await page.route('**/api/keypoint-training/runs?*', route=>route.fulfill({json:[run]}));
  await page.route('**/api/keypoint-training/runs/*/artifact?*', route=>route.fulfill({json:snapshot}));
  await page.route('**/__keypoint-feedback', async route=>{
    const response = await route.fetch({url:origin+'/'});
    await route.fulfill({response, body:(await response.text()).replace('/src/main.tsx','/tests/keypoint-feedback-harness.tsx')});
  });
  await page.goto(origin+'/__keypoint-feedback');
  await expect(page.getByRole('heading',{name:'Keypoint training'})).toBeVisible();
  await expect(page.getByRole('status').filter({hasText:'Preparing DeepLabCut'})).toBeVisible();
  await expect(page.getByRole('progressbar',{name:'Preparation step progress'})).toHaveAttribute('value','2');
  const stages=page.getByRole('region',{name:'Training stages'});
  await stages.getByRole('button',{name:'Graph',exact:true}).click();
  await expect(stages.getByRole('navigation',{name:'Workflow stages'}).getByRole('button')).toHaveCount(4);
  await stages.getByRole('button',{name:'List',exact:true}).click();
  await expect(stages.locator('[data-operation-id="prepare_trainer"]')).toHaveAttribute('data-status','running');
  snapshot = {...snapshot, sequence:2, operations:[{operation_id:'train_model',status:'running',unit:'epochs',completed:2,total:10}],
    metrics:['Training loss','Validation keypoint error'].map((label,i)=>({operation_id:'train_model',id:String(i),label,
      step_label:'Epoch',unit:i?'px':'loss',points:[{step:1,value:2},{step:2,value:1}]}))};
  await expect(page.getByRole('progressbar',{name:'Epoch progress'})).toHaveAttribute('value','2');
  await expect(page.locator('.sdk-metric-card')).toHaveCount(2);
  for (const line of await page.locator('.sdk-metric-card .metric-line').all()) {
    await expect(line).toHaveAttribute('d',/^M.+L/);
  }
  run.status = 'complete';
  snapshot = {...snapshot, sequence:3, status:'complete'};
  await page.reload();
  await expect(page.getByRole('status').filter({hasText:'Finished'})).toBeVisible();
  await expect(page.locator('.sdk-metric-card')).toHaveCount(2);
  console.log('PASS preparation, epoch progress, loss/error charts and completed run recovery');
} finally { await browser.close(); }
