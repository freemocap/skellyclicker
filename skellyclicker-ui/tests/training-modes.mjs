import assert from 'node:assert/strict';
import {access,readFile} from 'node:fs/promises';
import {join,resolve} from 'node:path';
import {chromium, expect} from '@playwright/test';

// The caller supplies a disposable copy of the three-camera reference recording.
const [ui, backend, recording] = process.argv.slice(2);
await access(join(recording,'.disposable-training-test'));
const fixture = JSON.parse(await readFile(resolve('backend/tests/fixtures/freemocap_test_data/manual-labels.json')));
const browser = await chromium.launch({channel:process.env.CHROMIUM_CHANNEL || 'msedge',headless:true});
try {
  const page = await browser.newPage({viewport:{width:1600,height:1000}});
  await page.addInitScript(({backend,recording})=>{
    window.isTauri=true;
    window.__TAURI_INTERNALS__={invoke:async command=>{
      if(command==='backend_url')return backend;
      if(command==='plugin:dialog|open')return recording;
      throw Error(command);
    }};
  },{backend,recording});
  await page.goto(ui);
  await page.getByRole('button',{name:'Open folder…'}).click();
  await expect(page.locator('.clicker-header')).toContainText('freemocap_test_data');
  await page.getByRole('textbox',{name:'Point names',exact:true}).fill('nose');
  await page.getByRole('button',{name:'Start labeling'}).click();
  await expect(page.locator('.playback-presented-image[data-presented-frame]')).toHaveCount(3,{timeout:30000});
  async function clickNose(frames) {
    const scrubber=page.locator('.playback-timeline-input');
    for(const frame of frames){
      await scrubber.fill(String(frame));
      await expect.poll(()=>page.locator('.playback-presented-image').evaluateAll(images=>images.map(image=>image.dataset.presentedFrame)),{timeout:30000}).toEqual(Array(3).fill(String(frame)));
      for(const observation of fixture.observations.filter(o=>o.source_frame===frame)){
        const overlay=page.getByRole('img',{name:`Click to place nose in ${observation.camera_id}; right-click to clear`});
        const position=await overlay.locator(':scope > g').evaluate((group,{x_px,y_px})=>{
          const screen=new DOMPoint(x_px,y_px).matrixTransform(group.getScreenCTM());
          return {x:screen.x,y:screen.y};
        },observation);
        await page.mouse.click(position.x,position.y);
      }
    }
  }
  await clickNose([10,115,210]);
  await page.getByRole('tab',{name:'Training',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Keypoint training'})).toBeVisible();
  await expect(page.getByLabel('Python executable for DeepLabCut')).toHaveCount(0);
  await page.getByLabel('Epochs',{exact:true}).fill('1');
  const panel=page.locator('.keypoint-training');
  async function train() {
    const started=page.waitForResponse(r=>r.url().endsWith('/api/keypoint-training/runs')&&r.request().method()==='POST');
    await page.getByRole('button',{name:'Start training'}).click();
    const response=await started;
    assert.ok(!('python_path' in response.request().postDataJSON()));
    assert.equal(response.status(),202,await response.text());
    const {run_id:id}=await response.json();
    const row=panel.locator('p').filter({hasText:id.slice(0,8)});
    await expect(row).toContainText(/complete|failed/,{timeout:300000});
    assert.match(await row.textContent(),/complete/);
    console.log('Completed keypoint training',id);
    return id;
  }
  const first=await train();
  await page.getByRole('tab',{name:'Viewer',exact:true}).click();
  await clickNose([45,150]);
  await page.getByRole('tab',{name:'Training',exact:true}).click();
  await page.getByLabel('Starting model').selectOption(first);
  await page.getByLabel('Epochs',{exact:true}).fill('1');
  await expect(panel).toContainText('4 training · 1 validation');
  await train();
  await page.getByRole('tab',{name:'Viewer',exact:true}).click();
  await page.getByRole('button',{name:'Project',exact:true}).click();
  await page.getByRole('button',{name:'New STL project'}).click();
  await expect(page.getByRole('heading',{name:'New STL project'})).toBeVisible();
  await expect(page.getByText('Original stereo SVO',{exact:true})).toBeVisible();
  await expect(page.getByText('Reference STL',{exact:true})).toBeVisible();
  console.log('Verified stereo/STL project entry');
} finally {
  await browser.close();
}
