import assert from 'node:assert/strict';
import {test} from 'node:test';
import {makeBoundWakeChannel, RDCWakeSignal} from '../lib/rdc-wake.mjs';

const DEVICE='00000000-0000-4000-8000-000000000001';
const url=(path)=>new Request('https://rdc-wake.internal'+path,{method:'POST'});

test('no Durable Object binding means opt-out and polling-only compatibility',()=>{
  assert.equal(makeBoundWakeChannel({}),null);
  assert.equal(makeBoundWakeChannel({RDC_WAKE_CHANNEL:{}}),null);
});

test('device-scoped private binding never sends credentials, request args or source',async()=>{
  const calls=[];
  const ns={
    idFromName(name){calls.push(['id',name]);return 'scoped-device'},
    get(id){
      calls.push(['get',id]);
      return {async fetch(request){
        calls.push(['fetch',new URL(request.url).pathname,new URL(request.url).search,request.method,
          await request.text(),request.headers.get('Authorization')]);
        return new Response(JSON.stringify({ok:true,signaled:true}),{status:200});
      }};
    }
  };
  const wake=makeBoundWakeChannel({RDC_WAKE_CHANNEL:ns});
  await wake.notify(DEVICE);
  assert.equal(await wake.wait(DEVICE,250),true);
  assert.deepEqual(calls,[
    ['id',DEVICE],['get','scoped-device'],['fetch','/notify','','POST','','null'],
    ['id',DEVICE],['get','scoped-device'],['fetch','/wait','?ms=250','POST','','null']
  ].map(row=>row.map(x=>x==='null'?null:x)));
  assert.ok(!JSON.stringify(calls).includes('password'));
});

test('Durable Object wake signals waiting subscribers and clears their waiters',async()=>{
  const signal=new RDCWakeSignal();
  const first=signal.fetch(url('/wait?ms=250'));
  const second=signal.fetch(url('/wait?ms=250'));
  const notified=await signal.fetch(url('/notify'));
  assert.equal(notified.status,200);
  for(const pending of [first,second]){
    const response=await pending;
    assert.equal(response.status,200);
    assert.equal((await response.json()).signaled,true);
  }
  assert.equal(signal.waiters.size,0);
});

test('missing wake hint times out rather than suspending the relay forever',async()=>{
  const signal=new RDCWakeSignal();
  const response=await signal.fetch(url('/wait?ms=10'));
  assert.equal((await response.json()).signaled,false);
  assert.equal(signal.waiters.size,0);
});

test('wake endpoint rejects public-looking methods, invalid timeouts and unknown routes',async()=>{
  const signal=new RDCWakeSignal();
  const badMethod=await signal.fetch(new Request('https://rdc-wake.internal/notify',{method:'GET'}));
  assert.equal(badMethod.status,405);
  for(const path of ['/wait','/wait?ms=0','/wait?ms=5001','/wait?ms=NaN']){
    const response=await signal.fetch(url(path));
    assert.equal(response.status,400);
  }
  assert.equal((await signal.fetch(url('/unexpected'))).status,404);
});


const OPERATION='00000000-0000-4000-8000-000000000002';

test('completion hints are isolated by original operation and contain no response body',async()=>{
  const signal=new RDCWakeSignal();
  const routes=[];
  const namespace={
    idFromName(name){assert.equal(name,DEVICE);return name},
    get(){return {fetch(request){routes.push(new URL(request.url).pathname);return signal.fetch(request)}}}
  };
  const wake=makeBoundWakeChannel({RDC_WAKE_CHANNEL:namespace});
  const pending=wake.waitResult(DEVICE,OPERATION,200);
  await wake.notifyResult(DEVICE,OPERATION);
  assert.equal(await pending,true);
  assert.deepEqual(routes,['/wait-result','/notify-result']);
  assert.equal(signal.resultWaiters.size,0);
});

