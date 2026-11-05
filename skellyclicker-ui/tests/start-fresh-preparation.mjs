import {chromium,expect} from '@playwright/test';
const browser=await chromium.connectOverCDP('http://127.0.0.1:9224');
try {
 const page=browser.contexts()[0].pages().find(p=>!p.url().startsWith('devtools:'));
 await expect(page.getByRole('button',{name:'Prepare fresh samples',exact:true})).toBeVisible({timeout:15000});
 console.log('Backend: '+await page.evaluate(()=>window.__TAURI_INTERNALS__.invoke('backend_url')));
 await page.getByRole('button',{name:'Prepare fresh samples',exact:true}).click();
 await expect(page.getByRole('button',{name:'Cancel preparation',exact:true})).toBeVisible({timeout:30000});
 console.log(await page.locator('.sample-preparation').innerText());
} finally {await browser.close();}
