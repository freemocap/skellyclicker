import {createRequire} from 'node:module';
import {writeFile} from 'node:fs/promises';
const require=createRequire(new URL('../skellyclicker-ui/package.json',import.meta.url));
const {chromium,expect}=require('@playwright/test');
const browser=await chromium.launch({channel:'msedge',headless:true});
const results=[],requests=[];
const artifacts=new URL('../.test-artifacts/',import.meta.url);
try{
 const page=await browser.newPage({viewport:{width:1600,height:1000}});
 page.on('request',r=>{if(r.url().includes('/point-cloud/'))requests.push(r.url())});
 await page.addInitScript(()=>{window.isTauri=true;window.__TAURI_INTERNALS__={invoke:async()=> 'http://127.0.0.1:8006'};localStorage.setItem('skellyclicker.projectPath','C:/Users/jonma/freemocap_data/skellyclicker_projects/benchy-sfn26/benchy-sfn26_project.json')});
 await page.goto('http://127.0.0.1:5176');await expect(page.getByText('Point cloud ready',{exact:true})).toBeVisible({timeout:30000});
 const initial=requests.length;
 for(const mode of ['Annotated','Raw']){
  await page.getByRole('button',{name:mode,exact:true}).click();
  await page.waitForFunction(mode=>{const vs=[...document.querySelectorAll('video')];return vs.length===2&&vs.every(v=>v.src.includes(mode==='Annotated'?'annotated':'synchronized')&&v.readyState>=2)},mode,{timeout:15000});
  for(const frame of [0,375,600,650,749]){
   console.log('Checking',mode,frame);
   await page.locator('.playback-timeline-input').fill(String(frame));await page.locator('.playback-timeline-input').dispatchEvent('pointerup');
   await page.waitForFunction(f=>{const a=[...document.querySelectorAll('.playback-presented-image')];return a.length===2&&a.every(c=>c.dataset.presentedFrame===String(f))},frame,{timeout:15000});
   for(let camera=0;camera<2;camera++){
    const shown=(await page.locator('.playback-presented-image').elementHandles())[camera];
    const prior=await shown.getAttribute('style');
    await shown.evaluate(c=>{const marker=document.createComment('test-canvas');c.before(marker);c.__testMarker=marker;document.body.append(c);c.style.cssText='position:fixed;left:0;top:0;width:640px;height:360px;max-width:none;max-height:none;z-index:99999;object-fit:fill;background:black';});
    const actual=new URL(`./pixel-${mode}-${frame}-${camera}-actual.png`,artifacts).pathname;
    const expected=new URL(`./pixel-${mode}-${frame}-${camera}-expected.png`,artifacts).pathname;
    const actualPath=decodeURIComponent(actual.replace(/^\/([A-Za-z]:)/,'$1'));
    const expectedPath=decodeURIComponent(expected.replace(/^\/([A-Za-z]:)/,'$1'));
    await shown.screenshot({path:actualPath});
    const bounds=await shown.boundingBox();
    const metadata=await page.evaluate(async({frame,camera,bounds})=>{
     const source=document.querySelectorAll('video')[camera];
     const video=document.createElement('video');video.id='referenceVideo';video.muted=true;video.style.cssText='position:fixed;width:2px;height:2px;left:0;top:0;opacity:.001';document.body.append(video);
     let latest=null;const cb=(_now,m)=>{latest=m.mediaTime;video.requestVideoFrameCallback(cb)};video.requestVideoFrameCallback(cb);
     await new Promise((resolve,reject)=>{video.onloadeddata=resolve;video.onerror=reject;video.src=source.src;video.load()});
     video.currentTime=frame===0?0:(frame+.5)/30;
     const deadline=performance.now()+10000;
     while(Math.round((latest??-999)*30)!==frame){if(performance.now()>deadline)throw Error('Reference frame timed out');await new Promise(r=>setTimeout(r,10))}
     const canvas=document.createElement('canvas');canvas.id='referenceCanvas';canvas.width=video.videoWidth;canvas.height=video.videoHeight;
     canvas.getContext('2d').drawImage(video,0,0);canvas.style.cssText=`position:fixed;left:0;top:0;width:${bounds.width}px;height:${bounds.height}px;z-index:100000;object-fit:fill;background:black`;document.body.append(canvas);
     return {camera,frame,referenceMediaTime:latest};
    },{frame,camera,bounds});
    await page.locator('#referenceCanvas').screenshot({path:expectedPath});
    await page.evaluate(()=>{document.querySelector('#referenceCanvas').remove();const v=document.querySelector('#referenceVideo');v.pause();v.removeAttribute('src');v.load();v.remove()});
    await shown.evaluate((c,style)=>{c.__testMarker.replaceWith(c);delete c.__testMarker;if(style===null)c.removeAttribute('style');else c.setAttribute('style',style)},prior);
    results.push({mode,...metadata,actualPath,expectedPath});
   }
  }
 }
 await writeFile(new URL('./presentation-pixels.json',artifacts),JSON.stringify({results,cloudRequests:requests.length,postReadyCloudRequests:requests.length-initial},null,2));
 console.log(JSON.stringify({comparisons:results.length,postReadyCloudRequests:requests.length-initial}));
 if(requests.length!==initial)throw Error('Cloud refetched on media choice/seeks');
}catch(error){const page=browser.contexts()[0]?.pages()[0];if(page)console.log(JSON.stringify(await page.evaluate(()=>({canvases:[...document.querySelectorAll('.playback-presented-image')].map(c=>({...c.dataset,width:c.width,height:c.height})),videos:[...document.querySelectorAll('video')].map(v=>({src:v.src,time:v.currentTime,ready:v.readyState})),body:document.body.innerText.slice(-1500)}))));throw error;}finally{await browser.close()}
