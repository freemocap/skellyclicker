import assert from 'node:assert/strict';
import {basename, resolve} from 'node:path';
import {chromium, expect} from '@playwright/test';

// Attach to a test-owned native WebView with the real packaged backend.
const folder = resolve(process.argv[2]);
const browser = await chromium.connectOverCDP(process.env.SKELLYCLICKER_CDP_URL);
try {
  const [page] = browser.contexts()[0].pages();
  const open = page.getByRole('button', {name: 'Open recording or project', exact: true});
  if (!await open.isVisible()) await page.getByRole('button', {name: 'Labels / project', exact: true}).click();
  await open.click();
  if (!process.argv.includes('--native-picker')) {
    // Only supply the OS selection. All application requests and video decoding are real.
    await page.evaluate(selected => {
      const ipc = window.__TAURI_INTERNALS__;
      const invoke = ipc.invoke.bind(ipc);
      ipc.invoke = (command, args, ...rest) => {
        if (command === 'plugin:dialog|open') {
          ipc.invoke = invoke;
          if (!args.options.directory) throw Error('Expected a directory chooser');
          return Promise.resolve(selected);
        }
        return invoke(command, args, ...rest);
      };
    }, folder);
  }
  await page.getByRole('button', {name: 'Browse folders'}).click();
  await expect(page.locator('.clicker-header')).toContainText(basename(folder), {timeout: 180000});
  await expect(page.getByRole('region', {name: 'Define points'}).or(page.getByRole('region', {name: 'Points'}))).toBeVisible();
  const videos = page.locator('#viewer-view video');
  await expect(videos).toHaveCount(3);
  await expect.poll(async () => videos.evaluateAll(elements => elements.every(video => video.readyState >= 2 && video.videoWidth > 0)),
                    {timeout: 45000}).toBe(true);
  const sizes = await videos.evaluateAll(elements => elements.map(video => [video.videoWidth, video.videoHeight]));
  assert.equal(sizes.length, 3);
  console.log('Opened', basename(folder), 'in the native labeling workspace. Decoded camera sizes:', sizes);
} finally {
  await browser.close();
}
