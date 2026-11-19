import assert from 'node:assert/strict';
import {test} from 'node:test';
import {makeBoundWakeChannel, RDCWakeSignal} from '../lib/rdc-wake.mjs';

const DEVICE='00000000-0000-4000-8000-000000000001';
const OTHER_DEVICE='00000000-0000-4000-8000-000000000009';
const OP='00000000-0000-4000-8000-000000000002';
const OTHER='00000000-0000-4000-8000-000000000003';
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));

function setup(){
 const instances=new Map(),requests=[];
 const namespace={
  idFromName(name){return name},
  get(name){if(!instances.has(name))instances.set(name,new RDCWakeSignal());
    return {async fetch(request){requests.push({name,path:new URL(request.url).pathname,
      body:await request.clone().text(),headers:[...request.headers.keys()]});
      return instances.get(name).fetch(request)}}}
 };
 const env={RDC_WAKE_CHANNEL:namespace,RDC_ENABLE_V2_WAKE:'1'};
 return {channel:makeBoundWakeChannel(env),legacy:makeBoundWakeChannel({RDC_WAKE_CHANNEL:namespace}),
    instances,requests,env};
}

test('v2 mode is strictly opt-in and requires the original private binding',()=>{
 assert.equal(makeBoundWakeChannel({RDC_ENABLE_V2_WAKE:'1'}),null);
 assert.equal(makeBoundWakeChannel({RDC_ENABLE_V2_WAKE:'yes'}),null);
 const s=setup();
 assert.ok(s.channel);
 assert.ok(s.legacy);
});

test('v2 gateway notifies original device queue without any tool payload',async()=>{
 const s=setup();
 const pending=s.channel.wait(DEVICE,200);
 await delay(5);
 await s.channel.notify(DEVICE);
 assert.equal(await pending,true);
 const v2=s.requests.filter(x=>x.path.startsWith('/v2/'));
 assert.ok(v2.length>=2,'private DO must receive explicit v2 event route');
 assert.ok(v2.every(x=>!x.body.includes('request_json')&&!x.body.includes('token')));
 assert.equal(await s.channel.wait(DEVICE,5),false,
   'old event must be consumed exactly once by this notification subscriber');
});

test('v2 completed result wakes only exact immutable operation ID',async()=>{
 const s=setup();
 const pending=s.channel.waitResult(DEVICE,OP,50);
 await delay(5);
 await s.channel.notifyResult(DEVICE,OTHER);
 assert.equal(await pending,false,'unrelated operation cannot signal selected result');
 const matching=s.channel.waitResult(DEVICE,OP,200);
 await delay(5);
 await s.channel.notifyResult(DEVICE,OP);
 assert.equal(await matching,true);
 assert.equal(await s.channel.waitResult(DEVICE,OP,5),false,'cursor cannot replay a completed hint');
});

test('v2 queue and completion signals are isolated by private device namespaces',async()=>{
 const s=setup();
 const waiting=s.channel.wait(DEVICE,35);
 await delay(5);
 await s.channel.notify(OTHER_DEVICE);
 assert.equal(await waiting,false);
 assert.equal(s.instances.size,2);
 assert.ok(s.requests.every(x=>!x.body.includes('source_code')));
});

test('v2 missed bounded history signals an authoritative D1 recheck',async()=>{
 const s=setup();
 for(let n=0;n<300;n++)await s.channel.notify(DEVICE);
 assert.equal(await s.channel.wait(DEVICE,10),true,
   'lost event history must recheck durable DB instead of assuming no operation');
 assert.equal(await s.channel.wait(DEVICE,5),false);
});

test('v2 invalid data and remote legacy mode never cross into the new broker',async()=>{
 const s=setup();
 await s.legacy.notify(DEVICE);
 assert.ok(s.requests.some(x=>x.path==='/notify'));
 assert.ok(!s.requests.some(x=>x.path==='/v2/notify'));
 await assert.rejects(s.channel.notifyResult(DEVICE,'/fake/op'));
 const forged=new Request('https://rdc-wake.internal/v2/notify',{
   method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({deviceId:DEVICE,kind:'queue-ready',request_json:'secret'})
 });
 const denied=await (new RDCWakeSignal()).fetch(forged);
 assert.equal(denied.status,400);
});

test('v2 signal pins its device ID within one private Durable Object',async()=>{
 const object=new RDCWakeSignal();
 const send=(deviceId,kind)=>object.fetch(new Request(
  'https://rdc-wake.internal/v2/notify',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({deviceId,kind}),
  }));
 assert.equal((await send(DEVICE,'queue-ready')).status,200);
 assert.equal((await send(OTHER_DEVICE,'queue-ready')).status,403);
 assert.equal(object.v2DeviceId,DEVICE);
 assert.equal(object.v2Broker.readSince(0).events.length,1);
});

test('v2 invalid, oversized, or malformed JSON cannot enqueue a hint',async()=>{
 const object=new RDCWakeSignal();
 const cases=[
  ['POST','/v2/notify','text/plain','{}',415],
  ['POST','/v2/notify','application/json','{broken',400],
  ['POST','/v2/notify','application/json',JSON.stringify({deviceId:DEVICE,kind:'queue-ready',password:'fake'}),400],
  ['POST','/v2/notify','application/json','x'.repeat(750),413],
  ['POST','/v2/wait','application/json',JSON.stringify({deviceId:DEVICE,kind:'queue-ready',timeoutMs:-10,afterSequence:0}),400],
  ['POST','/v2/wait','application/json',JSON.stringify({deviceId:DEVICE,kind:'queue-ready',timeoutMs:10,afterSequence:-1}),400],
 ];
 for(const [method,path,type,body,status] of cases){
  const result=await object.fetch(new Request('https://rdc-wake.internal'+path,{
    method,headers:{'Content-Type':type},body,
  }));
  assert.equal(result.status,status,path);
 }
 assert.equal(object.v2Broker,null,'rejected hints must not initialize a channel');
});

test('v2 bounded request reader rejects streaming bodies before consuming overflow',async()=>{
  let reads=0,cancelled=false;
  const request=new Request('https://rdc-wake.internal/v2/notify',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:new ReadableStream({
      pull(controller){
        reads++;
        if(reads===1)controller.enqueue(new Uint8Array(520).fill(65));
        else controller.error(new Error('Oversized body must not be fully consumed'));
      },
      cancel(){cancelled=true}
    },{highWaterMark:0}),
    duplex:'half'
  });
  const signal=new RDCWakeSignal();
  const response=await signal.fetch(request);
  assert.equal(response.status,413);
  assert.equal(signal.v2Broker,null);
  assert.equal(reads,1);
  assert.equal(cancelled,true);
});

test('private exact-result wait remains pending across unrelated notices',async()=>{
  const s=setup();
  let finished=false;
  const pending=s.channel.waitResult(DEVICE,OP,200).then(value=>{
    finished=true;
    return value;
  });
  await s.channel.notify(DEVICE);
  await s.channel.notifyResult(DEVICE,OTHER);
  await Promise.resolve();
  assert.equal(finished,false,'unrelated queue/completion hints must not consume the active wait');
  await s.channel.notifyResult(DEVICE,OP);
  assert.equal(await pending,true);
});

test('private queue wait ignores unrelated completion hints',async()=>{
  const s=setup();
  let finished=false;
  const pending=s.channel.wait(DEVICE,150).then(value=>{
    finished=true;
    return value;
  });
  await s.channel.notifyResult(DEVICE,OP);
  await Promise.resolve();
  assert.equal(finished,false);
  await s.channel.notify(DEVICE);
  assert.equal(await pending,true);
});
