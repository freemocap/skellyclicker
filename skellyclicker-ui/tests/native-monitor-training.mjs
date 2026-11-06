import {chromium,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
const {run,backend}=JSON.parse(await readFile('../.test-artifacts/training-native-start.json','utf8'));
const project='C:/Users/jonma/freemocap_data/skellyclicker_projects/benchy-sfn26/benchy-sfn26_project.json';
const b=await chromium.connectOverCDP('http://127.0.0.1:9224');
try {
 const p=b.contexts().flatMap(c=>c.pages()).find(p=>p.url().includes('5176'));
 await p.getByRole('tab',{name:'Training dashboard',exact:true}).click();
 const hide=p.getByRole('button',{name:'Collapse log panel',exact:true});if(await hide.count())await hide.click();
 let last='';let state;
 for(let i=0;i<180;i++){
  const response=await p.request.get(backend+'/api/training/runs/'+run+'?project_path='+encodeURIComponent(project));state=await response.json();
  const summary=JSON.stringify({status:state.status,metrics:state.metrics?.map(m=>({id:m.id,points:m.points.length,last:m.points.at(-1)})),previews:state.previews?.length,error:state.error});if(summary!==last){console.log(summary);last=summary;}
  if(state.status==='failed')throw new Error(state.error);
  if(state.metrics?.length&&state.previews?.length)break;
  await p.waitForTimeout(2000);
 }
 expect(state.metrics.length).toBeGreaterThanOrEqual(2);expect(state.previews.length).toBeGreaterThan(0);
 await expect(p.locator('.sdk-metric-card').first()).toBeVisible({timeout:10000});
 await expect(p.locator('.sdk-sample-image img').first()).toBeVisible({timeout:10000});
 await p.screenshot({path:'../.test-artifacts/training-first-real-metrics-20261105.png'});
 await writeFile('../.test-artifacts/training-first-real-metrics.json',JSON.stringify(state,null,2));
 console.log('Real training metrics and checkpoint previews visible');
} finally{await b.close();}
