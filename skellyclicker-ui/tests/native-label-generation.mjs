// Mutating integration journey: explicitly processes the entire current recording.
// Run only when real generation is intended and the native backend is idle.
import {chromium,expect} from '@playwright/test';
import {writeFile} from 'node:fs/promises';
const browser=await chromium.connectOverCDP('http://127.0.0.1:9224');
const evidence={requests:[],errors:[]};
try{
 const page=browser.contexts()[0].pages()[0];
 page.on('pageerror',e=>evidence.errors.push(String(e)));
 page.on('request',r=>{if(r.method()==='POST'&&/api\/(labels|preparation)/.test(r.url()))evidence.requests.push({url:r.url(),body:r.postDataJSON()});});
 const close=page.getByRole('button',{name:'Close Create image training set',exact:true});if(await close.count())await close.click();
 await page.getByRole('button',{name:'Create image training set',exact:true}).click();
 const dialog=page.getByRole('dialog',{name:'Create image training set',exact:true});
 await dialog.getByRole('combobox',{name:'Frames to generate'}).selectOption('all');
 await dialog.getByRole('button',{name:'Generate all images',exact:true}).click();
 await expect(dialog.getByRole('button',{name:'Open generated images',exact:true})).toBeEnabled({timeout:3600000});
 evidence.result=await dialog.getByRole('region',{name:'Run activity',exact:true}).innerText();
 const label=evidence.requests.find(r=>r.url.endsWith('/api/labels/runs'));
 expect(label.body.start_frame).toBe(0);expect(label.body.step).toBe(1);expect(label.body.max_moments).toBe(null);expect(label.body.fit_filter).toBe('all');
 expect(evidence.errors).toEqual([]);await page.screenshot({path:'../.test-artifacts/labels-full-recording-complete.png'});
 await dialog.getByRole('button',{name:'Open generated images',exact:true}).click();
 await writeFile('../.test-artifacts/labels-full-recording.json',JSON.stringify(evidence,null,2));console.log('PASS',JSON.stringify(evidence));
}finally{await browser.close();}
