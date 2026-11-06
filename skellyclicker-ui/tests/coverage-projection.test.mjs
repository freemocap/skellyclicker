import {test} from 'node:test';
import assert from 'node:assert/strict';
import {build} from 'esbuild';
await build({entryPoints:['src/coverage-projection.ts'],bundle:true,platform:'node',format:'esm',outfile:'../.test-artifacts/coverage-projection.mjs'});
const {projectedHistograms}=await import('../../.test-artifacts/coverage-projection.mjs');
const identity=[1,0,0,0,1,0,0,0,1],sum=x=>x.reduce((a,b)=>a+b,0);
test('signed projection preserves front/back and reports axes rather than inventing bins',()=>{
 const h=projectedHistograms([[0,0,1],[0,0,-1],[1,0,0],[-1,0,0],[0,1,0],[0,-1,0]],identity);
 assert.equal(sum(h.horizontal),4);assert.equal(h.horizontalUndefined,2);assert.equal(sum(h.vertical),4);assert.equal(h.verticalUndefined,2);assert.equal(h.horizontal[0],1);assert.equal(h.horizontal[12],1);assert.equal(h.invalid,0);
});
test('orbit rotation changes projection while conserving both histogram counts',()=>{
 const dirs=Array.from({length:3038},(_,i)=>{const z=2*(i+.5)/3038-1,a=i*2.3999632297,r=Math.sqrt(1-z*z);return [r*Math.cos(a),r*Math.sin(a),z]});
 const before=projectedHistograms(dirs,identity),after=projectedHistograms(dirs,[0,0,1,0,1,0,-1,0,0]);
 assert.notDeepEqual(before.horizontal,after.horizontal);for(const h of [before,after]){assert.equal(sum(h.horizontal)+h.horizontalUndefined,dirs.length);assert.equal(sum(h.vertical)+h.verticalUndefined,dirs.length);assert.equal(h.invalid,0);}
});
test('invalid source directions remain counted as unknown rather than contaminating charts',()=>{const h=projectedHistograms([[0,0,0],[NaN,0,1],[0,0,1]],identity);assert.equal(h.invalid,2);assert.equal(sum(h.horizontal),1);assert.throws(()=>projectedHistograms([],[]));});
