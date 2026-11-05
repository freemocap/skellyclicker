import {chromium} from '@playwright/test';
import {writeFile} from 'node:fs/promises';
const browser=await chromium.connectOverCDP('http://127.0.0.1:9224');
try {const page=browser.contexts()[0].pages().find(p=>!p.url().startsWith('devtools:'));
const evidence={backend:await page.evaluate(()=>window.__TAURI_INTERNALS__.invoke('backend_url')),body:await page.locator('body').innerText(),videos:await page.locator('video').evaluateAll(vs=>vs.map(v=>({src:v.src,width:v.videoWidth,height:v.videoHeight,readyState:v.readyState,time:v.currentTime,error:v.error?.message}))),canvases:await page.locator('canvas').count(),handles:await page.locator('[data-panel-resize-handle-id]').count()};
await page.screenshot({path:'../.test-artifacts/native-integrated-playback.png'});await writeFile('../.test-artifacts/native-integrated-playback.json',JSON.stringify(evidence,null,2));console.log(JSON.stringify(evidence));} finally{await browser.close();}
