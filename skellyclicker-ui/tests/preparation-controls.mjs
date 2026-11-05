import {chromium,expect} from '@playwright/test';
const native=await chromium.connectOverCDP('http://127.0.0.1:9224');
const nativePage=native.contexts()[0].pages().find(p=>!p.url().startsWith('devtools:'));
const endpoint=await nativePage.evaluate(()=>window.__TAURI_INTERNALS__.invoke('backend_url'));
const path=await nativePage.evaluate(()=>localStorage.getItem('skellyclicker.projectPath'));
await native.close();
const browser=await chromium.launch({channel:'msedge',headless:true});
try {
 const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(({endpoint,path})=>{globalThis.isTauri=true;window.__TAURI_INTERNALS__={invoke:async cmd=>{if(cmd==='backend_url')return endpoint;throw new Error(cmd);}};localStorage.setItem('skellyclicker.projectPath',path);},{endpoint,path});
 await page.goto('http://127.0.0.1:5176');
 await expect(page.getByRole('button',{name:'Play samples',exact:true})).toBeVisible();
 await page.getByLabel('Sample frame',{exact:true}).fill('14');
 await expect(page.locator('.sample-images')).toBeVisible();
 await expect(page.locator('.sample-images img').first()).toHaveAttribute('alt','left-candidate, source frame 14');
 await page.getByLabel('Sample view',{exact:true}).selectOption('depth');
 await expect(page.locator('.sample-images img').first()).toHaveAttribute('alt','depth, source frame 14');
 await page.waitForFunction(()=>[...document.querySelectorAll('.sample-images img')].every(i=>i.complete&&i.naturalWidth===1280));
 await page.route('**/api/preparation/start',route=>route.fulfill({json:{job_id:'ui-test',state:'queued',stage:'queued',completed:0,total:30}}));
 await page.route('**/api/preparation/status/ui-test',route=>route.fulfill({json:{job_id:'ui-test',state:'complete',stage:'complete',completed:30,total:30,accepted:14}}));
 await page.getByRole('button',{name:'Prepare fresh samples',exact:true}).click();
 await expect(page.getByText('complete · complete',{exact:true})).toBeVisible();
 await expect(page.getByLabel('Sample frame',{exact:true})).toHaveValue('0');
 await expect(page.locator('.sample-images img').first()).toHaveAttribute('alt','depth, source frame 0');
 if(errors.length)throw new Error(errors.join('\n'));
 console.log('PASS: separate browser reopens real result, selects frame/view, decodes depth+mask, and loads result after terminal job state without generating data');
} finally {await browser.close();}