test('different operations cannot wake each other and stale completion hints time out',async()=>{
  const signal=new RDCWakeSignal();
  const waiting=signal.fetch(url('/wait-result?operation_id='+OPERATION+'&ms=15'));
  const other='00000000-0000-4000-8000-000000000003';
  await signal.fetch(url('/notify-result?operation_id='+other));
  const response=await waiting;
  assert.equal((await response.json()).signaled,false);
  assert.equal(signal.resultWaiters.size,0);
  for(const path of ['/notify-result','/wait-result?ms=10',
      '/notify-result?operation_id=not-uuid',
      '/wait-result?operation_id='+OPERATION+'&ms=5001']){
    const bad=await signal.fetch(url(path));
    assert.equal(bad.status,400,path);
  }
});


test('completion delivered before listener registration is replayed as a bounded wake hint',async()=>{
  let now=100_000;
  const signal=new RDCWakeSignal({clock:()=>now});
  await signal.fetch(url('/notify-result?operation_id='+OPERATION));
  const started=performance.now();
  const response=await signal.fetch(url('/wait-result?operation_id='+OPERATION+'&ms=120'));
  assert.equal((await response.json()).signaled,true,
    'a recent committed completion must wake a later-arriving gateway waiter');
  assert.ok(performance.now()-started<80,'must not pay the old 120ms fallback interval');
  assert.equal(signal.resultWaiters.size,0);
  assert.ok(signal.recentCompletions.size<=256);
  now+=5001;
  const expired=await signal.fetch(url('/wait-result?operation_id='+OPERATION+'&ms=10'));
  assert.equal((await expired.json()).signaled,false,
    'stale completion hints must not remain in memory or repeat forever');
});

test('recent completion cache is device-local, bounded, and never carries result payload',async()=>{
  let now=150_000;
  const signal=new RDCWakeSignal({clock:()=>now});
  for(let i=0;i<270;i++){
    const id='00000000-0000-4000-8000-'+i.toString(16).padStart(12,'0');
    assert.equal((await signal.fetch(url('/notify-result?operation_id='+id))).status,200);
  }
  assert.ok(signal.recentCompletions.size<=256,'no unbounded cache growth');
  assert.ok(!JSON.stringify([...signal.recentCompletions]).includes('result_json'));
  now+=5001;
  const unrelated='00000000-0000-4000-8000-000000000800';
  const timed=await signal.fetch(url('/wait-result?operation_id='+unrelated+'&ms=10'));
  assert.equal((await timed.json()).signaled,false);
  assert.equal(signal.recentCompletions.size,0,'expired entries must be pruned');
});


test('queue hint arriving before listener is consumed once rather than lost',async()=>{
  let now=200_000;
  const signal=new RDCWakeSignal({clock:()=>now});
  await signal.fetch(url('/notify')); // D1 operation was admitted; waiter not registered yet.
  const started=performance.now();
  const first=await signal.fetch(url('/wait?ms=120'));
  assert.equal((await first.json()).signaled,true);
  assert.ok(performance.now()-started<80,'must not pay the 120ms fallback delay');
  assert.equal(signal.lastDeviceNoticeAt,null,'queued pre-listener wake is one-shot');
  const second=await signal.fetch(url('/wait?ms=10'));
  assert.equal((await second.json()).signaled,false,
    'an old wake must not trigger repeated empty D1 claim queries');
  await signal.fetch(url('/notify'));
  now+=751;
  const stale=await signal.fetch(url('/wait?ms=10'));
  assert.equal((await stale.json()).signaled,false,'stale queue hints expire');
});

test('queue hint reaches existing listeners without leaving a stale cached wake',async()=>{
  const signal=new RDCWakeSignal();
  const pending=signal.fetch(url('/wait?ms=200'));
  await signal.fetch(url('/notify'));
  assert.equal((await (await pending).json()).signaled,true);
  assert.equal(signal.lastDeviceNoticeAt,null);
  const after=await signal.fetch(url('/wait?ms=10'));
  assert.equal((await after.json()).signaled,false);
});
