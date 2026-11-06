import {chromium,expect} from '@playwright/test';
const b=await chromium.launch({channel:'msedge',headless:true});const p=await b.newPage();let generated=0;
await p.route('http://candidate-fixture.invalid/**',async route=>{
 const url=new URL(route.request().url());let value;
 if(url.pathname.endsWith('/result'))value={frames:Array.from({length:4},(_,i)=>({source_frame:10+i,accepted:true,status:'accepted'})),accepted:4,calibration:{source_frame_count:100,image_width:100,image_height:80}};
 else if(url.pathname.endsWith('/validate-stl'))value={path:'/fixture/canonical.stl',compatible:true,sha256:'mesh',authored_units:'mm'};
 else if(url.pathname.endsWith('/preview'))value={moment_count:4,image_count:8,label_count:24,expected_pose_manifest_sha256:'pose',expected_target_manifest_sha256:'target',source_frames:[10,11,12,13]};
 else if(url.pathname.endsWith('/runs')){generated++;value={run_id:'fixture-run'};}else value={};
 await route.fulfill({json:value});
});
await p.route('**/__candidate-actions-test',async route=>{const original=await route.fetch({url:'http://127.0.0.1:5176/'});await route.fulfill({response:original,body:(await original.text()).replace('/src/main.tsx','/tests/candidate-actions-harness.tsx')});});
try{
 await p.goto('http://127.0.0.1:5176/__candidate-actions-test');const d=p.getByRole('dialog');
 await expect(d.getByRole('button',{name:'Preview candidates',exact:true})).toBeEnabled();
 await d.getByRole('button',{name:'List',exact:true}).click();
 await d.getByRole('combobox',{name:'Input strategy',exact:true}).selectOption('fresh');
 await expect(d.getByRole('button',{name:'Preview candidates',exact:true})).toBeDisabled();
 await expect(d.locator('.training-set-action-status')).toContainText('Fresh preparation is not connected');
 await d.getByRole('button',{name:'Use prepared frames',exact:true}).click();
 await expect(d.getByRole('button',{name:'Preview candidates',exact:true})).toBeEnabled();
 await expect(d.locator('.training-set-action-status')).toContainText('Generate candidates becomes available after a successful preview');
 await d.getByRole('button',{name:'Preview candidates',exact:true}).click();
 await expect(d.getByRole('button',{name:'Generate candidates',exact:true})).toBeEnabled();
 expect(generated).toBe(0);console.log('PASS: exact fresh-mode disabled reason, one-click recovery, preview prerequisite explained, generation enabled');
}finally{await b.close();}
