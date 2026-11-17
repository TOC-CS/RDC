import test from 'node:test';
import assert from 'node:assert/strict';
import {OBSAdapter} from '../src/adapters.mjs';
class MockSocket{
 static active=null;
 constructor(){this.listeners=new Map();this.sent=[];this.closed=false;MockSocket.active=this;}
 addEventListener(type,listener){let list=this.listeners.get(type);if(!list)this.listeners.set(type,list=[]);list.push(listener);}
 send(raw){this.sent.push(JSON.parse(raw));}
 close(){this.closed=true;}
 emit(type,data){for(const fn of this.listeners.get(type)??[])fn(type==='message'?{data:JSON.stringify(data)}:{});}
}
function adapter(){return new OBSAdapter({url:'ws://127.0.0.1:4455/',password:'password',WebSocketCtor:MockSocket,timeoutMs:90});}
async function handshake(){
 const socket=MockSocket.active;
 socket.emit('message',{op:0,d:{rpcVersion:1}});
 assert.equal(socket.sent[0].op,1);
 socket.emit('message',{op:2,d:{negotiatedRpcVersion:1}});
 const sent=socket.sent.at(-1);
 assert.equal(sent.d.requestType,'SetCurrentProgramScene');
 return {socket,sent};
}
test('OBS adapter acknowledges only the matching request response',async()=>{
 const pending=adapter().show(0,{scene:'Worship'});
 const {socket,sent}=await handshake();
 socket.emit('message',{op:7,d:{requestType:'OtherRequest',requestId:'not-ours',requestStatus:{result:true}}});
 assert.equal(socket.closed,false);
 socket.emit('message',{op:7,d:{requestType:'SetCurrentProgramScene',requestId:sent.d.requestId,requestStatus:{result:true}}});
 const verify=socket.sent.at(-1);
 assert.equal(verify.d.requestType,'GetCurrentProgramScene');
 assert.equal(socket.closed,false,'The adapter should wait for independent scene readback.');
 socket.emit('message',{op:7,d:{requestType:'GetCurrentProgramScene',requestId:verify.d.requestId,requestStatus:{result:true},responseData:{sceneName:'Worship'}}});
 assert.deepEqual(await pending,{ok:true,scene:'Worship',confirmed:true});
 assert.equal(socket.closed,true);
});
test('OBS adapter rejects matching negative responses and does not retry',async()=>{
 const pending=adapter().show(0,{scene:'Unknown'});
 const {socket,sent}=await handshake();
 socket.emit('message',{op:7,d:{requestType:'SetCurrentProgramScene',requestId:sent.d.requestId,requestStatus:{result:false,code:601,comment:'Scene not found'}}});
 await assert.rejects(pending,/Scene not found/);
 assert.equal(socket.sent.filter(v=>v.op===6).length,1);
});
test('OBS adapter verifies negotiated RPC version',async()=>{
 const pending=adapter().show(0,{scene:'Worship'});
 const socket=MockSocket.active;
 socket.emit('message',{op:0,d:{rpcVersion:1}});
 socket.emit('message',{op:2,d:{negotiatedRpcVersion:42}});
 await assert.rejects(pending,/RPC version/i);
 assert.equal(socket.sent.some(v=>v.op===6),false);
});
test('OBS adapter fails safely when authentication is required but missing',async()=>{
 const a=new OBSAdapter({url:'ws://127.0.0.1:4455/',password:'',WebSocketCtor:MockSocket,timeoutMs:90});
 const pending=a.show(0,{scene:'Scene'});
 MockSocket.active.emit('message',{op:0,d:{rpcVersion:1,authentication:{salt:'abc',challenge:'def'}}});
 await assert.rejects(pending,/password required/i);
});

test('OBS adapter refuses a successful write ack when the actual program scene differs',async()=>{
 const pending=adapter().show(0,{scene:'Lyrics'});
 const {socket,sent}=await handshake();
 socket.emit('message',{op:7,d:{
   requestType:'SetCurrentProgramScene',requestId:sent.d.requestId,
   requestStatus:{result:true}
 }});
 const verify=socket.sent.at(-1);
 assert.equal(verify.d.requestType,'GetCurrentProgramScene');
 socket.emit('message',{op:7,d:{
   requestType:'GetCurrentProgramScene',requestId:verify.d.requestId,
   requestStatus:{result:true},responseData:{sceneName:'Welcome'}
 }});
 await assert.rejects(pending,/readback.*mismatch/i);
});

test('OBS readback failure does not count as a successful presentation change',async()=>{
 const pending=adapter().show(0,{scene:'Lyrics'});
 const {socket,sent}=await handshake();
 socket.emit('message',{op:7,d:{
   requestType:'SetCurrentProgramScene',requestId:sent.d.requestId,
   requestStatus:{result:true}
 }});
 const verify=socket.sent.at(-1);
 assert.equal(verify.d.requestType,'GetCurrentProgramScene');
 socket.emit('message',{op:7,d:{
   requestType:'GetCurrentProgramScene',requestId:verify.d.requestId,
   requestStatus:{result:false,code:602,comment:'Scene query unavailable'}
 }});
 await assert.rejects(pending,/Scene query unavailable/);
 assert.equal(socket.sent.filter(v=>v.d.requestType==='SetCurrentProgramScene').length,1);
});
