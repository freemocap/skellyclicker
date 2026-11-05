import {chromium,expect} from '@playwright/test';
import {writeFile} from 'node:fs/promises';
const browser=await chromium.connectOverCDP('http://127.0.0.1:9224');
try {
 const page=browser.contexts()[0].pages().find(p=>!p.url().startsWith('devtools:'));
 await expect(page.getByRole('button',{name:'Play samples',exact:true})).toBeVisible({timeout:15000});
 await expect(page.locator('.sample-images img')).toHaveCount(2);
 await page.waitForFunction(()=>[...document.querySelectorAll('.sample-images img')].every(i=>i.complete&&i.naturalWidth===1280));
 const evidence={backendUrl:await page.evaluate(()=>window.__TAURI_INTERNALS__.invoke('backend_url')),text:await page.locator('.sample-preparation').innerText(),images:await page.locator('.sample-images img').evaluateAll(imgs=>imgs.map(i=>({src:i.src,width:i.naturalWidth,height:i.naturalHeight})))};
 await page.screenshot({path:'../.test-artifacts/native-fresh-samples.png'});
 await writeFile('../.test-artifacts/native-fresh-samples.json',JSON.stringify(evidence,null,2));
 console.log(JSON.stringify(evidence));
} finally {await browser.close();}
