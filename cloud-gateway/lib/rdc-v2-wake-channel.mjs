import {RDCV2EventBroker} from './rdc-v2-broker.mjs';
import {createControlEvent} from './rdc-v2-protocol.mjs';

// Optional private Durable Object hint path for RDC 2.0. This adapter never
// contains work, user identity, command arguments or result payloads.
// Durable D1 claim/results remain mandatory, including after any lost hint.
const internalOrigin='https://rdc-wake.internal';
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const shape=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
const exact=(value,allowed,required)=>shape(value)&&
  Object.keys(value).every(key=>allowed.includes(key))&&
  required.every(key=>Object.hasOwn(value,key));

export function makeBoundV2WakeChannel(namespace){
  if(!namespace||typeof namespace.idFromName!=='function'||typeof namespace.get!=='function')
    return null;
  const cursors=new Map();
  const endpoint=deviceId=>{
    if(!uuid.test(deviceId))throw new TypeError('Invalid RDC wake device');
    return namespace.get(namespace.idFromName(deviceId));
  };
  async function post(deviceId,route,body){
    const response=await endpoint(deviceId).fetch(new Request(internalOrigin+'/v2/'+route,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({deviceId,...body}),
    }));
    if(!response.ok)throw new Error('RDC private V2 event channel unavailable');
    const result=await response.json();
    if(result?.ok!==true)throw new Error('Invalid RDC V2 event response');
    return result;
  }
  async function wait(deviceId,kind,operationId,intervalMs){
    if(!Number.isFinite(intervalMs)||intervalMs<=0)
      throw new TypeError('Invalid RDC V2 interval');
    const ms=Math.max(1,Math.min(5000,Math.ceil(intervalMs)));
    const cursorKey=kind==='queue-ready'?deviceId+':queue':deviceId+':'+operationId;
    const afterSequence=cursors.get(cursorKey)??0;
    const response=await post(deviceId,'wait',{
      kind,...(operationId?{operationId}:{}),afterSequence,timeoutMs:ms,
    });
    if(!Number.isSafeInteger(response.latestSequence)||response.latestSequence<0||
        typeof response.signaled!=='boolean'||typeof response.gap!=='boolean')
      throw new Error('Invalid RDC V2 cursor response');
    cursors.set(cursorKey,response.latestSequence);
    // A missed wake demands an immediate D1 recheck. Never replay any action.
    return response.signaled||response.gap;
  }
  return {
    notify:deviceId=>post(deviceId,'notify',{kind:'queue-ready'}).then(()=>{}),
    wait:(deviceId,intervalMs)=>wait(deviceId,'queue-ready',null,intervalMs),
    notifyResult:(deviceId,operationId)=>post(deviceId,'notify',{
      kind:'result-ready',operationId,
    }).then(()=>{}),
    waitResult:(deviceId,operationId,intervalMs)=>wait(deviceId,'result-ready',operationId,intervalMs),
  };
}

export async function handleV2Wake(signal,request){
  const address=new URL(request.url);
  const respond=(value,status=200)=>Response.json(value,{status,
    headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
  if(!['/v2/notify','/v2/wait'].includes(address.pathname))return respond({ok:false},404);
  if(request.method!=='POST')return respond({ok:false},405);
  if(request.headers.get('Content-Type')?.split(';')[0].trim()!=='application/json')
    return respond({ok:false},415);
  let payload;
  const declared=request.headers.get('content-length');
  if(declared!==null&&(!/^\d+$/.test(declared)||Number(declared)>512))
    return respond({ok:false},413);
  const reader=request.body?.getReader();
  if(!reader)return respond({ok:false},400);
  try {
    const bytes=new Uint8Array(512);
    let used=0;
    while(true){
      const {done,value}=await reader.read();
      if(done)break;
      if(used+value.byteLength>512){
        await reader.cancel().catch(()=>{});
        return respond({ok:false},413);
      }
      bytes.set(value,used);
      used+=value.byteLength;
    }
    payload=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes.subarray(0,used)));
  }catch{return respond({ok:false},400)}
  finally{reader.releaseLock()}
  const isWait=address.pathname==='/v2/wait';
  const allowed=isWait?['deviceId','kind','operationId','afterSequence','timeoutMs']:
    ['deviceId','kind','operationId'];
  const required=isWait?['deviceId','kind','afterSequence','timeoutMs']:
    ['deviceId','kind'];
  if(!exact(payload,allowed,required))return respond({ok:false},400);
  // Check only exact control-event fields; timeouts and cursors are
  // transport metadata, never part of an executable event.
  const {afterSequence,timeoutMs,...event}=payload;
  try{createControlEvent({...event,sequence:0})}catch{return respond({ok:false},400)}
  if(isWait&&(!Number.isSafeInteger(payload.afterSequence)||payload.afterSequence<0||
      !Number.isSafeInteger(payload.timeoutMs)||payload.timeoutMs<1||payload.timeoutMs>5000))
    return respond({ok:false},400);
  if(signal.v2DeviceId&&signal.v2DeviceId!==payload.deviceId)return respond({ok:false},403);
  if(!signal.v2Broker) {
    signal.v2Broker=new RDCV2EventBroker({deviceId:payload.deviceId,clock:signal.clock,
      maxEvents:256,maxWaiters:512,ttlMs:5000});
    signal.v2DeviceId=payload.deviceId;
  }
  if(!isWait){
    const event=signal.v2Broker.publish({kind:payload.kind,
      ...(payload.kind==='result-ready'?{operationId:payload.operationId}:{})});
    return respond({ok:true,sequence:event.sequence});
  }
  const current=await signal.v2Broker.wait({
    afterSequence:payload.afterSequence,timeoutMs:payload.timeoutMs,signal:request.signal,
  });
  const matches=current.events.some(event=>event.kind===payload.kind&&
    (payload.kind!=='result-ready'||event.operationId===payload.operationId));
  return respond({ok:true,signaled:matches||current.gap,
    gap:current.gap,latestSequence:current.latestSequence});
}
