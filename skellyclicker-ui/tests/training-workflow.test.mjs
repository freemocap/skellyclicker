import test from 'node:test';
import assert from 'node:assert/strict';
import {build} from 'esbuild';
const compiled=await build({entryPoints:['src/training-workflow.ts'],bundle:true,write:false,format:'esm',platform:'node'});
const {defaultConfig,validateConfig,candidateFrames,trainingGraph,readConfig}=await import('data:text/javascript;base64,'+Buffer.from(compiled.outputFiles[0].text).toString('base64'));
const summary={frames:Array.from({length:7},(_,i)=>({source_frame:100+i,accepted:i%2===0,status:'candidate'})),accepted:4,calibration:{source_frame_count:130,image_width:640,image_height:480}};
test('defaults and sampling use source identity, retain failed candidates, and filter before stride',()=>{
 const config=defaultConfig(summary);assert.equal(config.first,'100');assert.equal(config.count,'7');
 assert.deepEqual(candidateFrames({...config,step:'2'},summary),[100,102,104,106]);
 assert.deepEqual(candidateFrames({...config,fit:'failed',step:'2'},summary),[101,105]);
 assert.deepEqual(candidateFrames({...config,fit:'passed',limit:'2'},summary),[100,102]);
});
test('reuse refuses missing source frames and invalid configuration',()=>{
 const config=defaultConfig(summary);
 assert.ok(validateConfig({...config,first:'99'},summary).length);
 assert.ok(validateConfig({...config,step:'0'},summary).length);
 assert.ok(validateConfig({...config,count:'901'},summary).length);
 assert.ok(validateConfig({...config,mode:'fresh',first:'129',count:'2'},summary).length);
 assert.deepEqual(candidateFrames({...config,mode:'fresh'},summary),[]);
 assert.equal(readConfig({first:100}),null);
});
test('workflow binds every input once with matching semantics and retains manual review dependency',()=>{
 const nodes=new Map(trainingGraph.definition.nodes.map(n=>[n.id,n]));const bound=new Set();
 for(const e of trainingGraph.definition.edges){
  const source=nodes.get(e.source.node).outputs.find(p=>p.name===e.source.port);
  const target=nodes.get(e.target.node).inputs.find(p=>p.name===e.target.port);
  assert.deepEqual(source.contract,target.contract);assert.equal(e.binding,'same_key');
  const key=e.target.node+':'+e.target.port;assert.ok(!bound.has(key));bound.add(key);
  assert.ok(trainingGraph.topological_order.indexOf(e.source.node)<trainingGraph.topological_order.indexOf(e.target.node));
 }
 assert.equal(bound.size,trainingGraph.definition.nodes.reduce((n,node)=>n+node.inputs.length,0));
 assert.equal(nodes.get('review_labels').execution_resource,'human');
 assert.ok(trainingGraph.definition.edges.some(e=>e.source.node==='review_labels'&&e.target.node==='publish_dataset'));
});
