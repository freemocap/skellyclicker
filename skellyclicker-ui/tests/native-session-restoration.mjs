import {chromium,expect} from '@playwright/test';
import {readFile,writeFile,readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {join} from 'node:path';
const statePath=join(process.env.LOCALAPPDATA,'SkellyClicker','session.json');
const session=JSON.parse(await readFile(statePath,'utf8'));
const project=JSON.parse(await readFile(session.project_path,'utf8'));
const root=join(session.project_path,'..');
const review=join(root,project.active_review,'manifest.json');
const runs=join(root,'recordings',session.recording_id,'skellyclicker','training-runs');
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const evidence={session,projectHash:hash(await readFile(session.project_path)),selectionHash:hash(await readFile(review)),runs:(await readdir(runs)).sort()};
const b=await chromium.connectOverCDP('http://127.0.0.1:9224');
try{
 const p=b.contexts().flatMap(c=>c.pages()).find(p=>p.url().includes('5176'));
 const writes=[];p.on('request',r=>{if(r.method()==='POST'&&/training\/runs$/.test(r.url()))writes.push(r.url());});
 await expect(p.getByRole('button',{name:'Create image training set',exact:true})).toBeVisible({timeout:60000});
 await expect(p.getByRole('tab',{name:session.workspace==='training'?'Training dashboard':'Viewer',exact:true})).toHaveAttribute('aria-selected','true');
 await expect(p.locator('.project-child-recordings button[aria-pressed="true"]')).toContainText(session.recording_id);
 await expect(p.getByLabel('Displayed run',{exact:true})).toHaveValue(session.training_run_id);
 expect(await p.locator('video').evaluateAll(es=>es.every(e=>e.paused))).toBe(true);
 if(process.argv.includes('--after')){
  const before=JSON.parse(await readFile('../.test-artifacts/session-before.json','utf8'));
  expect(evidence).toEqual(before);
  await p.screenshot({path:'../.test-artifacts/session-restored-native.png'});
 }else await writeFile('../.test-artifacts/session-before.json',JSON.stringify(evidence,null,2));
 expect(writes).toEqual([]);
 console.log(JSON.stringify({restored:session,unchangedSelection:evidence.selectionHash,runCount:evidence.runs.length,paused:true}));
}finally{await b.close();}
