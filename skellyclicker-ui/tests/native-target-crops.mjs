import {chromium,expect} from '@playwright/test';
import {writeFile} from 'node:fs/promises';
const browser=await chromium.connectOverCDP('http://127.0.0.1:9224');
const evidence={checks:[],errors:[],requests:[]};
try {
 const page=browser.contexts().flatMap(c=>c.pages()).find(p=>p.url().includes('5176'));
 page.on('pageerror',e=>evidence.errors.push(String(e)));
 page.on('request',r=>{if(r.url().includes('target-crops'))evidence.requests.push(r.url())});
 await page.reload();
 await expect(page.locator('.playback-target-closeup canvas')).toHaveCount(2,{timeout:30000});
 await page.waitForFunction(()=>[...document.querySelectorAll('.playback-target-closeup canvas')].every(c=>c.dataset.cropStatus==='available'),{},{timeout:90000});
 expect(await page.locator('video').evaluateAll(v=>v.every(x=>x.src.includes('annotated')))).toBe(true);
 async function check(name){
  const state=await page.evaluate(()=>({main:[...document.querySelectorAll('.playback-presented-image')].map(c=>({...c.dataset})),crops:[...document.querySelectorAll('.playback-target-closeup canvas')].map(c=>({...c.dataset})),sources:[...document.querySelectorAll('video')].map(v=>v.src)}));
  expect(state.crops.length).toBe(2);
  for(let i=0;i<2;i++){expect(state.crops[i].cropStatus).toBe('available');expect(state.crops[i].presentedFrame).toBe(state.main[i].presentedFrame);expect(state.crops[i].presentationEpoch).toBe(state.main[i].presentationEpoch);}
  evidence.checks.push({name,...state});
 }
 async function seek(frame){await page.locator('.playback-timeline-input').fill(String(frame));await page.locator('.playback-timeline-input').dispatchEvent('pointerup');await page.waitForFunction(f=>[...document.querySelectorAll('.playback-target-closeup canvas')].every(c=>c.dataset.presentedFrame===String(f)),frame,{timeout:15000});}
 await check('initial90');
 const cdp=await page.context().newCDPSession(page);
 await cdp.send('Emulation.setDeviceMetricsOverride',{width:1100,height:800,deviceScaleFactor:1,mobile:false});await page.waitForTimeout(200);await check('resize1100');
 await cdp.send('Emulation.clearDeviceMetricsOverride');await page.waitForTimeout(200);await check('resizeRestored');await seek(30);await check('source120');
 for(const mode of ['Raw','Annotated']){await page.getByRole('button',{name:mode,exact:true}).click();await page.waitForFunction(()=>[...document.querySelectorAll('.playback-target-closeup canvas')].every(c=>c.dataset.cropStatus==='available'));await check(mode);}
 await seek(375);await check('nonzero375');
 const canvas=page.locator('.playback-presented-image').first();await canvas.hover();await page.mouse.wheel(0,-100);await check('zoom');
 await page.getByRole('button',{name:'Play',exact:true}).click();await page.waitForTimeout(1500);await page.locator('.playback-btn-play[aria-label=Pause]').click();await check('playpause');
 const loop=page.locator('.playback-controls-group-loop-speed button').first();if(!(await loop.getAttribute('title'))?.includes('is on'))await loop.click();
 await seek(745);await page.getByRole('button',{name:'Play',exact:true}).click();await page.waitForFunction(()=>Number(document.querySelector('.playback-timeline-input').value)<90,{},{timeout:15000});await page.locator('.playback-btn-play[aria-label=Pause]').click();await check('loop');
 if((await loop.getAttribute('title'))?.includes('is on'))await loop.click();await seek(30);
 await page.getByRole('button',{name:'Frame the subject',exact:true}).click();await page.screenshot({path:'../.test-artifacts/target-closeups-native.png'});
 expect(evidence.errors).toEqual([]);await writeFile('../.test-artifacts/target-closeups-native.json',JSON.stringify(evidence,null,2));console.log('PASS',evidence.checks.map(c=>c.name));
}finally{await browser.close();}
