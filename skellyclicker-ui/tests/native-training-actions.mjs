import {chromium,expect} from '@playwright/test';
const b=await chromium.connectOverCDP('http://127.0.0.1:9224');
const p=b.contexts().flatMap(c=>c.pages()).find(p=>p.url().includes('5176'));
let sent;
try{
 await expect(p.getByRole('button',{name:'Create image training set',exact:true})).toBeVisible({timeout:60000});
 await p.getByRole('tab',{name:'Training dashboard',exact:true}).click();
 await expect(p.getByRole('button',{name:'Run pipeline',exact:true})).toHaveCount(0);
 await expect(p.getByRole('button',{name:'Configure training',exact:true})).toHaveCount(1);
 await p.getByRole('button',{name:'Configure training',exact:true}).click();
 const d=p.getByRole('dialog',{name:'Configure training',exact:true});
 await expect(d.getByRole('button',{name:'Start training',exact:true})).toBeEnabled({timeout:30000});
 await expect(d).toContainText('10 epochs');
 await expect(d.locator('button .play-icon')).toHaveCount(1);
 // Exercise the real HTTP endpoint with a deliberately stale preview identity.
 // This must reject before allocating a run or launching a worker.
 await p.route('**/api/training/runs',async route=>{
  if(route.request().method()!=='POST')return route.continue();
  sent=route.request().postDataJSON();
  await route.continue({postData:JSON.stringify({...sent,expected_selection_sha256:'0'.repeat(64)})});
 });
 const response=p.waitForResponse(r=>r.url().endsWith('/api/training/runs')&&r.request().method()==='POST');
 await d.getByRole('button',{name:'Start training',exact:true}).click();
 const result=await response;expect(result.status()).toBe(409);expect(sent.epochs).toBe(10);
 await expect(d.getByRole('alert').first()).toBeVisible();
 console.log(JSON.stringify({configureOpensOnePanel:true,configuredEpochs:sent.epochs,realStartEndpoint:result.status(),noRunStarted:true}));
}finally{await p.unroute('**/api/training/runs');await p.reload();await b.close();}
