import {chromium,expect} from '@playwright/test';
import {writeFile} from 'node:fs/promises';
const browser=await chromium.connectOverCDP('http://127.0.0.1:9224');
try {
 const p=browser.contexts().flatMap(c=>c.pages()).find(p=>p.url().includes('5176'));
 await expect(p.getByRole('button',{name:'Create image training set',exact:true})).toBeEnabled({timeout:60000});
 const old=p.getByRole('button',{name:'Close Configure training',exact:true});if(await old.count())await old.click();
 await p.getByRole('tab',{name:'Training dashboard',exact:true}).click();
 const start=p.getByRole('button',{name:'Configure training',exact:true});await expect(start).toBeEnabled({timeout:30000});
 const style=await start.evaluate(e=>({background:getComputedStyle(e).backgroundColor,height:e.getBoundingClientRect().height,icon:!!e.querySelector('.icon')}));
 expect(style.background).not.toBe('rgba(0, 0, 0, 0)');expect(style.height).toBeGreaterThanOrEqual(44);expect(style.icon).toBe(true);
 expect(await p.locator('#viewer-view').evaluate(e=>getComputedStyle(e).opacity)).toBe('0');
 await p.screenshot({path:'../.test-artifacts/training-dashboard-styled-20261105-v2.png'});
 await start.click();const d=p.getByRole('dialog',{name:'Configure training',exact:true});
 await expect(d.getByRole('button',{name:'Start training',exact:true})).toBeEnabled({timeout:30000});
 await d.getByRole('spinbutton',{name:'Epochs',exact:true}).fill('2');await d.getByRole('spinbutton',{name:'Epochs',exact:true}).press('Tab');
 await d.getByRole('button',{name:'Refresh included images',exact:true}).click();await expect(d.getByRole('button',{name:'Start training',exact:true})).toBeEnabled({timeout:30000});
 await p.screenshot({path:'../.test-artifacts/training-panel-styled-20261105-v2.png'});
 const response=p.waitForResponse(r=>r.url().includes('/api/training/runs')&&r.request().method()==='POST');
 await d.getByRole('button',{name:'Start training',exact:true}).click();const r=await response;const body=await r.json();expect(r.status()).toBe(202);
 await expect(d).toHaveCount(0);await writeFile('../.test-artifacts/training-native-start.json',JSON.stringify({run:body.run_id,style,backend:new URL(r.url()).origin},null,2));
 console.log(JSON.stringify({run:body.run_id,style,backend:new URL(r.url()).origin}));
}finally{await browser.close();}
