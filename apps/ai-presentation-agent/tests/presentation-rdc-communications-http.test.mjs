import test from 'node:test';
import assert from 'node:assert/strict';
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';

const operator='operator-rdc-communication-test-token-2026';
const viewer='audience-rdc-communication-view-token-2026';
const stage='stage-rdc-communication-view-token-2026';
const stream='stream-rdc-communication-view-token-2026';
const PRIVATE='PRIVATE_STAGE_CHORDS_AND_SERMON_NOTES';
const room={localSessionId:'presentation-fixture',
 roomMembers:['presentation-fixture','rdc-fixture','bandmates-fixture'],
 roomKey:'toc-service-room',requestId:'status-request-1'};
const plan={title:'Original Worship',items:[{
 id:'opening',type:'announcement',title:'Welcome',text:'Public welcome',notes:PRIVATE
}]};
const rpc=(name,args={})=>({jsonrpc:'2.0',id:1,method:'tools/call',
 params:{name,arguments:args}});
async function call(h,name,args={}){
 const r=await h(rpc(name,args));
 if(r?.result?.isError)throw new Error(r.result.content[0].text);
 return r.result.structuredContent;
}

test('presentation AI exposes explicitly inert two/three-way room capabilities and safe status draft',async()=>{
 const handler=createMcpHandler({stageGrant:stage});
 await call(handler,'presentation_load_worship',{plan});
 const baseline=await call(handler,'presentation_status');
 const caps=await call(handler,'presentation_communication_capabilities');
 assert.equal(caps.schema,'toc.presentation.rdc-communications-capabilities/v1');
 assert.equal(caps.liveConnected,false);
 assert.equal(caps.directChatPushAllowed,false);
 assert.equal(caps.crossProjectEnrollmentVerified,false);
 assert.equal(caps.roomSizes.includes(3),true);
 assert.equal(caps.existingAtlasBusRequired,true);
 const preview=await call(handler,'presentation_communication_prepare',room);
 assert.equal(preview.roomSize,3);
 assert.equal(preview.applied,false);
 assert.equal(preview.expectedRecipients.length,2);
 assert.equal(preview.requiresAuthenticatedRdcBinding,true);
 assert.equal(JSON.parse(preview.text).slideId,'opening');
 assert.equal(JSON.stringify(preview).includes(PRIVATE),false);
 assert.deepEqual(await call(handler,'presentation_status'),baseline);
 assert.ok(!(await handler({jsonrpc:'2.0',id:2,method:'tools/list'})).result.tools
  .some(x=>x.name==='presentation_communication_send'));
});

test('operator-only HTTP room preview denies audience, stage and broadcast tokens without changing outputs',async()=>{
 const handler=createMcpHandler({stageGrant:stage});
 const server=createHttpServer({handler,token:operator,viewerToken:viewer,
  stageToken:stage,streamToken:stream});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const base='http://127.0.0.1:'+server.address().port;
 const body=JSON.stringify(room);
 const post=async credential=>fetch(base+'/v1/communications/prepare',{
  method:'POST',headers:{'Content-Type':'application/json',
   ...(credential?{Authorization:'Bearer '+credential}:{})},
  body
 });
 try{
  await call(handler,'presentation_load_worship',{plan});
  const before=await call(handler,'presentation_status');
  for(const cred of [null,viewer,stage,stream,'wrong']){
   assert.equal((await post(cred)).status,401);
  }
  assert.equal((await fetch(base+'/v1/communications/capabilities')).status,401);
  const caps=await fetch(base+'/v1/communications/capabilities',{
   headers:{Authorization:'Bearer '+operator}});
  assert.equal(caps.status,200);
  assert.equal((await caps.json()).liveConnected,false);
  const result=await post(operator);
  assert.equal(result.status,200);
  const draft=await result.json();
  assert.equal(draft.roomSize,3);
  assert.equal(draft.applied,false);
  assert.equal(JSON.stringify(draft).includes(PRIVATE),false);
  const invalid={...room,roomMembers:['presentation-fixture']};
  const rejected=await fetch(base+'/v1/communications/prepare',{
   method:'POST',headers:{'Content-Type':'application/json',
    Authorization:'Bearer '+operator},body:JSON.stringify(invalid)});
  assert.equal(rejected.status,422);
  assert.deepEqual(await call(handler,'presentation_status'),before);
 }finally{
  server.closeAllConnections();
  await new Promise(resolve=>server.close(resolve));
 }
});
