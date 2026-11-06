import {chromium,expect} from '@playwright/test';
const b=await chromium.connectOverCDP('http://127.0.0.1:9224');
try{
 const p=b.contexts()[0].pages()[0];let generations=0;p.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/api/labels/runs'))generations++;});
 for(const tab of ['Training dashboard','Viewer']){
  const close=p.getByRole('button',{name:'Close Create image training set',exact:true});if(await close.count())await close.click();
  await p.getByRole('tab',{name:tab,exact:true}).click();await p.getByRole('button',{name:'Create image training set',exact:true}).click();
  const d=p.getByRole('dialog',{name:'Create image training set',exact:true});await d.getByRole('button',{name:'List',exact:true}).click();
  await d.getByRole('combobox',{name:'Input strategy',exact:true}).selectOption('fresh');
  await expect(d.locator('.training-set-action-status')).toContainText('Fresh preparation is not connected');
  await expect(d.getByRole('button',{name:'Preview candidates',exact:true})).toBeDisabled();
  await d.getByRole('button',{name:'Use prepared frames',exact:true}).click();
  await d.getByRole('button',{name:'Preview candidates',exact:true}).click();
  await expect(d.getByRole('button',{name:'Generate candidates',exact:true})).toBeEnabled({timeout:15000});
  await d.getByRole('button',{name:'Close Create image training set',exact:true}).click();
 }
 expect(generations).toBe(0);await p.getByRole('tab',{name:'Training dashboard',exact:true}).click();
 console.log('PASS interactive candidate dialog and explicit blockers from both tabs; no generation');
}finally{await b.close();}
