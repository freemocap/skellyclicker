import {chromium, expect} from '@playwright/test';
const browser=await chromium.launch({headless:true,channel:'msedge'});
try {
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const errors=[];page.on('pageerror',e=>errors.push(String(e)));
await page.goto('http://127.0.0.1:5176');
await page.getByLabel('Project path').fill('C:/Users/jonma/freemocap_data/skellyclicker_projects/benchy-sfn26');
await page.getByRole('button',{name:'Open project',exact:true}).click();
await expect(page.getByRole('heading',{name:'benchy-sfn26',exact:true})).toBeVisible({timeout:30000});
await expect(page.getByText('Reference: benchy (mm)',{exact:true})).toBeVisible();
await expect(page.getByText('Calibration: awaiting fresh replay',{exact:true})).toBeVisible();
if(errors.length)throw new Error(errors.join('\n'));
await page.screenshot({path:'../.test-artifacts/fresh-project-open.png',fullPage:true});
console.log(JSON.stringify({project:'benchy-sfn26',opened:true,errors}));
} finally {await browser.close();}
