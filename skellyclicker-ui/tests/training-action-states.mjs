import {chromium,expect} from '@playwright/test';
import {writeFile} from 'node:fs/promises';
const native=await chromium.connectOverCDP('http://127.0.0.1:9224');const nativePage=native.contexts()[0].pages()[0];const backend=await nativePage.evaluate(()=>window.__TAURI_INTERNALS__.invoke('backend_url'));const config=await(await nativePage.request.get(backend+'/api/training/configuration')).json();await native.close();
const browser=await chromium.launch({channel:'msedge',headless:true});const page=await browser.newPage({viewport:{width:1440,height:960}});
const fixture={project:{manifest_path:'/fixture/project.json',root:'/fixture',project:{project_id:'State verification',uuid:'fixture'},recordings:[],targets:[],issues:[],sample_state:'prepared',playback:null}};
let starts=0,previews=0,cancels=0,payload;const errors=[];page.on('pageerror',e=>errors.push(String(e)));
const make=(status,stage,detail='',completed=null,total=null)=>({run_id:'fixture-run',sequence:Math.random()*10000,status,cancel_requested:false,graph:config.graph,operations:['freeze_inputs','prepare_trainer','train_model','publish_run'].map(operation_id=>({operation_id,label:operation_id,status:operation_id===stage?'running':'waiting',detail:operation_id===stage?detail:'',completed:operation_id===stage?completed:null,total:operation_id===stage?total:null,unit:operation_id===stage&&total?'epochs':null,dependencies:[],waiting_for:[],blocked_by:[],files_read:[],files_written:[],items:[],elapsed_seconds:0,progress_fraction:null,effects:[],stage:null})),metrics:[],previews:[],elapsed_seconds:12,error:null});
const prepared=make('running','prepare_trainer','Preparing official DLC project');
await page.addInitScript(fixture=>{window.fixture=fixture;},fixture);
await page.route('http://training-fixture.invalid/**',async route=>{
 const url=new URL(route.request().url());let value;
 if(url.pathname.endsWith('/checkpoints'))value={checkpoints:[],recommended_path:null,recommendation:'No checkpoints'};
 else if(url.pathname==='/api/refinement/latest')value=null;
 else if(url.pathname.endsWith('/configuration'))value=config;
 else if(url.pathname.endsWith('/preview')){previews++;value={image_count:31,keypoint_count:52,counts:{training:22,validation:8,guard:1},expected_selection_sha256:'fresh-'+previews,expected_label_manifest_sha256:'labels'};}
 else if(url.pathname.endsWith('/runs')&&route.request().method()==='POST'){starts++;payload=route.request().postDataJSON();await new Promise(r=>setTimeout(r,700));value={run_id:'fixture-run',snapshot:prepared};}
 else if(url.pathname.endsWith('/cancel')){cancels++;value={};}
 else if(url.pathname.endsWith('/artifact'))value=payload??config.defaults;
 else if(url.pathname.endsWith('/runs'))value=[];
 else value=prepared;
 await route.fulfill({json:value});
});
await page.route('**/__training-actions-test',async route=>{const original=await route.fetch({url:'http://127.0.0.1:5176/'});await route.fulfill({response:original,body:(await original.text()).replace('/src/main.tsx','/tests/training-actions-harness.tsx')});});
try{
 await page.goto('http://127.0.0.1:5176/__training-actions-test');
 const group=page.locator('.training-dashboard > .sdk-workspace-toolbar .training-command-group');
 const names=['Configure training','Start training','Cancel training'];
 const positions=async()=>group.locator('button').evaluateAll(es=>es.map(e=>({name:e.innerText,x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y,w:e.getBoundingClientRect().width,h:e.getBoundingClientRect().height})));
 await expect(group.getByRole('button',{name:'Start training',exact:true})).toBeEnabled();
 await expect.poll(()=>previews).toBeGreaterThan(0);const initial=await positions();
 await group.getByRole('button',{name:'Configure training',exact:true}).click();const d=page.getByRole('dialog',{name:'Configure training',exact:true});
 expect(await d.locator('.training-command-group button').allTextContents()).toEqual(names);
 await d.getByRole('spinbutton',{name:'Epochs',exact:true}).fill('12');await d.getByRole('spinbutton',{name:'Epochs',exact:true}).press('Tab');await expect(d).toContainText('12 epochs');
 await d.getByRole('button',{name:'Close Configure training',exact:true}).click();await group.getByRole('button',{name:'Configure training',exact:true}).click();await expect(d.getByRole('spinbutton',{name:'Epochs',exact:true})).toHaveValue('12');await d.getByRole('button',{name:'Close Configure training',exact:true}).click();
 const previewsBefore=previews;await page.evaluate(()=>window.setSelectionRevision('two'));await expect.poll(()=>previews).toBeGreaterThan(previewsBefore);
 await group.getByRole('button',{name:'Start training',exact:true}).click();await expect(page.locator('.training-dashboard > .run-summary')).toContainText('Starting');await expect(group.getByRole('button',{name:'Start training',exact:true})).toBeDisabled();
 await group.getByRole('button',{name:'Start training',exact:true}).evaluate(e=>e.click());
 expect(await positions()).toEqual(initial);await expect(page.locator('.training-dashboard > .run-summary')).toContainText('Preparing DeepLabCut');expect(starts).toBe(1);expect(payload.epochs).toBe(12);expect(payload.expected_selection_sha256).toMatch(/^fresh-/);
 const states=[['running',make('running','train_model','Training',2,12),'Training'],['evaluating',make('running','train_model','Evaluation',2,12),'Evaluating'],['saving',make('running','publish_run','Saving'),'Saving results']];
 for(const [name,state,label] of states){await page.evaluate(v=>window.setTrainingSnapshot(v),state);await expect(page.locator('.training-dashboard > .run-summary')).toContainText(label);expect(await positions()).toEqual(initial);await page.screenshot({path:'../.test-artifacts/training-actions-'+name+'-fixture.png'});}
 await page.evaluate(v=>window.setTrainingSnapshot(v),make('running','train_model','Training',3,12));await group.getByRole('button',{name:'Cancel training',exact:true}).click();await expect(page.locator('.training-dashboard > .run-summary')).toContainText('Cancelling');expect(cancels).toBe(1);expect(await positions()).toEqual(initial);
 await page.clock.install();await page.clock.fastForward(31000);await expect(page.locator('.training-dashboard > .run-summary')).toContainText('No update for');expect(await page.locator('.training-dashboard > .run-summary .sdk-run-indicator').evaluate(e=>getComputedStyle(e).animationName)).toBe('none');
 await page.evaluate(v=>window.setTrainingSnapshot(v),make('running','train_model','Training',4,12));await expect(page.locator('.training-dashboard > .run-summary')).toContainText('Last update');await page.emulateMedia({reducedMotion:'reduce'});expect(await page.locator('.training-dashboard > .run-summary .sdk-run-indicator').evaluate(e=>getComputedStyle(e).animationName)).toBe('none');
 for(const [terminal,label] of [['failed','Failed'],['cancelled','Cancelled']]){await page.evaluate(v=>window.setTrainingSnapshot(v),make(terminal,null));await expect(page.locator('.training-dashboard > .run-summary')).toContainText(label);await expect(group.getByRole('button',{name:'Start training',exact:true})).toBeEnabled();}
 await page.evaluate(v=>window.setTrainingSnapshot(v),make('complete',null));await expect(page.locator('.training-dashboard > .run-summary')).toContainText('Finished');await expect(group.getByRole('button',{name:'Start training',exact:true})).toBeEnabled();expect(await positions()).toEqual(initial);
 expect(errors).toEqual([]);await writeFile('../.test-artifacts/training-action-states.json',JSON.stringify({states:['idle','starting','preparing','running','evaluating','saving','cancelling','finished'],positions:initial,starts,cancels,configuredEpochs:payload.epochs,previewRequests:previews,errors},null,2));console.log('PASS stable shared actions, config retention, fresh preview, duplicate guard and all lifecycle stages; isolated fixture only');
}catch(e){console.log({errors,body:(await page.locator('body').innerText()).slice(0,500)});throw e;}finally{await browser.close();}
