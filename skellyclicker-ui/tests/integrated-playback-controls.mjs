import {chromium,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
import {PlaybackManifestSchema,decodePlaybackParquet,prepareRecordedModelFrame} from '@freemocap/client/recording';
const nativeTest=!!process.env.SKELLYCLICKER_TEST_CDP_PORT;
const native=await chromium.connectOverCDP('http://127.0.0.1:'+(process.env.SKELLYCLICKER_TEST_CDP_PORT??'9224'));const np=native.contexts()[0].pages().find(p=>!p.url().startsWith('devtools:'));
const endpoint=await np.evaluate(()=>window.__TAURI_INTERNALS__.invoke('backend_url'));if(!nativeTest)await native.close();
const root='C:/Users/jonma/freemocap_data/skellyclicker_projects/benchy-sfn26';const projectPath=root+'/benchy-sfn26_project.json';
const project=JSON.parse(await readFile(projectPath,'utf8')),folder=root+'/'+project.playback_result;
const manifest=PlaybackManifestSchema.parse(JSON.parse(await readFile(folder+'/playback.json','utf8'))),run=manifest.runs[0];const bytes=await readFile(folder+'/display.parquet');const decoded=await decodePlaybackParquet(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),manifest);
const expected=Object.fromEntries(run.models.map(model=>{const read=prepareRecordedModelFrame(run,{channels:decoded[0]},model,'stereo');return [model.model_id,run.timelines[0].timestamps_s.map(t=>Array.from(read(t).segmentOrigins.data))];}));
const browser=nativeTest?native:await chromium.launch({channel:'msedge',headless:true});
try {
 const page=nativeTest?np:await browser.newPage({viewport:{width:1600,height:1000}});const errors=[],requests=[];page.on('pageerror',e=>errors.push(String(e)));page.on('request',r=>{if(r.url().includes(endpoint))requests.push(r.url());});
 await page.addInitScript(({endpoint,projectPath,expected})=>{
  globalThis.isTauri=true;if(!window.__TAURI_INTERNALS__)window.__TAURI_INTERNALS__={invoke:async()=>endpoint};localStorage.setItem('skellyclicker.projectPath',projectPath);
  const presented=new WeakMap(),layouts=new Map();window.__alignment=[];
  const callback=HTMLVideoElement.prototype.requestVideoFrameCallback;
  HTMLVideoElement.prototype.requestVideoFrameCallback=function(fn){const video=this;return callback.call(this,(now,metadata)=>{presented.set(video,Math.round(metadata.mediaTime*30));fn(now,metadata);});};
  const post=Worker.prototype.postMessage;
  Worker.prototype.postMessage=function(message,...args){
   if(message?.type==='viewportFrame'&&message.stream==='modelFrames'){
    const key=message.sessionId+':'+message.layoutVersion;if(message.layout)layouts.set(key,message.layout);const layout=layouts.get(key);
    const videoFrames=[...document.querySelectorAll('video')].map(v=>presented.get(v));
    for(const model of layout?.models??[]){if(!model.origins)continue;const values=Array.from(new Float32Array(message.buffer,model.origins.offset,model.origins.length));if(!values.every(Number.isFinite))continue;
     const frame=videoFrames[0],want=expected[model.modelId]?.[frame];window.__alignment.push({model:model.modelId,frame,videoFrames,values,okay:videoFrames.length===2&&videoFrames.every(f=>f===frame)&&!!want&&values.every((v,i)=>Math.abs(v-want[i])<.02)});
    }
    if(window.__alignment.length>2000)window.__alignment.splice(0,1000);
   }
   return post.call(this,message,...args);
  };
 },{endpoint,projectPath,expected});
 await page.goto('http://127.0.0.1:5176');await expect(page.locator('.playback-timeline-input')).toHaveAttribute('max',String(run.timelines[0].frame_numbers.length-1),{timeout:30000});await page.waitForFunction(()=>document.querySelectorAll('video').length===2&&[...document.querySelectorAll('video')].every(v=>v.readyState>=2));await expect(page.getByRole('button',{name:'Play',exact:true})).toBeEnabled({timeout:30000});
 await page.getByText('Prepare another sample range',{exact:true}).click();
 const startField=page.getByRole('spinbutton',{name:'First source frame',exact:true});
 const countField=page.getByRole('spinbutton',{name:'Frames',exact:true});
 const prepare=page.getByRole('button',{name:'Prepare fresh samples',exact:true});
 await countField.fill('901');await expect(prepare).toBeDisabled();await countField.fill('30');
 await startField.fill('-1');await expect(prepare).toBeDisabled();await startField.fill('0');await expect(prepare).toBeEnabled();
 const legend=page.getByRole('region',{name:'Pose candidates',exact:true});
 await expect(legend.locator('.sdk-legend-swatch')).toHaveCount(3);
 await legend.getByText('Details',{exact:true}).click();await expect(legend).toContainText('not detector predictions');await legend.getByText('Details',{exact:true}).click();
 const styles=await page.evaluate(()=>{
  const input=getComputedStyle(document.querySelector('.sdk-number-container'));
  const action=getComputedStyle([...document.querySelectorAll('button')].find(b=>b.textContent==='Prepare fresh samples'));
  const legend=getComputedStyle(document.querySelector('.sdk-legend'));
  return {inputBackground:input.backgroundColor,inputBorder:input.borderTopWidth,buttonBackground:action.backgroundColor,buttonColor:action.color,legendDisplay:legend.display};
 });
 if(styles.inputBackground==='rgba(0, 0, 0, 0)'||styles.inputBorder==='0px'||styles.buttonBackground==='rgba(0, 0, 0, 0)'||styles.legendDisplay!=='flex')throw Error('SDK theme not applied: '+JSON.stringify(styles));
 const loaded=requests.length;await page.getByRole('button',{name:'Play',exact:true}).click();await page.waitForTimeout(750);if(await page.locator('.playback-btn-play[aria-label=Pause]').count())await page.locator('.playback-btn-play[aria-label=Pause]').click();
 const playRequests=requests.slice(loaded);
 for(const frame of [12,21,14,29,1,20,0]){await page.locator('.playback-timeline-input').fill(String(frame));await page.locator('.playback-timeline-input').dispatchEvent('pointerup');await page.waitForFunction(f=>[...document.querySelectorAll('video')].every(v=>Math.floor(v.currentTime*30+1e-5)===f),frame);await page.waitForTimeout(120);if(frame===12||frame===21)await page.screenshot({path:'../.test-artifacts/'+(nativeTest?'native-':'')+'scene-frame-'+frame+'.png'});}
 await page.getByRole('button',{name:'Annotated',exact:true}).click();await page.waitForFunction(()=>[...document.querySelectorAll('video')].every(v=>v.src.includes('annotated')&&v.readyState>=2));
 const resize=[];
 async function drag(locator,delta){const before=await page.locator('.skellyclicker-sidebar').boundingBox(),box=await locator.boundingBox();await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();await page.mouse.move(box.x+box.width/2+delta.x,box.y+box.height/2+delta.y,{steps:8});await page.mouse.up();await page.waitForTimeout(150);resize.push({before,after:await page.locator('.skellyclicker-sidebar').boundingBox()});}
 await drag(page.getByRole('separator',{name:'Resize project sidebar'}),{x:90,y:0});
 const panels=page.locator('[data-panel-resize-handle-id]');const beforeMedia=await page.locator('.playback-mode-video-feed-container').boundingBox();await drag(panels.nth(1),{x:-100,y:0});const afterMedia=await page.locator('.playback-mode-video-feed-container').boundingBox();
 const beforeLogs=await page.locator('.sdk-bottom-log-panel').boundingBox();await drag(page.getByRole('separator',{name:'Resize log panel'}),{x:0,y:-60});const afterLogs=await page.locator('.sdk-bottom-log-panel').boundingBox();
 const tile=page.locator('.video-feed-tile').first(),beforeTile=await tile.boundingBox();await drag(tile.locator('.react-resizable-handle'),{x:-55,y:-70});const afterTile=await tile.boundingBox();
 await page.getByRole('button',{name:'Frame the subject',exact:true}).click();await page.waitForTimeout(1900);
 const alignment=await page.evaluate(()=>window.__alignment);const mismatches=alignment.filter(a=>!a.okay);
 const result={nativeTest,endpoint,styles,initialRequests:requests.slice(0,loaded),playRequests,alignmentCount:alignment.length,mismatches,resize,beforeMedia,afterMedia,beforeLogs,afterLogs,beforeTile,afterTile,errors};
 await page.screenshot({path:'../.test-artifacts/'+(nativeTest?'native-':'')+'integrated-playback-controls.png'});await writeFile('../.test-artifacts/'+(nativeTest?'native-':'')+'integrated-playback-controls.json',JSON.stringify(result,null,2));console.log(JSON.stringify({nativeTest,styles,initialRequests:loaded,playRequests:playRequests.length,imageRequests:requests.filter(u=>u.includes('/preparation/image')).length,alignmentCount:alignment.length,mismatches:mismatches.length,sidebarResized:Math.abs(resize[0].after.width-resize[0].before.width)>20,mediaResized:Math.abs(afterMedia.width-beforeMedia.width)>20,logsResized:Math.abs(afterLogs.height-beforeLogs.height)>20,tileWidthResized:Math.abs(afterTile.width-beforeTile.width)>20,tileHeightResized:Math.abs(afterTile.height-beforeTile.height)>20,errors}));
 if(mismatches.length||errors.length||!alignment.length||playRequests.length||requests.some(u=>u.includes('/preparation/image'))||Math.abs(afterMedia.width-beforeMedia.width)<20||Math.abs(afterLogs.height-beforeLogs.height)<20||Math.abs(afterTile.width-beforeTile.width)<20||Math.abs(afterTile.height-beforeTile.height)<20)throw Error('Integrated verification failed; inspect evidence');
} finally {await browser.close();}
