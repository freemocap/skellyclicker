import {chromium,expect} from '@playwright/test';
import {writeFile} from 'node:fs/promises';
const browser=await chromium.connectOverCDP('http://127.0.0.1:9224');
const evidence={checks:[],errors:[]};
try{
 const page=browser.contexts().flatMap(c=>c.pages()).find(p=>p.url().includes('5176'));
 page.on('pageerror',e=>evidence.errors.push(String(e)));
 await page.reload();
 const figures=page.locator('.playback-target-closeup');await expect(figures).toHaveCount(2,{timeout:30000});
 await page.waitForFunction(()=>[...document.querySelectorAll('.playback-target-closeup canvas')].every(c=>c.dataset.cropStatus==='available'),{},{timeout:30000});
 const first=figures.first(),second=figures.nth(1);
 async function box(locator){const b=await locator.boundingBox();if(!b)throw Error('Missing inset');return b;}
 async function drag(handle,dx,dy){const b=await box(handle);await page.mouse.move(b.x+b.width/2,b.y+b.height/2);await page.mouse.down();await page.mouse.move(b.x+b.width/2+dx,b.y+b.height/2+dy,{steps:10});await page.mouse.up();}
 async function check(name){const values=await figures.evaluateAll(fs=>fs.map(f=>{const b=f.getBoundingClientRect(),p=f.parentElement.getBoundingClientRect(),c=f.querySelector('canvas'),main=f.parentElement.querySelector('.playback-presented-image');return {box:{x:b.x,y:b.y,width:b.width,height:b.height},parent:{x:p.x,y:p.y,width:p.width,height:p.height},crop:{...c.dataset},main:{...main.dataset}};}));
  for(const v of values){expect(v.box.x).toBeGreaterThanOrEqual(v.parent.x-1);expect(v.box.y).toBeGreaterThanOrEqual(v.parent.y-1);expect(v.box.x+v.box.width).toBeLessThanOrEqual(v.parent.x+v.parent.width+1);expect(v.box.y+v.box.height).toBeLessThanOrEqual(v.parent.y+v.parent.height+1);expect(v.crop.presentedFrame).toBe(v.main.presentedFrame);expect(v.crop.presentationEpoch).toBe(v.main.presentationEpoch);}
  evidence.checks.push({name,values});return values;
 }
 const original=await check('largerDefault');expect(original[0].box.width).toBeGreaterThan(180);
 const secondBefore=await box(second);await drag(first.getByRole('button',{name:/^Move .* target close-up$/}),-35,-100);const moved=await box(first);expect(Math.abs(moved.y-original[0].box.y)).toBeGreaterThan(20);expect(await box(second)).toEqual(secondBefore);await check('pausedDrag');
 await drag(first.getByRole('button',{name:/^Resize .* target close-up$/}),-55,-55);const resized=await box(first);expect(Math.abs(resized.width-moved.width)).toBeGreaterThan(20);await check('pausedResize');
 await page.getByRole('button',{name:'Raw',exact:true}).click();await page.waitForFunction(()=>[...document.querySelectorAll('.playback-target-closeup canvas')].every(c=>c.dataset.cropStatus==='available'));expect(await box(first)).toEqual(resized);await check('rawRetainsLayout');
 await page.getByRole('button',{name:'Annotated',exact:true}).click();await page.waitForFunction(()=>[...document.querySelectorAll('.playback-target-closeup canvas')].every(c=>c.dataset.cropStatus==='available'));
 await page.getByRole('button',{name:'Play',exact:true}).click();await drag(first.getByRole('button',{name:/^Move .* target close-up$/}),20,30);await drag(first.getByRole('button',{name:/^Resize .* target close-up$/}),30,30);await page.locator('.playback-btn-play[aria-label=Pause]').click();await check('liveDragResize');
 const cdp=await page.context().newCDPSession(page);await cdp.send('Emulation.setDeviceMetricsOverride',{width:1000,height:750,deviceScaleFactor:1,mobile:false});await page.waitForTimeout(250);await check('parentResize');await cdp.send('Emulation.clearDeviceMetricsOverride');await page.waitForTimeout(250);await check('restoreParent');
 await page.screenshot({path:'../.test-artifacts/target-closeups-interactive.png'});expect(evidence.errors).toEqual([]);await writeFile('../.test-artifacts/target-closeups-interactive.json',JSON.stringify(evidence,null,2));console.log('PASS',evidence.checks.map(x=>x.name));
}finally{await browser.close();}
