import {chromium,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
import {join} from 'node:path';

// This test moves two labels on disk. Supply a disposable recording with manual clicks.
const root=process.argv[2],url=process.argv[3]??'http://127.0.0.1:5176';
const doc=JSON.parse(await readFile(join(root,'skellyclicker','manual-labels.json'),'utf8'));
const clicks=doc.observations.filter(o=>o.origin==='click');
const images=new Set(clicks.map(o=>JSON.stringify([o.camera_id,o.source_frame])));
const saved=process.argv[4]?JSON.parse(await readFile(process.argv[4],'utf8')):null;
const epoch=saved?.epoch??2;
const browser=await chromium.launch({channel:'msedge',headless:true});
try {
  const page=await browser.newPage({viewport:{width:1440,height:960}});
  await page.addInitScript(root=>localStorage.setItem('skellyclicker.manualRecording',root),root);
  const run={id:'fixture',status:'running',epochs:10,validation_frames:[clicks.at(-1).source_frame]};
  await page.route('**/api/keypoint-training/runs?*',route=>route.fulfill({json:[run]}));
  await page.route('**/api/keypoint-training/runs/fixture/artifact?*',route=>{
    const path=new URL(route.request().url()).searchParams.get('path');
    const value=path==='status.json'?{run_id:run.id,status:'running',sequence:4,elapsed_seconds:10,
      metrics:[],operations:[],previews:[{id:'camera',operation_id:'train_model',step:epoch,label:'Sample',image_url:'/fixture.png'}]}:
      path==='dataset/manifest.json'?{keypoint_names:doc.tracked_point_names}:
      saved??{images:clicks.map(o=>({camera_id:o.camera_id,source_frame:o.source_frame,keypoints:[[o.x_px+3,o.y_px+4,1]]}))};
    return route.fulfill({json:value});
  });
  await page.goto(url);
  const training=page.getByRole('tab',{name:'Training',exact:true});
  const set=page.getByRole('tab',{name:'Training set',exact:true});
  await expect(set).toBeVisible({timeout:30000});
  await expect.poll(()=>training.evaluate(e=>getComputedStyle(e,'::after').animationName)).toBe('activity-border-orbit');
  await expect.poll(()=>training.evaluate(e=>getComputedStyle(e,'::after').backgroundImage)).toContain('conic-gradient');
  await set.click();
  await expect(page.getByRole('tabpanel',{name:'Training set'})).toBeVisible();
  await expect(page.locator('.recording-image-pair')).toHaveCount(images.size);
  await expect(page.getByRole('img',{name:'Labeled target close-up'}).first()).toBeVisible({timeout:30000});
  if(saved) await expect(page.getByText(/mean label–prediction distance/).first()).toBeVisible();
  else await expect(page.locator('.recording-gallery article').first()).toContainText('5.0 px');
  await page.getByRole('tab',{name:'Viewer'}).click();
  await expect(page.locator('.playback-target-closeup canvas[data-crop-status=available]').first()).toBeVisible({timeout:30000});
  await expect(page.locator('svg[aria-label="Model predictions"] path').first()).toBeVisible({timeout:30000});
  await expect(page.locator('.playback-target-closeup svg path').first()).toBeVisible();
  await page.getByRole('checkbox',{name:'Model predictions'}).uncheck();
  await expect(page.locator('svg[aria-label="Model predictions"] path')).toHaveCount(0);
  await expect(page.locator('.playback-target-closeup svg path')).toHaveCount(0);
  await expect(page.locator('.playback-target-closeup svg circle').first()).toBeVisible();
  await expect(page.locator('.label-image-overlay').first()).toBeVisible();
  await expect(page.locator('.playback-timeline-scrubber .label-quality-track')).toHaveCount(2);
  for(const track of await page.locator('.label-quality-track').all()) {
    await expect(track.locator('rect[fill^="hsl"]').first()).toBeVisible();
  }
  await set.click();
  const other=clicks.find(o=>o.source_frame!==doc.session.source_frame)??clicks[0];
  const item=page.locator('.recording-gallery article').filter({has:page.getByRole('heading',{name:other.camera_id+' · frame '+other.source_frame,exact:true})});
  const heading=await item.getByRole('heading').innerText();
  const [camera,frameText]=heading.split(' · frame ');
  const frame=Number(frameText);
  const target=clicks.find(o=>o.camera_id===camera&&o.source_frame===frame);
  const labelsPath=join(root,'skellyclicker','manual-labels.json');
  const matches=o=>o.camera_id===camera&&o.source_frame===frame&&o.point===target.point;
  const stored=async()=>JSON.parse(await readFile(labelsPath,'utf8'));
  for(const svg of [item.locator('.recording-image-pair > div svg'),item.getByRole('img',{name:'Labeled target close-up'})]) {
    const marker=svg.getByLabel('Drag '+target.point,{exact:true});
    await marker.scrollIntoViewIfNeeded();
    const before=(await stored()).observations.find(matches);
    const {x,y,dx,dy}=await marker.evaluate((el,p)=>{
      const m=el.getScreenCTM(),screen=new DOMPoint(p.x_px,p.y_px).matrixTransform(m);
      return {x:screen.x,y:screen.y,dx:12/m.a,dy:8/m.d};
    },before);
    await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x+12,y+8,{steps:4});await page.mouse.up();
    await expect.poll(async()=> (await stored()).observations.find(matches).x_px).toBeCloseTo(before.x_px+dx,0);
    expect((await stored()).observations.find(matches).y_px).toBeCloseTo(before.y_px+dy,0);
  }
  const edited=await stored();
  expect(edited.observations.filter(o=>!matches(o))).toEqual(doc.observations.filter(o=>!matches(o)));
  await page.reload();await set.click();
  await expect(item.locator('.training-label-handle').first().locator('circle').first()).toHaveAttribute('cx',String(edited.observations.find(matches).x_px));
  console.log('PASS rotating tab border, both quality tracks, full/crop marker dragging, persisted coordinates and playback overlays');
} finally {await browser.close();}
