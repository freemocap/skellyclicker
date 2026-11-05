import {chromium,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
import {PlaybackManifestSchema,decodePlaybackParquet,prepareRecordedModelFrame} from '@freemocap/client/recording';
const nativePort=process.env.SKELLYCLICKER_TEST_CDP_PORT;
const endpointOverride=process.env.SKELLYCLICKER_TEST_BACKEND_URL;
const discovery=endpointOverride?null:await chromium.connectOverCDP('http://127.0.0.1:'+(nativePort??'9224'));
const nativePage=discovery?.contexts()[0].pages().find(p=>!p.url().startsWith('devtools:'));
const endpoint=endpointOverride??await nativePage.evaluate(()=>window.__TAURI_INTERNALS__.invoke('backend_url'));
if(!nativePort)await discovery?.close();
const root='C:/Users/jonma/freemocap_data/skellyclicker_projects/benchy-sfn26';const projectPath=root+'/benchy-sfn26_project.json';
const project=JSON.parse(await readFile(projectPath,'utf8'));const folder=root+'/'+project.playback_result;
const manifest=PlaybackManifestSchema.parse(JSON.parse(await readFile(folder+'/playback.json','utf8')));const run=manifest.runs[0];
const bytes=await readFile(folder+'/display.parquet');const decoded=await decodePlaybackParquet(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),manifest);
const expected=Object.fromEntries(run.models.map(m=>{const reader=prepareRecordedModelFrame(run,{channels:decoded[0]},m,'stereo');return [m.model_id,run.timelines[0].timestamps_s.map(t=>Array.from(reader(t).segmentOrigins.data))]}));
const browser=nativePort?discovery:await chromium.launch({channel:'msedge',headless:true});
const prefix=nativePort?'native-':'';const errors=[],requests=[];
try{
 const page=nativePort?nativePage:await browser.newPage({viewport:{width:1600,height:1000}});
 page.on('pageerror',e=>errors.push(String(e)));page.on('request',r=>{if(r.url().includes(endpoint))requests.push(r.url())});
 await page.addInitScript(({endpoint,projectPath,expected})=>{
  window.isTauri=true;if(!window.__TAURI_INTERNALS__)window.__TAURI_INTERNALS__={invoke:async()=>endpoint};localStorage.setItem('skellyclicker.projectPath',projectPath);
  const presented=new WeakMap(),layouts=new Map();window.__cloudStats=[];window.__cloudMessages=[];window.__cloudErrors=[];window.__modelErrors=[];window.__modelChecks=0;window.__surfaceStats=[];window.__committedFrames=[];window.__videoFrames=[[],[]];
  const shown=()=>[...document.querySelectorAll('.playback-presented-image')].map(c=>c.dataset.presentedFrame===undefined?null:Number(c.dataset.presentedFrame));
  window.__shown=shown;
  new MutationObserver(()=>{const canvases=[...document.querySelectorAll('.playback-presented-image')];if(canvases.length===2&&canvases.every(c=>c.dataset.presentedFrame!==undefined))window.__committedFrames.push({wall:performance.now(),frames:shown(),epochs:canvases.map(c=>c.dataset.presentationEpoch)});}).observe(document,{subtree:true,attributes:true,attributeFilter:['data-presented-frame']});
  const callback=HTMLVideoElement.prototype.requestVideoFrameCallback;
  HTMLVideoElement.prototype.requestVideoFrameCallback=function(fn){const video=this;return callback.call(this,(now,metadata)=>{const frame=Math.round(metadata.mediaTime*30);presented.set(video,frame);const index=[...document.querySelectorAll('video')].indexOf(video);if(index>=0&&index<2)window.__videoFrames[index].push({wall:performance.now(),frame,presented:metadata.presentedFrames});fn(now,metadata)})};
  const post=Worker.prototype.postMessage;
  Worker.prototype.postMessage=function(message,...args){
   if(message?.type?.startsWith('pointCloud'))window.__cloudMessages.push({wall:performance.now(),...message,videos:shown()});
   if(!this.__observed){this.__observed=true;this.addEventListener('message',event=>{
    if(event.data?.type==='pointCloudStats')window.__cloudStats.push({...event.data.data,wall:performance.now(),videos:[...document.querySelectorAll('video')].map(v=>({frame:presented.get(v),time:v.currentTime,paused:v.paused}))});
    if(event.data?.type==='stats'&&event.data.data?.modelSurfaces)window.__surfaceStats.push({wall:performance.now(),...event.data.data.modelSurfaces});
    if(event.data?.type==='pointCloudError')window.__cloudErrors.push(event.data.message);
   })}
   if(message?.type==='viewportFrame'&&message.stream==='modelFrames'){
    const key=message.sessionId+':'+message.layoutVersion;if(message.layout)layouts.set(key,message.layout);const layout=layouts.get(key);
    const frames=shown();
    for(const model of layout?.models??[]){if(!model.origins)continue;const values=Array.from(new Float32Array(message.buffer,model.origins.offset,model.origins.length));if(!values.every(Number.isFinite))continue;
     const want=expected[model.modelId]?.[frames[0]];window.__modelChecks++;
     if(!want||!frames.every(f=>f===frames[0])||!values.every((v,i)=>Math.abs(v-want[i])<.02))window.__modelErrors.push({frames,model:model.modelId,values,want});
    }
   }
   return post.call(this,message,...args);
  };
 },{endpoint,projectPath,expected});
 await page.goto('http://127.0.0.1:5176');await expect(page.locator('.playback-timeline-input')).toHaveAttribute('max','750',{timeout:30000});
 await page.waitForFunction(()=>window.__cloudStats.some(s=>s.status==='ready'&&s.mode==='clip'&&s.residentChunks===s.totalChunks&&s.visible&&s.renderedSourceFrameIndex===90),{},{timeout:30000});

 await page.getByRole('button',{name:'Annotated',exact:true}).click();await page.waitForFunction(()=>[...document.querySelectorAll('video')].every(v=>v.src.includes('annotated')&&v.readyState>=2));
 await page.getByRole('button',{name:'Frame the subject',exact:true}).click();await page.waitForTimeout(1200);
 await page.waitForFunction(()=>{const s=window.__cloudStats.at(-1);return s?.status==='ready'&&s.residentChunks===s.totalChunks},{},{timeout:30000});
 const cloudRequestsAtReady=requests.filter(u=>u.includes('/point-cloud/')).length;
 await page.screenshot({path:'../.test-artifacts/'+prefix+'reconstruction-smoke.png'});
 if(process.argv.includes('--sustained')||process.argv.includes('--seek-only')){
  const marks=[];
  async function mark(name){marks.push({name,...await page.evaluate(()=>({wall:performance.now(),video:document.querySelector('video').currentTime,frame:Number(document.querySelector('.playback-timeline-input').value),cloud:window.__cloudStats.at(-1),quality:[...document.querySelectorAll('video')].map(v=>{const q=v.getVideoPlaybackQuality();return {totalVideoFrames:q.totalVideoFrames,droppedVideoFrames:q.droppedVideoFrames}})}))})}
  async function pause(){const button=page.locator('.playback-btn-play[aria-label=Pause]');if(await button.count())await button.click()}
  async function seek(frame){await pause();await page.locator('.playback-timeline-input').fill(String(frame));await page.locator('.playback-timeline-input').dispatchEvent('pointerup');await page.waitForFunction(f=>window.__cloudStats.at(-1)?.renderedFrameIndex===f&&window.__shown().length===2&&window.__shown().every(v=>v===f),frame,{timeout:15000})}
  const loop=page.locator('.playback-controls-group-loop-speed button').first();if((await loop.getAttribute('title'))?.includes('is on'))await loop.click();
  if(!process.argv.includes('--seek-only')){
  await seek(0);await mark('sustained-start');await page.getByRole('button',{name:'Play',exact:true}).click();
  await page.waitForFunction(()=>[...document.querySelectorAll('video')].every(v=>v.paused)&&window.__videoFrames.every(v=>v.at(-1)?.frame===750)&&window.__cloudStats.at(-1)?.renderedFrameIndex===750,{},{timeout:40000});await mark('sustained-end');
  await page.getByRole('button',{name:'Play',exact:true}).click();await page.waitForFunction(()=>{const s=window.__cloudStats.at(-1);return s?.renderedSourceFrameIndex>90&&s.renderedSourceFrameIndex<180&&Number(document.querySelector('.playback-timeline-input').value)>0},{},{timeout:12000});await mark('end-replay');await pause();
  await seek(730);await loop.click();await mark('loop-start');await page.getByRole('button',{name:'Play',exact:true}).click();
  await page.waitForFunction(()=>{const s=window.__cloudStats.at(-1);return s?.renderedFrameIndex>5&&s.renderedFrameIndex<90},{},{timeout:12000});await mark('loop-one');
  await page.waitForTimeout(27000);await mark('loop-two');if(marks.at(-1).frame>=180)throw Error('Second loop did not reset the presented frame');await pause();
  if((await loop.getAttribute('title'))?.includes('is on'))await loop.click();
  }
  for(const frame of [375,749,1,750,0]){await seek(frame);await mark('seek-'+frame)}
  const detailed=await page.evaluate(()=>({stats:window.__cloudStats,committedFrames:window.__committedFrames,surfaceStats:window.__surfaceStats,cloudMessages:window.__cloudMessages,videoFrames:window.__videoFrames,modelErrors:window.__modelErrors,modelChecks:window.__modelChecks,cloudErrors:window.__cloudErrors}));
  const start=marks.find(m=>m.name==='sustained-start'),end=marks.find(m=>m.name==='sustained-end');
  const steady=start&&end?detailed.stats.filter(s=>s.wall>start.wall+1000&&s.wall<end.wall-1000):[];
  const visibility=steady.length?steady.filter(s=>s.visible).length/steady.length:null;
  const cadence=steady.length>1?(steady.at(-1).uploads-steady[0].uploads)*1000/(steady.at(-1).wall-steady[0].wall):null;
  const videoPresentation=start&&end?detailed.videoFrames.map((frames,i)=>{const selected=frames.filter(f=>f.wall>=start.wall&&f.wall<=end.wall);return {callbackHz:selected.length*1000/(end.wall-start.wall),uniqueFrames:new Set(selected.map(f=>f.frame)).size,qualityStart:start.quality[i],qualityEnd:end.quality[i]}}):[];
  const resourceBounds={cacheBytes:Math.max(...detailed.stats.map(s=>s.cacheBytes)),chunks:Math.max(...detailed.stats.map(s=>s.residentChunks)),inFlight:Math.max(...detailed.stats.map(s=>s.inFlight)),geometryCount:new Set(detailed.stats.filter(s=>s.geometryId).map(s=>s.geometryId)).size,positionAttributeCount:new Set(detailed.stats.filter(s=>s.visible).map(s=>s.positionAttributeId)).size,colorAttributeCount:new Set(detailed.stats.filter(s=>s.visible).map(s=>s.colorAttributeId)).size,maxCpuCopyMs:Math.max(...detailed.stats.map(s=>s.maxUploadMs))};
  const hiddenReasons=Object.fromEntries([...new Set(steady.map(s=>s.hiddenReason))].map(reason=>[reason,steady.filter(s=>s.hiddenReason===reason).length]));
  const postReadyCloudRequests=requests.filter(u=>u.includes('/point-cloud/')).length-cloudRequestsAtReady;
  const commits=start&&end?detailed.committedFrames.filter(f=>f.wall>=start.wall&&f.wall<=end.wall):[];
  const committedHz=commits.length*1000/(end?.wall-start?.wall);
  if(detailed.committedFrames.some(f=>f.frames[0]!==f.frames[1]||f.epochs[0]!==f.epochs[1]))throw Error('Visible camera pair identity mismatch');
  const report={endpoint,marks,committedHz,hiddenReasons,postReadyCloudRequests,steadyCloudVisibility:visibility,cloudUpdateHz:cadence,videoPresentation,resourceBounds,...detailed,errors,requests};await writeFile('../.test-artifacts/'+prefix+'reconstruction-sustained.json',JSON.stringify(report,null,2));
  console.log('SUSTAINED '+JSON.stringify({marks:marks.map(m=>({name:m.name,wall:m.wall,frame:m.frame,cloudFrame:m.cloud?.renderedFrameIndex})),samples:detailed.stats.length,committedHz,hiddenReasons,postReadyCloudRequests,steadyCloudVisibility:visibility,cloudUpdateHz:cadence,videoPresentation,resourceBounds,modelChecks:detailed.modelChecks,modelErrors:detailed.modelErrors.length,cloudErrors:detailed.cloudErrors,errors}));
  if(resourceBounds.geometryCount!==1||resourceBounds.positionAttributeCount!==1||resourceBounds.colorAttributeCount!==1)throw Error('Point geometry or attributes recreated during playback');
  if(requests.some(u=>u.includes('/preparation/image')))throw Error('Per-frame image requests returned');
  if(visibility!==null&&visibility<.9)throw Error('Cloud missing during sustained playback: visible fraction '+visibility);
  if(postReadyCloudRequests!==0||detailed.stats.some(s=>s.reservedBytes>s.maxResidentBytes||s.inFlight>s.concurrency)||detailed.cloudErrors.length||detailed.modelErrors.length||errors.length)throw Error('Resident cache, resource budget or synchronization failed');
 }
 const result=await page.evaluate(()=>({cloud:window.__cloudStats.at(-1),cloudErrors:window.__cloudErrors,modelErrors:window.__modelErrors,modelChecks:window.__modelChecks}));
 await writeFile('../.test-artifacts/'+prefix+'reconstruction-smoke.json',JSON.stringify({endpoint,...result,errors,requests},null,2));console.log(JSON.stringify({endpoint,...result,errors,requests:requests.length}));
 if(result.cloudErrors.length||result.modelErrors.length||errors.length)throw Error('Reconstruction integration failed');
}catch(error){
 const page=browser.contexts()[0]?.pages().find(p=>!p.url().startsWith('devtools:'));
 if(page){const state=await page.evaluate(()=>({frame:document.querySelector('.playback-timeline-input')?.value,stats:window.__cloudStats,committedFrames:window.__committedFrames,surfaceStats:window.__surfaceStats,cloudMessages:window.__cloudMessages,videoFrames:window.__videoFrames,modelErrors:window.__modelErrors,modelChecks:window.__modelChecks,cloudErrors:window.__cloudErrors,videos:[...document.querySelectorAll('video')].map(v=>({time:v.currentTime,paused:v.paused,ended:v.ended}))}));await writeFile('../.test-artifacts/'+prefix+'reconstruction-failure.json',JSON.stringify({error:String(error),state,errors,requests},null,2));await page.screenshot({path:'../.test-artifacts/'+prefix+'reconstruction-failure.png'})}
 throw error;
}finally{await browser.close()}
