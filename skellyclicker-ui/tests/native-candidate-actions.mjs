import {chromium,expect} from '@playwright/test';
const browser=await chromium.connectOverCDP('http://127.0.0.1:9224');
try{
 const page=browser.contexts()[0].pages()[0];let generations=0;
 page.on('request',r=>{if(r.method()==='POST'&&(/\/api\/labels\/runs$/.test(r.url())||/\/api\/preparation\/start$/.test(r.url())))generations++;});
 for(const tab of ['Training','Viewer']){
  const close=page.getByRole('button',{name:'Close Create image training set',exact:true});if(await close.count())await close.click();
  await page.getByRole('tab',{name:tab,exact:true}).click();await page.getByRole('button',{name:'Create image training set',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Create image training set',exact:true});
  await dialog.getByRole('combobox',{name:'Frames to generate'}).selectOption('all');
  await expect(dialog.getByRole('button',{name:'Generate all images',exact:true})).toBeEnabled({timeout:15000});
  await expect(dialog.getByRole('region',{name:'Image generation',exact:true})).toContainText('Entire recording · every frame · both cameras');
  expect(await dialog.getByRole('button',{name:'Generate all images',exact:true}).evaluate(e=>getComputedStyle(e).backgroundColor)).not.toBe('rgba(0, 0, 0, 0)');
  await dialog.getByRole('button',{name:'Close Create image training set',exact:true}).click();
 }
 expect(generations).toBe(0);console.log('PASS whole-recording default and styled action from Viewer and Training; no processing started');
}finally{await browser.close();}
