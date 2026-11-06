import {chromium,expect} from '@playwright/test';
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:960}});
let prepared=false,finishPreparation=false,finishLabels=false,prepStarts=0,labelStarts=0,previews=0,cancelled=false,previewError=false;const errors=[];let prepBody,labelBody;
page.on('pageerror',e=>errors.push(String(e)));
const summary=()=>({frames:Array.from({length:prepared?1519:751},(_,i)=>({source_frame:prepared?i:i+90,accepted:true,status:'accepted'})),accepted:751,calibration:{source_frame_count:1519,image_width:1280,image_height:720}});
await page.route('http://images-fixture.invalid/**',async route=>{
 const path=new URL(route.request().url()).pathname;let value;
 if(path==='/api/preparation/result')value=summary();
 else if(path.endsWith('/validate-stl'))value={path:'/fixture/benchy.stl',authored_units:'mm',sha256:'target',compatible:true};
 else if(path==='/api/preparation/start'){prepStarts++;prepBody=route.request().postDataJSON();value={job_id:'prep',state:'running',stage:'Extracting stereo images',completed:0,total:1519};}
 else if(path==='/api/preparation/status/prep'){prepared=finishPreparation;value={job_id:'prep',state:cancelled?'cancelled':prepared?'complete':'running',stage:'Extracting stereo images',completed:prepared?1519:250,total:1519};}
 else if(path==='/api/preparation/cancel/prep'){cancelled=true;value={};}
 else if(path==='/api/labels/preview'){previews++;if(previewError){await route.fulfill({status:422,json:{detail:'Fixture input mismatch. Correct target and retry.'}});return;}value={expected_pose_manifest_sha256:'pose',expected_target_manifest_sha256:'target',moment_count:1519,image_count:3038,label_count:157976};}
 else if(path==='/api/labels/runs'){labelStarts++;labelBody=route.request().postDataJSON();value={run_id:'labels'};}
 else if(path==='/api/label-tasks/labels'){value={run_id:'labels',status:finishLabels?'complete':'running',cancel_requested:false,graph:await page.evaluate(()=>window.fixtureGraph),operations:[],metrics:[],previews:[],elapsed_seconds:1,error:null};}
 else throw new Error('Unexpected fixture request '+path);
 await route.fulfill({json:value});
});
await page.route('**/__image-generation-test',async route=>{const original=await route.fetch({url:'http://127.0.0.1:5176/'});await route.fulfill({response:original,body:(await original.text()).replace('/src/main.tsx','/tests/image-generation-harness.tsx')});});
try{
 await page.goto('http://127.0.0.1:5176/__image-generation-test');
 await expect(page.getByRole('combobox',{name:'Frames to generate'})).toHaveValue('all');
 const start=page.getByRole('button',{name:'Generate all images',exact:true});await expect(start).toBeEnabled();
 await expect(page.getByRole('region',{name:'Image generation',exact:true})).toContainText('1,519 frames / 3,038 images');
 expect(await start.evaluate(e=>getComputedStyle(e).backgroundColor)).not.toBe('rgba(0, 0, 0, 0)');
 await expect(page.getByText('Generate prepares missing recording frames', {exact:false})).not.toBeVisible();
 await page.getByRole('button',{name:'Image generation',exact:true}).click();
 await expect(page.getByText('Generate prepares missing recording frames', {exact:false})).toBeVisible();
 await page.keyboard.press('Escape');
 await page.screenshot({path:'../.test-artifacts/image-generation-default.png'});
 await start.click();await expect.poll(()=>prepStarts).toBe(1);expect(prepBody.start_frame).toBe(0);expect(prepBody.frame_count).toBe(null);
 await expect(page.getByLabel('Run activity')).toContainText('250 / 1519');
 await page.getByRole('button',{name:'Close Create image training set',exact:true}).click();
 await page.getByRole('button',{name:'Reopen generation',exact:true}).click();await expect(page.getByLabel('Run activity')).toContainText('250 / 1519');expect(prepStarts).toBe(1);
 await page.reload();await expect(page.getByLabel('Run activity')).toContainText('250 / 1519');expect(prepStarts).toBe(1);
 finishPreparation=true;await expect.poll(()=>labelStarts).toBe(1);expect(labelBody.start_frame).toBe(0);expect(labelBody.end_frame).toBe(1518);expect(labelBody.step).toBe(1);expect(labelBody.max_moments).toBe(null);expect(labelBody.fit_filter).toBe('all');
 finishLabels=true;await expect(page.getByRole('button',{name:'Open generated images',exact:true})).toBeEnabled();
 await page.screenshot({path:'../.test-artifacts/image-generation-complete.png'});
 await page.getByRole('button',{name:'Open generated images',exact:true}).click();expect(await page.evaluate(()=>window.reviewOpened)).toBe(true);
 await page.reload();await page.getByRole('combobox',{name:'Frames to generate'}).selectOption('custom');
 await page.getByRole('spinbutton',{name:'First frame',exact:true}).fill('90');await page.getByRole('spinbutton',{name:'Number of frames',exact:true}).fill('751');await page.getByRole('spinbutton',{name:'Use every Nth frame',exact:true}).fill('10');
 await expect(page.getByRole('button',{name:'Generate 152 images',exact:true})).toBeEnabled();
 await page.getByRole('combobox',{name:'Frames to generate'}).selectOption('all');await expect(page.getByRole('button',{name:'Generate all images',exact:true})).toBeEnabled();
 previewError=true;await page.getByRole('button',{name:'Generate all images',exact:true}).click();await expect(page.getByRole('alert').first()).toContainText('Fixture input mismatch');
 await expect(page.getByRole('button',{name:'Generate all images',exact:true})).toBeEnabled();expect(labelStarts).toBe(1);
 await page.setViewportSize({width:900,height:700});await page.screenshot({path:'../.test-artifacts/image-generation-narrow.png'});
 prepared=false;finishPreparation=false;previewError=false;await page.reload();await page.getByRole('button',{name:'Generate all images',exact:true}).click();await expect.poll(()=>prepStarts).toBe(2);await page.reload();await expect(page.getByLabel('Run activity')).toContainText('250 / 1519');await page.getByRole('button',{name:'Cancel generation',exact:true}).click();await expect(page.getByRole('alert').first()).toContainText('cancelled');expect(labelStarts).toBe(1);
 expect(errors).toEqual([]);console.log('PASS whole recording defaults, real button styling, automatic preparation/validation/labels, progress, close/reopen, reload recovery, custom sampling opt-in, errors and open result; fixture only');
}finally{await browser.close();}
