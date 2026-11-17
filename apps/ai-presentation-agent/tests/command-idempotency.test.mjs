import test from 'node:test';
import assert from 'node:assert/strict';
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';

const deck={slides:[{id:'first',title:'First'},{id:'second',title:'Second'},{id:'third',title:'Third'}]};
function rpc(id,name,args={}){return {jsonrpc:'2.0',id,method:'tools/call',params:{name,arguments:args}};}
const call=async(h,id,name,args={})=>{
 const res=await h(rpc(id,name,args));
 if(res.result.isError)throw Error(res.result.content?.[0]?.text??'Failed');
 return res.result.structuredContent;
};
test('idempotency key prevents duplicated next slide across simultaneous AI hosts',async()=>{
 const h=createMcpHandler();
 await call(h,1,'presentation_load',{deck});
 await call(h,2,'presentation_start',{mode:'automatic'});
 const [a,b]=await Promise.all([
   call(h,3,'presentation_command',{action:'next',idempotencyKey:'shared-next-1'}),
   call(h,4,'presentation_command',{idempotencyKey:'shared-next-1',action:'next'})
 ]);
 assert.deepEqual(a,b);
 assert.equal(a.slide.id,'second');
 const state=await call(h,5,'presentation_status');
 assert.equal(state.current.id,'second');
 const again=await call(h,6,'presentation_command',{action:'next',idempotencyKey:'shared-next-1'});
 assert.deepEqual(again,a);
 assert.equal((await call(h,7,'presentation_status')).current.id,'second');
});
test('reusing a key for a different command is rejected instead of performing it',async()=>{
 const h=createMcpHandler();
 await call(h,1,'presentation_load',{deck});
 await call(h,2,'presentation_start',{mode:'manual'});
 await call(h,3,'presentation_command',{action:'next',idempotencyKey:'key-2'});
 const denied=await h(rpc(4,'presentation_command',{action:'previous',idempotencyKey:'key-2'}));
 assert.equal(denied.result.isError,true);
 assert.match(denied.result.content[0].text,/idempotency|conflict/i);
 assert.equal((await call(h,5,'presentation_status')).current.id,'second');
});
test('command receipts reset when an intentional new deck is loaded',async()=>{
 const h=createMcpHandler();
 await call(h,1,'presentation_load',{deck});
 await call(h,2,'presentation_start',{mode:'manual'});
 await call(h,3,'presentation_command',{action:'next',idempotencyKey:'same-key'});
 await call(h,4,'presentation_load',{deck:{slides:[{id:'new'},{id:'new-two'}]}});
 await call(h,5,'presentation_start',{mode:'manual'});
 const after=await call(h,6,'presentation_command',{action:'next',idempotencyKey:'same-key'});
 assert.equal(after.slide.id,'new-two');
});
test('malformed idempotency keys are refused before external output changes',async()=>{
 const h=createMcpHandler();
 await call(h,1,'presentation_load',{deck});
 await call(h,2,'presentation_start',{mode:'manual'});
 const result=await h(rpc(3,'presentation_command',{action:'next',idempotencyKey:'../override'}));
 assert.equal(result.result.isError,true);
 assert.equal((await call(h,4,'presentation_status')).index,0);
});
test('independent authenticated HTTP clients can retry with an exact key safely',async()=>{
 const h=createMcpHandler();
 const server=createHttpServer({handler:h,token:'presentation-idempotency-test-secret'});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const origin='http://127.0.0.1:'+server.address().port;
 const post=async(path,payload)=>{
   const res=await fetch(origin+path,{method:'POST',headers:{
     Authorization:'Bearer presentation-idempotency-test-secret',
     'Content-Type':'application/json'},body:JSON.stringify(payload)});
   assert.equal(res.status,200);return res.json();
 };
 try{
   await post('/v1/load',{deck});
   await post('/v1/start',{mode:'automatic'});
   const request={action:'next',idempotencyKey:'host-client-command-555'};
   const outcomes=await Promise.all([post('/v1/command',request),post('/v1/command',request)]);
   assert.deepEqual(outcomes[0],outcomes[1]);
   const status=await (await fetch(origin+'/v1/status',{headers:{Authorization:'Bearer presentation-idempotency-test-secret'}})).json();
   assert.equal(status.current.id,'second');
 }finally{server.closeAllConnections();await new Promise(r=>server.close(r));}
});
