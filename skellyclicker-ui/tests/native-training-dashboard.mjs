import {chromium,expect} from '@playwright/test';
import {writeFile} from 'node:fs/promises';
const browser=await chromium.connectOverCDP('http://127.0.0.1:9224');
try {
 const page=browser.contexts().flatMap(c=>c.pages()).find(p=>p.url().includes('5176'));
 await expect(page.getByRole('button',{name:'Create image training set',exact:true})).toBeEnabled({timeout:60000});
 await page.getByRole('tab',{name:'Viewer',exact:true}).click();
 const before=await page.locator('#viewer-view video').count();
 await page.getByRole('tab',{name:'Training dashboard',exact:true}).click();
 await expect(page.getByRole('button',{name:'Configure training',exact:true})).toBeEnabled({timeout:30000});
 await page.getByRole('button',{name:'Configure training',exact:true}).click();
 const dialog=page.getByRole('dialog',{name:'Configure training',exact:true});
 await expect(dialog.locator('.pg-node')).toHaveCount(4,{timeout:30000});
 await expect(dialog.getByRole('button',{name:'Start training',exact:true})).toBeEnabled({timeout:30000});
 await expect(dialog.getByRole('alert')).toHaveCount(0);
 const countText=await dialog.innerText();expect(countText).toContain('31 images');
 await page.screenshot({path:'../.test-artifacts/training-configuration-20261105-v1.png'});
 await dialog.getByRole('button',{name:'Close Configure training',exact:true}).click();
 await expect(page.locator('#viewer-view video')).toHaveCount(before);
 await page.getByRole('tab',{name:'Viewer',exact:true}).click();
 await expect(page.locator('#viewer-view')).toBeVisible();
 await page.getByRole('tab',{name:'Training dashboard',exact:true}).click();
 await writeFile('../.test-artifacts/training-dashboard-ui.json',JSON.stringify({fourStages:true,preview31:true,viewerVideoCountPreserved:before,trainingStarted:false}));
 console.log('Training UI: four stages, real 31-image preview, Viewer DOM retained; no training started');
} finally {await browser.close();}
