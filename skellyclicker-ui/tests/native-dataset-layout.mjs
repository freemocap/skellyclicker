import {chromium,expect} from '@playwright/test';
import {writeFile} from 'node:fs/promises';
const b=await chromium.connectOverCDP('http://127.0.0.1:9224');
try{
 const p=b.contexts()[0].pages()[0];const close=p.getByRole('button',{name:'Close Configure training',exact:true});if(await close.count())await close.click();
 const open=p.getByRole('button',{name:'Project / images',exact:true});if(await open.count())await open.click();await p.getByRole('button',{name:'Images',exact:true}).click();
 const endpoint=await p.evaluate(()=>window.__TAURI_INTERNALS__.invoke('backend_url'));
 const session=await(await p.request.get(endpoint+'/api/session')).json();const path=session.state.project_path;
 const membership=await(await p.request.get(endpoint+'/api/labels/selection?project_path='+encodeURIComponent(path))).json();
 await expect(p.locator('.sdk-image-card')).toHaveCount(membership.selected_image_ids.length);
 expect((await p.locator('.sdk-image-card').evaluateAll(es=>es.map(e=>e.getAttribute('data-image-id')))).sort()).toEqual([...membership.selected_image_ids].sort());
 await expect(p.getByRole('group',{name:'Image inclusion filter'})).toHaveCount(0);await expect(p.locator('.skellyclicker-app > footer')).toHaveCount(0);
 const handle=p.getByRole('separator',{name:'Resize project sidebar'});const original=await handle.boundingBox();
 const resize=async x=>{const box=await handle.boundingBox();await p.mouse.move(box.x+box.width/2,box.y+120);await p.mouse.down();await p.mouse.move(x,box.y+120,{steps:10});await p.mouse.up();};
 const measure=()=>p.evaluate(()=>{const side=document.querySelector('.skellyclicker-sidebar').getBoundingClientRect();const catalog=document.querySelector('.sdk-image-catalog').getBoundingClientRect();const grid=document.querySelector('.sdk-image-members-grid');const cards=[...grid.children].map(e=>e.getBoundingClientRect());const scroll=document.querySelector('.sdk-image-catalog-scroll');return {columns:getComputedStyle(grid).gridTemplateColumns.split(' ').length,maxCardWidth:Math.max(...cards.map(r=>r.width)),bottomGap:side.bottom-catalog.bottom,scrollHeight:scroll.clientHeight,sideWidth:side.width,overflow:document.documentElement.scrollWidth>innerWidth};});
 const results=[];
 for(const tab of ['Viewer','Training']){
  await p.getByRole('tab',{name:tab,exact:true}).click();
  for(const logs of ['expanded','collapsed']){
   const button=p.getByRole('button',{name:logs==='expanded'?'Restore log panel':'Collapse log panel',exact:true});if(await button.count())await button.click();
   await resize(320);const narrow=await measure();await resize(680);const wide=await measure();
   expect(wide.columns).toBeGreaterThan(narrow.columns);expect(wide.maxCardWidth).toBeLessThanOrEqual(178);expect(narrow.maxCardWidth).toBeLessThanOrEqual(178);
   expect(wide.bottomGap).toBeLessThanOrEqual(12);expect(narrow.bottomGap).toBeLessThanOrEqual(12);expect(wide.overflow).toBe(false);expect(narrow.overflow).toBe(false);
   results.push({tab,logs,narrow,wide});
   if(tab==='Training'&&logs==='collapsed'){await p.screenshot({path:'../.test-artifacts/dataset-wide-native.png'});await resize(320);await p.screenshot({path:'../.test-artifacts/dataset-narrow-native.png'});}
  }
 }
 await resize(original.x+original.width/2);
 const after=await(await p.request.get(endpoint+'/api/labels/selection?project_path='+encodeURIComponent(path))).json();expect(after).toEqual(membership);
 await writeFile('../.test-artifacts/dataset-layout.json',JSON.stringify({membershipUnchanged:true,count:membership.selected_image_ids.length,results},null,2));console.log(JSON.stringify(results));
}finally{await b.close();}
