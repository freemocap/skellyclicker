// Real source data, isolated browser. Only read-only quality/STL validation POSTs are forwarded.
import {chromium,expect,request} from '@playwright/test';
const backend=process.env.SKELLYCLICKER_TEST_BACKEND_URL;if(!backend)throw new Error('Set read-only verification backend URL');
const api=await request.newContext();const saved=await(await api.get(backend+'/api/session')).json();if(!saved.project)throw new Error('Open a project first');
const projectPath=saved.project.manifest_path,q=encodeURIComponent(projectPath);const before=await(await api.get(backend+'/api/labels/selection?project_path='+q)).json();
let session={...saved,state:{...saved.state,workspace:'training'}},quality;let previewRequests=0,meshRequests=0;const writes=[],errors=[];
const browser=await chromium.launch({channel:'msedge',headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000}});page.on('pageerror',e=>errors.push(String(e)));
await page.addInitScript(()=>{localStorage.setItem('skellyclicker.results-view','generation');localStorage.setItem('skellyclicker.generation-view','selection');});
await page.routeWebSocket('ws://127.0.0.1:8006/**',()=>{});
await page.route('http://127.0.0.1:8006/**',async route=>{
 const req=route.request(),url=new URL(req.url()),path=url.pathname;
 if(path==='/api/session'){if(req.method()==='PATCH')session={...session,state:{...session.state,...req.postDataJSON()}};await route.fulfill({json:session});return;}
 if(path==='/api/projects/open'){await route.fulfill({json:{...session.project,session_state:session.state}});return;}
 if(req.method()!=='GET'&&!['/api/labels/quality/preview','/api/projects/validate-stl'].includes(path)){writes.push(path);await route.fulfill({status:409,json:{detail:'Mutation blocked in verification'}});return;}
 if(path==='/api/labels/quality/preview')previewRequests++;if(path==='/api/labels/quality/stl')meshRequests++;
 const response=await route.fetch({url:backend+path+url.search,timeout:120000});if(path==='/api/labels/quality/preview')quality=await response.json();await route.fulfill({response});
});
try{
 await page.goto('http://127.0.0.1:5176/');await expect(page.getByRole('button',{name:'Preview best 100',exact:true})).toBeEnabled();
 await page.getByRole('button',{name:'Preview best 100',exact:true}).click();await expect(page.getByRole('button',{name:'Apply: keep 100 images',exact:true})).toBeEnabled({timeout:120000});
 await expect(page.locator('.coverage-visuals canvas')).toBeVisible();await expect(page.getByText('Loading STL…',{exact:true})).toHaveCount(0,{timeout:30000});
 expect(quality.policy.selection_mode).toBe('quality_viewpoints');expect(quality.image_ids).toHaveLength(100);expect(quality.coverage.pools.proposed.known_count).toBe(100);
 const box=await page.locator('.generation-controls').boundingBox(),gallery=await page.locator('.quality-gallery').boundingBox();expect(gallery.x).toBeGreaterThan(box.x+box.width-2);expect(await page.locator('.quality-gallery [data-image-id]').count()).toBeLessThan(100);
 const histogramBefore=await page.locator('.coverage-histogram path').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('d')).join(''));const chartLabels=await page.locator('.coverage-histogram svg').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('aria-label')));const canvas=await page.locator('.coverage-visuals canvas').boundingBox();await page.mouse.move(canvas.x+canvas.width*.4,canvas.y+canvas.height*.4);await page.mouse.down();await page.mouse.move(canvas.x+canvas.width*.8,canvas.y+canvas.height*.6,{steps:10});await page.mouse.up();await expect.poll(async()=>page.locator('.coverage-histogram path').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('d')).join(''))).not.toBe(histogramBefore);expect(await page.locator('.coverage-histogram svg').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('aria-label')))).toEqual(chartLabels);
 await page.screenshot({path:'../.test-artifacts/quality-real-preview.png'});
 await page.getByRole('tab',{name:'Current',exact:true}).click();await expect(page.locator('.coverage-counts')).toContainText(String(before.selected_image_ids.length)+' images');
 await page.getByRole('tab',{name:'Proposed',exact:true}).click();
 const after=await(await api.get(backend+'/api/labels/selection?project_path='+q)).json();expect(after).toEqual(before);expect(writes).toEqual([]);expect(previewRequests).toBe(1);expect(meshRequests).toBe(1);expect(errors).toEqual([]);
 console.log(JSON.stringify({pass:true,membersUnchanged:before.selected_image_ids.length,chosen:quality.image_ids.length,eligible:quality.counts.eligible,viewpointUnknown:quality.counts.viewpoint_unknown,proposedCells:quality.coverage.pools.proposed.occupied_bins,totalCells:quality.coverage.azimuth_bins*quality.coverage.z_bins,mountedCards:await page.locator('.quality-gallery [data-image-id]').count()}));
}finally{await page.unrouteAll({behavior:'ignoreErrors'});await browser.close();await api.dispose();}
