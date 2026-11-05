import {chromium, expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
const browser=await chromium.connectOverCDP('http://127.0.0.1:9224');
const page=browser.contexts()[0].pages().find(p=>!p.url().startsWith('devtools:'));
const errors=[];page.on('pageerror',e=>errors.push(String(e)));
await expect(page.getByText('Backend connected',{exact:true})).toBeVisible();
await page.getByRole('button',{name:'Open project',exact:true}).click();
await page.getByLabel('Project path').fill('C:/Users/jonma/freemocap_data/skellyclicker_projects/benchy-sfn26');
await page.getByRole('button',{name:'Open',exact:true}).click();
await expect(page.getByText('benchy-sfn26',{exact:true}).first()).toBeVisible({timeout:30000});
const token='hmr-'+Date.now();
await page.evaluate(t=>{window.__hmrProbe=t;},token);
const cssPath='src/shell.css';const css=await readFile(cssPath,'utf8');
try {
 await writeFile(cssPath,css+'\n:root {--skelly-hmr-probe: live;}\n');
 await expect.poll(()=>page.evaluate(()=>getComputedStyle(document.documentElement).getPropertyValue('--skelly-hmr-probe').trim())).toBe('live');
 if(await page.evaluate(()=>window.__hmrProbe)!==token) throw new Error('WebView reloaded instead of HMR');
} finally {await writeFile(cssPath,css);}
await expect.poll(()=>page.evaluate(()=>getComputedStyle(document.documentElement).getPropertyValue('--skelly-hmr-probe').trim())).toBe('');
const backendUrl=await page.evaluate(()=>window.__TAURI_INTERNALS__.invoke('backend_url'));
const report={url:page.url(),backendUrl,project:'benchy-sfn26',native:true,frontendHmr:true,backendHmr:false,errors};
await page.screenshot({path:'../.test-artifacts/native-project-review.png'});
await writeFile('../.test-artifacts/native-project-review.json',JSON.stringify(report,null,2));
console.log(JSON.stringify(report));
if(errors.length)throw new Error(errors.join('\n'));
await browser.close();

