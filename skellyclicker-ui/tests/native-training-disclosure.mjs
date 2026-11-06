import {chromium,expect} from '@playwright/test';
import {writeFile} from 'node:fs/promises';
import {build} from 'esbuild';
const compiled=await build({entryPoints:['src/training-workflow.ts'],bundle:true,write:false,format:'esm',platform:'node'});
const {trainingGraph}=await import('data:text/javascript;base64,'+Buffer.from(compiled.outputFiles[0].text).toString('base64'));
const browser=await chromium.connectOverCDP('http://127.0.0.1:9224');
const checks={},errors=[],mutations=[];
try {
 const page=browser.contexts().flatMap(c=>c.pages()).find(p=>p.url().includes('5176'));
 page.on('pageerror',error=>errors.push(String(error)));
 page.on('request',r=>{if(/preparation\/(start|cancel)|labels\/runs/.test(r.url()))mutations.push(r.url());});
 const close=page.getByRole('button',{name:'Close Create image training set',exact:true});if(await close.isVisible())await close.click();
 await page.getByRole('button',{name:'Create image training set',exact:true}).click();
 const dialog=page.getByRole('dialog',{name:'Create image training set',exact:true});
 await expect(dialog.locator('.pg-node')).toHaveCount(7);
 const disclosures=dialog.locator('.pg-node button[aria-expanded]');
 await expect(disclosures).toHaveCount(7);
 for(const control of await disclosures.all())await expect(control).toHaveAttribute('aria-expanded','true');
 await expect(dialog.getByRole('button',{name:'Open stage settings',exact:true})).toHaveCount(0);
 const titles=await dialog.locator('.pg-node-title').evaluateAll(es=>es.map(e=>({text:e.textContent,whiteSpace:getComputedStyle(e).whiteSpace,overflow:getComputedStyle(e).textOverflow,width:e.clientWidth,scrollWidth:e.scrollWidth,height:e.clientHeight,scrollHeight:e.scrollHeight})));
 for(const title of titles){expect(title.whiteSpace).not.toBe('nowrap');expect(title.overflow).not.toBe('ellipsis');expect(title.scrollWidth).toBeLessThanOrEqual(title.width+1);expect(title.scrollHeight).toBeLessThanOrEqual(title.height+1);}
 checks.allOpenAndWrapped=titles;
 const initialTransform=await dialog.locator('.pg-world').evaluate(e=>e.style.transform);
 const scale=Number((await dialog.locator('.pg-zoom span').innerText()).replace('%',''));expect(scale).toBeGreaterThanOrEqual(80);checks.initialScale=scale;
 await page.screenshot({path:'../.test-artifacts/training-panel-expanded.png'});
 const source=dialog.locator('.pg-node[data-stage-id="source_inputs"]');const disclosure=source.locator('button[aria-expanded]');
 await disclosure.click();await expect(disclosure).toHaveAttribute('aria-expanded','false');
 await page.waitForTimeout(150);expect(await dialog.locator('.pg-world').evaluate(e=>e.style.transform)).toBe(initialTransform);checks.pointerCameraUnchanged=true;
 await disclosure.focus();await page.keyboard.press('Enter');await expect(disclosure).toHaveAttribute('aria-expanded','true');
 await page.waitForTimeout(150);expect(await dialog.locator('.pg-world').evaluate(e=>e.style.transform)).toBe(initialTransform);checks.keyboardCameraUnchanged=true;
 const outline=dialog.getByRole('navigation',{name:'Workflow stages'});
 await outline.getByRole('button').filter({hasText:'Source inputs'}).click();await page.waitForTimeout(450);
 const focusedTransform=await dialog.locator('.pg-world').evaluate(e=>e.style.transform);
 await disclosure.click();await expect(disclosure).toHaveAttribute('aria-expanded','false');await page.waitForTimeout(150);
 expect(await dialog.locator('.pg-world').evaluate(e=>e.style.transform)).toBe(focusedTransform);checks.focusedCameraUnchanged=true;
 await dialog.getByRole('button',{name:'List',exact:true}).click();
 await expect(dialog.locator('[data-stage-id="source_inputs"] button[aria-expanded]')).toHaveAttribute('aria-expanded','false');
 const value=await dialog.getByRole('spinbutton',{name:'Candidate stride',exact:true}).inputValue();
 await dialog.getByRole('button',{name:'Graph',exact:true}).click();
 await expect(disclosure).toHaveAttribute('aria-expanded','false');checks.viewDisclosurePreserved=true;
 await outline.getByRole('button').filter({hasText:'Generate keypoint candidates'}).click();
 await expect(disclosure).toHaveAttribute('aria-expanded','false');
 await expect(dialog.getByRole('spinbutton',{name:'Candidate stride',exact:true})).toHaveValue(value);checks.focusDoesNotReopen=true;
 await dialog.getByRole('button',{name:'Fit all',exact:true}).click();await page.waitForTimeout(450);
 const fitTransform=await dialog.locator('.pg-world').evaluate(e=>e.style.transform);
 await disclosure.click();await expect(disclosure).toHaveAttribute('aria-expanded','true');await page.waitForTimeout(150);
 expect(await dialog.locator('.pg-world').evaluate(e=>e.style.transform)).toBe(fitTransform);checks.fitCameraUnchanged=true;
 const layout=await dialog.evaluate((root,graph)=>{
  const nodes=[...root.querySelectorAll('.pg-node')];const rects=nodes.map(n=>({id:n.dataset.stageId,top:parseFloat(n.style.top),height:n.offsetHeight}));
  const rows=[...new Set(rects.map(n=>n.top))].sort((a,b)=>a-b);
  const paths=[...root.querySelectorAll('.pg-wire')];
  const endpoints=graph.definition.edges.map((edge,i)=>{
   const path=paths[i];const transform=path.getScreenCTM();
   const points=[path.getPointAtLength(0),path.getPointAtLength(path.getTotalLength())].map(p=>new DOMPoint(p.x,p.y).matrixTransform(transform));
   return [['source','out','outputs'],['target','in','inputs']].map(([end,direction,ports],j)=>{
    const ref=edge[end],definition=graph.definition.nodes.find(n=>n.id===ref.node);const index=definition[ports].findIndex(p=>p.name===ref.port);
    const element=root.querySelector(`[data-stage-id="${ref.node}"] .pg-port.${direction}:nth-child(1)`);
    const port=[...root.querySelectorAll(`[data-stage-id="${ref.node}"] .pg-port.${direction}`)][index];
    const r=port.querySelector('.pg-socket').getBoundingClientRect();
    return {node:ref.node,port:ref.port,dx:points[j].x-(r.left+r.width/2),dy:points[j].y-(r.top+r.height/2)};
   });
  }).flat();return {rows,rects,endpoints};
 },trainingGraph);
 expect(layout.rows.length).toBe(2);expect(layout.rows[1]).toBeGreaterThan(Math.max(...layout.rects.filter(n=>n.top===layout.rows[0]).map(n=>n.top+n.height)));
 for(const endpoint of layout.endpoints){expect(Math.abs(endpoint.dy)).toBeLessThan(3);expect(Math.abs(endpoint.dx)).toBeLessThan(3);}
 checks.measuredLayout=layout;
 await dialog.getByRole('button',{name:'Close Create image training set',exact:true}).click();
 await page.getByRole('button',{name:'Create image training set',exact:true}).click();
 await expect(page.getByRole('dialog').locator('.pg-node button[aria-expanded="true"]')).toHaveCount(7);
 await page.screenshot({path:'../.test-artifacts/training-panel-expanded-review.png'});
 expect(errors).toEqual([]);expect(mutations).toEqual([]);
 await writeFile('../.test-artifacts/training-panel-disclosure.json',JSON.stringify({checks,errors,mutations},null,2));
 console.log(JSON.stringify({checks:Object.keys(checks),initialScale:scale}));
}finally{await browser.close();}
