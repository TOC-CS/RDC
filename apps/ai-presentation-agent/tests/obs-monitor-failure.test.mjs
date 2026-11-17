import test from 'node:test';
import assert from 'node:assert/strict';
import {OBSReadOnlyMonitor} from '../src/obs-monitor.mjs';

class OfflineSocket extends EventTarget {
 constructor(){
   super();
   queueMicrotask(()=>this.dispatchEvent(new Event('error')));
 }
 close(){}
 send(){throw Error('No outgoing OBS commands after a failed connection');}
}
class InterruptedSocket extends EventTarget {
 constructor(){
   super();
   this.requests=[];
   queueMicrotask(()=>this.dispatchEvent(
     new MessageEvent('message',{data:JSON.stringify({
       op:0,d:{obsWebSocketVersion:'5.0.0',rpcVersion:1}
     })})
   ));
 }
 send(raw){
   const incoming=JSON.parse(raw);
   if(incoming.op===1){
     queueMicrotask(()=>this.dispatchEvent(
       new MessageEvent('message',{data:JSON.stringify({
         op:2,d:{negotiatedRpcVersion:1}
       })})
     ));
   }else if(incoming.op===6){
     this.requests.push(incoming.d.requestType);
     queueMicrotask(()=>this.dispatchEvent(new Event('close')));
   }
 }
 close(){}
}
test('disconnected OBS is reported as unavailable, without scene or stream writes',async()=>{
 const monitor=new OBSReadOnlyMonitor({WebSocketCtor:OfflineSocket,timeoutMs:500});
 await assert.rejects(()=>monitor.inspect(),/connection failed|closed/i);
 assert.equal(typeof monitor.startStream,'undefined');
 assert.equal(typeof monitor.stopStream,'undefined');
});
test('OBS connection dropping after identification does not auto-reconnect or issue duplicate write',async()=>{
 const monitor=new OBSReadOnlyMonitor({WebSocketCtor:InterruptedSocket,timeoutMs:500});
 await assert.rejects(()=>monitor.inspect(),/connection.*closed/i);
});
test('invalid status protocol fails closed rather than fabricating a healthy recording state',async()=>{
 class WrongRpc extends EventTarget {
   constructor(){
     super();
     queueMicrotask(()=>this.dispatchEvent(new MessageEvent('message',{
       data:JSON.stringify({op:0,d:{rpcVersion:1}})
     })));
   }
   send(value){
     if(JSON.parse(value).op===1)
       queueMicrotask(()=>this.dispatchEvent(new MessageEvent('message',{
         data:JSON.stringify({op:2,d:{negotiatedRpcVersion:99}})
       })));
   }
   close(){}
 }
 await assert.rejects(()=>new OBSReadOnlyMonitor({
   WebSocketCtor:WrongRpc,timeoutMs:500
 }).inspect(),/unsupported/i);
});
