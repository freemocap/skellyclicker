import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {chromium} from '@playwright/test';
import {decodeMessage, readImagePayload} from '@freemocap/client';
const fixture=JSON.parse(execFileSync('../backend/.venv/Scripts/python.exe',['-B','../backend/tests/image_fixture.py'],{encoding:'utf8'}));
const message=decodeMessage(Buffer.from(fixture.frame,'base64'));
assert.equal(message.kind,'frame');
const payload=readImagePayload(message.image);
assert.equal(payload.frameNumber,7);
assert.equal(payload.images.length,1);
const image=payload.images[0];
assert.deepEqual([image.cameraId,image.width,image.height],['fixture',16,12]);
assert.deepEqual(Buffer.from(image.jpeg),Buffer.from(fixture.jpeg,'base64'));
const browser=await chromium.launch({headless:true,channel:process.env.SKELLYCLICKER_BROWSER_CHANNEL || 'msedge'});
try {
 const page=await browser.newPage();
 await page.goto('http://127.0.0.1:5176');
 const result=await page.evaluate(async bytes=>{
  const {decodeJpegRgba}=await import('/tests/image-decoder.ts');
  const decoded=await decodeJpegRgba(new Uint8Array(bytes));
  return {width:decoded.width,height:decoded.height,pixelBytes:decoded.pixelBuffer.byteLength};
 },Array.from(image.jpeg));
 assert.deepEqual(result,{width:16,height:12,pixelBytes:768});
 console.log('PASS: Python SDK CBOR/image packing -> JS SDK decoding -> browser SDK JPEG pixels; bytes and metadata preserved');
} finally {await browser.close();}
