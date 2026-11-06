import {chromium,expect} from '@playwright/test';
import {writeFile} from 'node:fs/promises';
const b=await chromium.connectOverCDP('http://127.0.0.1:9224');
try {
 const p=b.contexts().flatMap(c=>c.pages()).find(p=>p.url().includes('5176'));
 await expect(p.getByRole('button',{name:'Create image training set',exact:true})).toBeEnabled({timeout:30000});
 await p.getByRole('button',{name:'Create image training set',exact:true}).click();
 const d=p.getByRole('dialog',{name:'Create image training set',exact:true});
 await expect(d.locator('.pg-node')).toHaveCount(7,{timeout:15000});
 const path=await d.locator('[aria-label="STL target path"]').innerText();
 expect(path.replaceAll('\\','/')).toContain('/recordings/benchy-20261104-232220-208509/skellyclicker/inputs/targets/benchy/r002/benchy.stl');
 await expect(d.getByRole('alert')).toHaveCount(0);
 const routing=await d.evaluate(root=>{
  const cards=[...root.querySelectorAll('.pg-node')].map(e=>({id:e.dataset.stageId,r:e.getBoundingClientRect()}));
  const violations=[];const wires=[...root.querySelectorAll('.pg-wire')];
  wires.forEach((wire,index)=>{const length=wire.getTotalLength(),m=wire.getScreenCTM();for(let s=3;s<length-3;s+=3){const pt=wire.getPointAtLength(s),p=new DOMPoint(pt.x,pt.y).matrixTransform(m);for(const {id,r} of cards)if(p.x>r.left+3&&p.x<r.right-3&&p.y>r.top+3&&p.y<r.bottom-3){violations.push({index,id,distance:s});break;}}});
  return {wires:wires.length,violations};
 });
 await p.screenshot({path:'../.test-artifacts/canonical-target-readable.png'});
 await d.getByRole('button',{name:'Fit all',exact:true}).click();await p.waitForTimeout(500);
 await p.screenshot({path:'../.test-artifacts/canonical-target-whole-graph.png'});
 await d.getByRole('button',{name:'Close Create image training set',exact:true}).click();
 await p.getByRole('button',{name:'New project',exact:true}).click();
 const create=p.getByRole('dialog',{name:'New project',exact:true});
 const prefill=await create.locator('[aria-label="Reference STL path"]').innerText();expect(prefill.replaceAll('\\','/')).toBe(path.replaceAll('\\','/'));
 await expect(create.getByLabel('Original stereo SVO')).not.toHaveValue('');await expect(create.getByLabel('Camera calibration source')).not.toHaveValue('');
 await create.getByRole('button',{name:'Cancel',exact:true}).click();
 await p.getByRole('button',{name:'Create image training set',exact:true}).click();
 await writeFile('../.test-artifacts/canonical-target-native.json',JSON.stringify({path,prefill,routing},null,2));
 console.log(JSON.stringify({path,prefill,wires:routing.wires,violations:routing.violations.length}));
 expect(routing.violations).toEqual([]);
}finally{await b.close();}
