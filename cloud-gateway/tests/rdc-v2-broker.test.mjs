import assert from 'node:assert/strict';
import {test} from 'node:test';
import {RDCV2EventBroker} from '../lib/rdc-v2-broker.mjs';
const device='11111111-1111-4111-8111-111111111111';
const operation='22222222-2222-4222-8222-222222222222';

test('v2 event broker publishes monotonically sequenced ID-only hints',async()=>{
  const broker=new RDCV2EventBroker({deviceId:device});
  const a=broker.publish({kind:'queue-ready'});
  const b=broker.publish({kind:'result-ready',operationId:operation});
  assert.equal(a.sequence,1);
  assert.equal(b.sequence,2);
  assert.deepEqual(broker.readSince(0).events,[a,b]);
  assert.deepEqual(Object.keys(b),['version','kind','deviceId','operationId','sequence']);
});

test('v2 event broker wakes subscribers immediately with original event identity',async()=>{
  const broker=new RDCV2EventBroker({deviceId:device});
  const pending=broker.wait({afterSequence:0,timeoutMs:1000});
  const receipt=broker.publish({kind:'result-ready',operationId:operation});
  const result=await pending;
  assert.deepEqual(result.events,[receipt]);
  assert.equal(result.gap,false);
  assert.equal(broker.activeWaiters,0);
});

test('v2 broker closes cancelled subscribers and does not retain callbacks',async()=>{
  const broker=new RDCV2EventBroker({deviceId:device});
  const ctrl=new AbortController();
  const pending=broker.wait({afterSequence:0,timeoutMs:1000,signal:ctrl.signal});
  ctrl.abort();
  const result=await pending;
  assert.deepEqual(result.events,[]);
  assert.equal(broker.activeWaiters,0);
});

test('v2 broker bounds waiting connections and maintains safe backpressure',async()=>{
  const broker=new RDCV2EventBroker({deviceId:device,maxWaiters:2});
  const controls=Array.from({length:2},()=>new AbortController());
  const pending=controls.map(c=>broker.wait({afterSequence:0,timeoutMs:1000,signal:c.signal}));
  assert.throws(()=>broker.wait({afterSequence:0,timeoutMs:1000}),/capacity/);
  controls.forEach(c=>c.abort());
  await Promise.all(pending);
  assert.equal(broker.activeWaiters,0);
});

test('v2 broker flags expired or evicted history and does not claim durable delivery',async()=>{
  let now=1000;
  const broker=new RDCV2EventBroker({deviceId:device,maxEvents:2,ttlMs:50,clock:()=>now});
  broker.publish({kind:'queue-ready'});
  broker.publish({kind:'queue-ready'});
  broker.publish({kind:'queue-ready'});
  assert.equal(broker.readSince(0).gap,true);
  assert.deepEqual(broker.readSince(0).events.map(e=>e.sequence),[2,3]);
  now+=51;
  const result=broker.readSince(0);
  assert.equal(result.gap,true);
  assert.deepEqual(result.events,[]);
  assert.equal(result.latestSequence,3);
});

test('v2 broker rejects payload-bearing notifications and invalid cursors',async()=>{
  const broker=new RDCV2EventBroker({deviceId:device});
  assert.throws(()=>broker.publish({kind:'queue-ready',request_json:'secret'}));
  assert.throws(()=>broker.publish({kind:'result-ready'}));
  assert.throws(()=>broker.readSince(-1));
  assert.throws(()=>broker.wait({afterSequence:0,timeoutMs:60_000}));
});

test('scoped result waiter ignores unrelated event kinds and operation IDs',async()=>{
  const other='33333333-3333-4333-8333-333333333333';
  const broker=new RDCV2EventBroker({deviceId:device});
  let resolved=false;
  const pending=broker.wait({afterSequence:0,timeoutMs:200,
    kind:'result-ready',operationId:operation}).then(receipt=>{
      resolved=true;
      return receipt;
    });
  broker.publish({kind:'queue-ready'});
  broker.publish({kind:'result-ready',operationId:other});
  await Promise.resolve();
  assert.equal(resolved,false,'unrelated hints must not prematurely end the exact result wait');
  assert.equal(broker.activeWaiters,1);
  const matching=broker.publish({kind:'result-ready',operationId:operation});
  const receipt=await pending;
  assert.equal(receipt.gap,false);
  assert.deepEqual(receipt.events,[matching]);
  assert.equal(broker.activeWaiters,0);
});

test('scoped waiter preserves authoritative reconciliation after unrelated event eviction',async()=>{
  const broker=new RDCV2EventBroker({deviceId:device,maxEvents:2});
  const pending=broker.wait({afterSequence:0,timeoutMs:200,
    kind:'result-ready',operationId:operation});
  broker.publish({kind:'queue-ready'});
  broker.publish({kind:'queue-ready'});
  broker.publish({kind:'queue-ready'});
  const receipt=await pending;
  assert.equal(receipt.gap,true,'evicted sequence must cause D1 recheck');
  assert.equal(broker.activeWaiters,0);
});

test('scoped wait replays only exact retained result without cross-operation leakage',async()=>{
  const broker=new RDCV2EventBroker({deviceId:device});
  broker.publish({kind:'result-ready',operationId:'33333333-3333-4333-8333-333333333333'});
  const target=broker.publish({kind:'result-ready',operationId:operation});
  const receipt=await broker.wait({afterSequence:0,timeoutMs:100,
    kind:'result-ready',operationId:operation});
  assert.deepEqual(receipt.events,[target]);
  assert.equal(receipt.latestSequence,2);
  assert.equal(broker.activeWaiters,0);
  assert.throws(()=>broker.wait({afterSequence:0,kind:'result-ready',operationId:'wrong/id'}));
  assert.throws(()=>broker.wait({afterSequence:0,operationId:operation}));
});
