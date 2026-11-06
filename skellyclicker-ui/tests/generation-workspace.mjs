// Uses real read-only backend responses in an isolated browser. All job mutations are blocked.
import {chromium,expect,request} from '@playwright/test';
const backend=process.env.SKELLYCLICKER_TEST_BACKEND_URL;if(!backend)throw new Error('Set SKELLYCLICKER_TEST_BACKEND_URL to the running backend.');
const api=await request.newContext();const saved=await(await api.get(backend+'/api/session')).json();
if(!saved.project)throw new Error('Open a project before running the read-only workspace test.');
let session={...saved,state:{...saved.state,workspace:'viewer'}};let labelReads=0,trainingPreviews=0;const mutations=[],errors=[];
const browser=await chromium.launch({channel:'msedge',headless:true});const page=await browser.newPage({viewport:{width:1440,height:960}});
page.on('pageerror',e=>errors.push(String(e)));
const receipt={run_id:'fixture-batch',created_at:Date.now()/1000,snapshot:{status:'complete',operations:[]},source_checkpoint:{run_id:'fixture-parent',path:'epoch-10.pt'},dataset:{count:61,revision:'fixture-receipt'},result:{counts:{candidates:3},proposals:[],scope:'recording'},accepted:{run_id:'fixture-add',snapshot:{status:'complete',operations:[]},receipt:{before_count:58,added_count:3,after_count:61,selection_revision:'fixture-receipt'}}};
await page.routeWebSocket('ws://127.0.0.1:8006/**',()=>{});
await page.route('http://127.0.0.1:8006/**',async route=>{
 const req=route.request(),url=new URL(req.url()),path=url.pathname;
 if(path==='/api/session'){if(req.method()==='PATCH')session={...session,state:{...session.state,...req.postDataJSON()}};await route.fulfill({json:session});return;}
 if(path==='/api/projects/open'){await route.fulfill({json:{...session.project,session_state:session.state}});return;}
 if(path==='/api/refinement/latest'||path.startsWith('/api/refinement/runs/fixture-batch')){await route.fulfill({json:receipt});return;}
 if(path==='/api/labels/selection')labelReads++;
 if(path==='/api/training/preview')trainingPreviews++;
 if(req.method()!=='GET'&&!['/api/training/preview','/api/projects/validate-stl'].includes(path)){mutations.push({path,method:req.method()});await route.fulfill({status:409,json:{detail:'Mutation blocked by read-only workspace test'}});return;}
 const response=await api.fetch(backend+path+url.search,{method:req.method(),data:req.postData()??undefined,headers:req.postData()?{'content-type':'application/json'}:undefined});await route.fulfill({response});
});
try{
 await page.goto('http://127.0.0.1:5176/');
 const tabs=page.getByRole('tablist',{name:'Workspace views'});
 expect(await tabs.getByRole('tab').allTextContents()).toEqual(['Viewer','Generate training data','Training']);
 await expect.poll(()=>labelReads).toBeGreaterThanOrEqual(2); // Receipt refresh without a WebSocket snapshot.
 await page.getByRole('button',{name:'Create image training set',exact:true}).click();
 const generation=page.getByRole('tabpanel',{name:'Generate training data',exact:true});await expect(generation).toBeVisible();
 await expect(page.getByRole('dialog',{name:'Create image training set',exact:true})).toHaveCount(0);
 await expect(page.getByRole('complementary',{name:'Project and training images'})).not.toBeVisible();
 const controlBox=await page.locator('.generation-controls').boundingBox(),galleryBox=await page.locator('.quality-gallery').boundingBox();expect(galleryBox.x).toBeGreaterThan(controlBox.x+controlBox.width-2);
 expect(await generation.locator('[data-image-id]').count()).toBeLessThan(100);
 await expect(generation.getByRole('button',{name:'Generate all images',exact:true})).toBeEnabled();
 await generation.getByRole('tab',{name:'Find more examples',exact:true}).click();
 await expect(generation.getByRole('button',{name:'Go to Training',exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'Start training',exact:true})).not.toBeVisible();
 await page.screenshot({path:'../.test-artifacts/generation-model-workspace.png'});
 await page.reload();await expect(page.getByRole('tab',{name:'Generate training data',exact:true})).toHaveAttribute('aria-selected','true');
 await expect(page.getByRole('tab',{name:'Find more examples',exact:true})).toHaveAttribute('aria-selected','true');
 expect(trainingPreviews).toBe(0);
 await page.getByRole('button',{name:'Go to Training',exact:true}).click();await expect(page.getByRole('tab',{name:'Training',exact:true})).toHaveAttribute('aria-selected','true');await expect.poll(()=>trainingPreviews).toBe(1);
 await expect(page.getByRole('tabpanel',{name:'Training',exact:true}).getByRole('button',{name:'Find next examples',exact:true})).toHaveCount(0);
 await tabs.getByRole('tab',{name:'Generate training data',exact:true}).click();await generation.getByRole('tab',{name:'Recording images',exact:true}).click();
 await expect(generation.getByRole('button',{name:'Generate all images',exact:true})).toBeEnabled();
 await page.screenshot({path:'../.test-artifacts/generation-recording-workspace.png'});
 await expect(tabs.getByRole('tab',{name:'Checkpoint images',exact:true})).toHaveCount(0);
 expect(mutations).toEqual([]);expect(errors).toEqual([]);console.log('PASS dedicated generation tabs, embedded pipeline, model portal, receipt refresh without WebSocket, navigation-only Go to Training, persistence, checkpoints; no job mutations');
}finally{await page.unrouteAll({behavior:'ignoreErrors'});await browser.close();await api.dispose();}
