import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {basename, join, resolve} from 'node:path';
import {chromium, expect} from '@playwright/test';

// Run against the desktop dev server and its packaged backend, in an isolated browser context.
const [uiUrl, backendUrl, recording] = process.argv.slice(2);
assert.ok(uiUrl && backendUrl && recording, 'Expected UI URL, backend URL, and three-camera reference recording path');
const output = resolve('.test-artifacts/calibrated-viewport');
await mkdir(output, {recursive:true});
const browser = await chromium.launch({channel:'msedge', headless:true});
try {
  const page = await browser.newPage({viewport:{width:1600,height:1000}});
  // Preserve the reference recording's annotations and last presented frame.
  await page.route(/\/api\/labels(?:\?|$)/, route => {
    const request = route.request();
    if (request.method() === 'GET') return route.fulfill({json:{document:null}});
    if (request.method() === 'PUT') return route.fulfill({json:{document:request.postDataJSON().document}});
    return route.continue();
  });
  page.on('pageerror', error => console.error(error.message));
  await page.addInitScript(({backendUrl, recording}) => {
    window.isTauri = true;
    window.__TAURI_INTERNALS__ = {invoke: async command => {
      if (command === 'backend_url') return backendUrl;
      if (command === 'plugin:dialog|open') return recording;
      throw Error(command);
    }};
    const post = Worker.prototype.postMessage;
    Worker.prototype.postMessage = function(message, ...args) {
      if (message.type === 'calibrationScene') {
        window.rigCameras = message.data.calibration?.cameras;
      }
      if (message.type === 'init') this.addEventListener('message', event => {
        if (event.data.type === 'stats') window.renderedCameraCount = event.data.data.cameras;
      });
      return post.call(this, message, ...args);
    };
  }, {backendUrl,recording});
  await page.goto(uiUrl);
  await page.getByRole('button', {name:'Open folder…'}).click();
  await expect(page.locator('.clicker-header')).toContainText(basename(recording));
  await expect.poll(() => page.evaluate(() => window.renderedCameraCount), {timeout:30000}).toBe(3);
  const cameras = await page.evaluate(() => window.rigCameras);
  assert.deepEqual(cameras.map(camera => camera.id).sort(), ['Cam1','Cam2','Cam3']);
  await expect(page.locator('.playback-presented-image[data-presented-frame]')).toHaveCount(3);
  const pointHelp = page.getByRole('button', {name:'Point names',exact:true});
  const instruction = page.getByText('Enter one point per line in the order you want to label them.');
  await expect(instruction).toBeHidden();
  await pointHelp.hover();
  await expect(instruction).toBeVisible();
  await page.mouse.move(0,0);
  await expect(instruction).toBeHidden();
  const canvas = page.locator('canvas[class~="3d-viewport"]');
  await canvas.screenshot({path:join(output,'cameras.png')});
  await page.screenshot({path:join(output,'workspace.png')});
  console.log(cameras.map(({id,world_position}) => ({id,world_position})));
} finally {
  await browser.close();
}
