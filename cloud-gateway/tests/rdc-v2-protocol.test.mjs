import assert from 'node:assert/strict';
import {test} from 'node:test';
import {createControlEvent, parseControlEvent, negotiateRdcV2} from '../lib/rdc-v2-protocol.mjs';

const device='11111111-1111-4111-8111-111111111111';
const operation='22222222-2222-4222-8222-222222222222';

test('v2 negotiate selects compatible version and explicit functionality',()=>{
  const result=negotiateRdcV2({protocolVersions:[2,1],features:['result-hints','queue-hints']});
  assert.deepEqual(result,{version:2,features:['queue-hints','result-hints']});
  assert.equal(negotiateRdcV2({protocolVersions:[1],features:[]}),null);
});

test('v2 control event transports only immutable IDs, event kind and sequence',()=>{
  const event=createControlEvent({kind:'result-ready',deviceId:device,operationId:operation,sequence:7});
  assert.deepEqual(Object.keys(event).sort(),['deviceId','kind','operationId','sequence','version']);
  assert.equal(Object.isFrozen(event),true);
  assert.deepEqual(parseControlEvent(JSON.stringify(event)),event);
});

test('v2 queue-ready events never require an operation payload',()=>{
  const event=createControlEvent({kind:'queue-ready',deviceId:device,sequence:0});
  assert.equal(event.operationId,undefined);
  assert.equal(parseControlEvent(JSON.stringify(event)).kind,'queue-ready');
});

test('v2 wire rejects arbitrary fields and dangerous device identities',()=>{
  assert.throws(()=>createControlEvent({kind:'queue-ready',deviceId:'../../../private',sequence:1}));
  assert.throws(()=>createControlEvent({kind:'queue-ready',deviceId:device,sequence:1,token:'secret'}));
  assert.throws(()=>parseControlEvent(JSON.stringify({version:2,kind:'result-ready',deviceId:device,operationId:operation,sequence:1,request_json:'forbidden'})));
  assert.throws(()=>parseControlEvent(JSON.stringify({version:2,kind:'queue-ready',deviceId:device,sequence:1,tool:'rdc_job_run'})));
});

test('v2 wire rejects mutated, replayable or ambiguous sequences',()=>{
  for(const sequence of [-1,2.5,Number.MAX_SAFE_INTEGER+1,'10'])
    assert.throws(()=>createControlEvent({kind:'queue-ready',deviceId:device,sequence}));
  assert.throws(()=>createControlEvent({kind:'result-ready',deviceId:device,sequence:1}));
  assert.throws(()=>parseControlEvent('not-json'));
});
