import assert from 'node:assert/strict';
import {test} from 'node:test';
import {TransportService} from '@freemocap/client';
import {stateKind} from '../src/state-message.ts';
const baseUrl=process.env.SKELLYCLICKER_TEST_URL || 'http://127.0.0.1:8006';
test('live backend logs use the existing validated SDK transport',async()=>{
 const url=new URL(baseUrl+'/websocket/connect');url.protocol='ws:';
 const stream=new TransportService({url:url.href,kinds:{skellyclicker_state:stateKind}});
 const records=[];const errors=[];
 stream.subscribeToLog(record=>records.push(record));
 stream.subscribeToProtocolErrors(error=>errors.push(error));
 try {
  stream.connect();
  const waitFor=async predicate=>{for(let i=0;i<100;i++){if(predicate())return;await new Promise(r=>setTimeout(r,50));}throw new Error('Expected live log not received');};
  await waitFor(()=>records.some(r=>r.message.includes('SkellyClicker backend ready')));
  const response=await fetch(baseUrl+'/api/projects/open',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project_path:'Z:/skellyclicker-log-check-does-not-exist'})});
  assert.equal(response.status,400);
  await waitFor(()=>records.some(r=>r.levelname==='WARNING'&&r.message.includes('Project operation failed')));
  const warning=records.find(r=>r.levelname==='WARNING');
  assert.equal(warning.name,'skellyclicker.projects');
  assert.ok(warning.created>0);assert.ok(warning.process>0);
  assert.deepEqual(errors,[]);
 } finally {stream.disconnect();}
});
