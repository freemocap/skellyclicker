import {chromium,expect} from '@playwright/test';
import {mkdir,writeFile} from 'node:fs/promises';
await mkdir('../.test-artifacts/ux-integration',{recursive:true});
const browser=await chromium.connectOverCDP('http://127.0.0.1:9224');
let cdp;
try{
 const page=browser.contexts()[0].pages()[0];page.setDefaultTimeout(20000);const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.reload({waitUntil:'domcontentloaded'});
 const endpoint=await page.evaluate(()=>window.__TAURI_INTERNALS__.invoke('backend_url'));
 const saved=await(await page.request.get(endpoint+'/api/session')).json();const q='?project_path='+encodeURIComponent(saved.project.manifest_path);
 const membership=await(await page.request.get(endpoint+'/api/labels/selection'+q)).json();
 const hide=page.getByRole('button',{name:'Hide project / images',exact:true});if(await hide.count())await hide.click();
 const collapseLogs=page.getByRole('button',{name:'Collapse log panel',exact:true});if(await collapseLogs.count())await collapseLogs.click();
 const tabs=page.getByRole('tablist',{name:'Workspace views'});
 await tabs.getByRole('tab',{name:'Viewer',exact:true}).click();await tabs.getByRole('tab',{name:'Viewer',exact:true}).press('ArrowRight');await expect(tabs.getByRole('tab',{name:'Generate training data',exact:true})).toBeFocused();await tabs.getByRole('tab',{name:'Generate training data',exact:true}).press('ArrowRight');await expect(tabs.getByRole('tab',{name:'Training',exact:true})).toBeFocused();
 await expect(page.locator('.metric-line[d]')).toHaveCount(4);
 await expect(page.locator('#viewer-view')).toHaveCSS('opacity','0');
 await page.screenshot({path:'../.test-artifacts/ux-integration/training.png'});
 await tabs.getByRole('tab',{name:'Training',exact:true}).press('End');await expect(tabs.getByRole('tab',{name:'Checkpoint images',exact:true})).toBeFocused();
 await page.waitForFunction(()=>[...document.querySelectorAll('.training-checkpoint-images img')].length===4&&[...document.querySelectorAll('.training-checkpoint-images img')].every(i=>i.complete&&i.naturalWidth>0));
 await page.screenshot({path:'../.test-artifacts/ux-integration/checkpoints.png'});
 await page.reload({waitUntil:'domcontentloaded'});await expect(tabs.getByRole('tab',{name:'Checkpoint images',exact:true})).toHaveAttribute('aria-selected','true');
 await tabs.getByRole('tab',{name:'Checkpoint images',exact:true}).press('Home');await expect(tabs.getByRole('tab',{name:'Viewer',exact:true})).toBeFocused();
 await page.getByRole('button',{name:'Configure training',exact:true}).click();await expect(page.getByRole('dialog',{name:'Configure training',exact:true})).toBeVisible();await page.getByRole('dialog',{name:'Configure training',exact:true}).press('Escape');
 await page.getByRole('button',{name:'Create image training set',exact:true}).click();await expect(page.getByRole('tabpanel',{name:'Generate training data',exact:true})).toBeVisible();await expect(page.getByRole('dialog',{name:'Create image training set',exact:true})).toHaveCount(0);await tabs.getByRole('tab',{name:'Viewer',exact:true}).click();
 await page.getByRole('button',{name:'Project / images',exact:true}).click();await page.getByRole('button',{name:'Images',exact:true}).click();await expect(page.locator('.sdk-image-card')).toHaveCount(membership.selected_image_ids.length);
 await page.getByRole('button',{name:'Project',exact:true}).click();await expect(page.locator('.project-browser-stack')).toBeVisible();await page.getByRole('button',{name:'Images',exact:true}).click();await page.getByRole('button',{name:'Hide project / images',exact:true}).click();
 const closeLogsAgain=page.getByRole('button',{name:'Collapse log panel',exact:true});if(await closeLogsAgain.count())await closeLogsAgain.click();await page.getByRole('button',{name:'Restore log panel',exact:true}).click();await expect(page.getByRole('button',{name:'Collapse log panel',exact:true})).toBeVisible();await page.getByRole('button',{name:'Collapse log panel',exact:true}).click();
 cdp=await page.context().newCDPSession(page);
 for(const [width,height] of [[1100,800],[720,480]]){
  await cdp.send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false});await tabs.getByRole('tab',{name:'Training',exact:true}).click();await page.waitForTimeout(500);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:`../.test-artifacts/ux-integration/training-${width}.png`});
 }
 await cdp.send('Emulation.clearDeviceMetricsOverride');
 await tabs.getByRole('tab',{name:'Viewer',exact:true}).click();await page.screenshot({path:'../.test-artifacts/ux-integration/viewer.png'});
 expect(await(await page.request.get(endpoint+'/api/labels/selection'+q)).json()).toEqual(membership);expect(errors).toEqual([]);
 await writeFile('../.test-artifacts/ux-integration/workspace.json',JSON.stringify({keyboard:true,checkpointReload:true,dialogs:true,catalogCount:membership.selected_image_ids.length,logs:true,membershipUnchanged:true,errors},null,2));console.log('PASS native tabs/keyboard/reload, dialogs, catalog, logs and constrained widths; membership unchanged');
}finally{if(cdp)await cdp.send('Emulation.clearDeviceMetricsOverride').catch(()=>{});await browser.close();}
