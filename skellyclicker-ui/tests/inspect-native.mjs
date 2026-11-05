import assert from 'node:assert/strict';
import {chromium, expect} from '@playwright/test';
import {writeFile} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {build} from 'esbuild';

const label=process.env.SKELLYCLICKER_NATIVE_LABEL || 'native-window';
assert.match(label,/^[a-z0-9-]+$/);
const browser = await chromium.connectOverCDP(process.env.SKELLYCLICKER_CDP_URL || 'http://127.0.0.1:9223');
const context = browser.contexts()[0];
const page = context.pages().find(page => !page.url().startsWith('devtools:'));
assert.ok(page, 'Native WebView page exists');
const errors=[];
page.on('pageerror', error=>errors.push(error.stack || String(error)));
await expect(page.getByText('Backend connected',{exact:true})).toBeVisible({timeout:15000});
await expect(page.getByRole('img',{name:'SkellyClicker',exact:true})).toBeVisible();
await expect(page.locator('canvas').first()).toBeVisible();
await expect(page.getByText('Stream updates: 1',{exact:true})).toBeVisible();
assert.equal(await page.getByText('Streaming',{exact:true}).count(),0);
const backendUrl=await page.evaluate(()=>window.__TAURI_INTERNALS__.invoke('backend_url'));
const status=await page.evaluate(async url=>(await fetch(url+'/api/status')).json(),backendUrl);
assert.equal(status.application,'skellyclicker');
assert.notEqual(new URL(backendUrl).port,'53117');

// Inject a test-only bundle of the public SDK API into this actual WebView.
// This checks its decoder in the packaged runtime without adding a product test endpoint.
const fixture=JSON.parse(execFileSync('../backend/.venv/Scripts/python.exe',['-B','../backend/tests/image_fixture.py'],{encoding:'utf8'}));
const probe=await build({stdin:{contents:`
import {decodeMessage,readImagePayload,decodeJpegRgba} from '@freemocap/client';
globalThis.__skellyclickerImageProbe=async base64=>{
 const message=decodeMessage(Uint8Array.from(atob(base64),c=>c.charCodeAt(0)));
 const payload=readImagePayload(message.image);
 const image=payload.images[0];
 const pixels=await decodeJpegRgba(image.jpeg);
 return {frameNumber:payload.frameNumber,cameraId:image.cameraId,width:pixels.width,height:pixels.height,pixelBytes:pixels.pixelBuffer.byteLength,jpeg:Array.from(image.jpeg)};
};`,resolveDir:process.cwd(),sourcefile:'native-image-probe.js'},bundle:true,write:false,platform:'browser',format:'iife'});
await page.evaluate(probe.outputFiles[0].text);
const imageResult=await page.evaluate(frame=>globalThis.__skellyclickerImageProbe(frame),fixture.frame);
assert.deepEqual(Buffer.from(imageResult.jpeg),Buffer.from(fixture.jpeg,'base64'));
assert.deepEqual({...imageResult,jpeg:undefined},{frameNumber:7,cameraId:'fixture',width:16,height:12,pixelBytes:768,jpeg:undefined});
delete imageResult.jpeg;
await page.screenshot({path:`../.test-artifacts/${label}.png`});
const result={url:page.url(),backendUrl,status,imageResult,errors,body:await page.locator('body').innerText()};
await writeFile(`../.test-artifacts/${label}.json`,JSON.stringify(result,null,2));
console.log(JSON.stringify(result,null,2));
assert.deepEqual(errors,[]);
await browser.close();
