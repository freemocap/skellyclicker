import {chromium,expect} from '@playwright/test';
const browser=await chromium.connectOverCDP('http://127.0.0.1:9224');
try{
 const page=browser.contexts()[0].pages()[0];let generations=0;
 page.on('request',r=>{if(r.method()==='POST'&&(/\/api\/labels\/runs$/.test(r.url())||/\/api\/preparation\/start$/.test(r.url())))generations++;});
 for(const tab of ['Training','Viewer']){
  await page.getByRole('tab',{name:tab,exact:true}).click();await page.getByRole('button',{name:'Create image training set',exact:true}).click();
  const dialog=page.getByRole('tabpanel',{name:'Generate training data',exact:true});
  await dialog.getByRole('combobox',{name:'Frames to generate'}).selectOption('all');
  await expect(dialog.getByRole('button',{name:'Generate all images',exact:true})).toBeEnabled({timeout:15000});
  await expect(dialog.getByRole('region',{name:'Image generation',exact:true})).toContainText('Both cameras');
  expect(await dialog.getByRole('button',{name:'Generate all images',exact:true}).evaluate(e=>getComputedStyle(e).backgroundColor)).not.toBe('rgba(0, 0, 0, 0)');
  await page.getByRole('tab',{name:tab,exact:true}).click();
 }
 expect(generations).toBe(0);console.log('PASS whole-recording default and styled action from Viewer and Training; no processing started');
}finally{await browser.close();}
