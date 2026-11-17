import test from 'node:test';
import assert from 'node:assert/strict';
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';

const tokens={token:'local-output-control-test-2026',viewerToken:'audience-output-test-token-2026',
 stageToken:'private-stage-test-token-2026',streamToken:'public-stream-test-token-2026'};
const HIDDEN='UNANNOUNCED_PASTOR_STAGE_MESSAGE';
const TEXT='Original cue for both displays';
const plan={title:'Emergency Layer Isolation',items:[
 {id:'start',title:'Opening',type:'announcement',text:TEXT,notes:HIDDEN},
 {id:'finish',title:'Closing',type:'closing',text:'Closing'}
]};
const rpc=async(handler,id,name,args={})=>{
 const result=await handler({jsonrpc:'2.0',id,method:'tools/call',
   params:{name,arguments:args}});
 if(result.result?.isError)throw new Error(result.result.content[0].text);
 return result.result.structuredContent;
};
test('unprivileged AI host may observe visibility but cannot clear live output',async()=>{
 const h=createMcpHandler({stageGrant:tokens.stageToken});
 await rpc(h,1,'presentation_load_worship',{plan});
 const state=await rpc(h,2,'presentation_worship_visibility');
 assert.equal(state.outputs.find(x=>x.destination==='broadcast').mode,'visible');
 const result=await h({jsonrpc:'2.0',id:3,method:'tools/call',
  params:{name:'presentation_worship_visibility_set',
   arguments:{destination:'broadcast',mode:'clear'}}});
 assert.equal(result.result.isError,true);
 assert.match(result.result.content[0].text,/operator|grant/i);
 assert.equal((await rpc(h,4,'presentation_worship_visibility')).revision,0);
});
test('broadcast overlay clear does not change audience slide, private stage, OBS, or stream state',async()=>{
 const h=createMcpHandler({stageGrant:tokens.stageToken,allowWorshipLookChanges:true});
 await rpc(h,1,'presentation_load_worship',{plan});
 await rpc(h,2,'presentation_start',{mode:'manual'});
 const before=await rpc(h,3,'presentation_status');
 const clear=await rpc(h,4,'presentation_worship_visibility_set',{destination:'broadcast',mode:'clear'});
 assert.equal(clear.nativeDisplayWritesPerformed,false);
 assert.equal(clear.streamOrRecordChanged,false);
 assert.equal(h.getBroadcastCue().current.text,'');
 assert.equal(h.getBroadcastCue().visibility,'clear');
 assert.equal(h.getPrivateStageCue(tokens.stageToken).current.notes,HIDDEN);
 assert.equal(h.getAudienceLook().visibility,'visible');
 assert.deepEqual(await rpc(h,5,'presentation_status'),before);
 assert.equal((await rpc(h,6,'presentation_worship_visibility_set',{destination:'broadcast',mode:'visible'})).revision,2);
 assert.equal(h.getBroadcastCue().current.text,TEXT);
});
test('independent audience blank changes only audience viewer output, never native projector',async()=>{
 const h=createMcpHandler({stageGrant:tokens.stageToken,allowWorshipLookChanges:true});
 await rpc(h,1,'presentation_load_worship',{plan});
 await rpc(h,2,'presentation_worship_visibility_set',{destination:'audience',mode:'blank'});
 assert.equal(h.getAudienceLook().visibility,'blank');
 assert.equal(h.getBroadcastCue().visibility,'visible');
 assert.equal(h.getBroadcastCue().current.text,TEXT);
 assert.equal(h.getPrivateStageCue(tokens.stageToken).current.notes,HIDDEN);
});
test('stage clear hides notes and next cue but cannot clear broadcast or public slide',async()=>{
 const h=createMcpHandler({stageGrant:tokens.stageToken,allowWorshipLookChanges:true});
 await rpc(h,1,'presentation_load_worship',{plan});
 await rpc(h,2,'presentation_worship_visibility_set',{destination:'stage',mode:'clear'});
 assert.equal(h.getPrivateStageCue(tokens.stageToken).current.notes,'');
 assert.equal(h.getPrivateStageCue(tokens.stageToken).next,null);
 assert.equal(h.getBroadcastCue().current.text,TEXT);
 const stageLook=h.getWorshipLook('stage',tokens.stageToken);
 assert.equal(JSON.stringify(stageLook).includes(HIDDEN),false);
});
test('independent HTTP visibility controls require operator bearer, configured owner grant and exact schema',async()=>{
 const h=createMcpHandler({stageGrant:tokens.stageToken,allowWorshipLookChanges:true});
 const server=createHttpServer({handler:h,...tokens});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const base='http://127.0.0.1:'+server.address().port;
 const post=async(path,payload,token=null)=>{
   const response=await fetch(base+path,{method:'POST',headers:{
     'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{})
   },body:JSON.stringify(payload)});
   return {status:response.status,body:await response.json()};
 };
 try{
  await post('/v1/worship/load',{plan},tokens.token);
  assert.equal((await post('/v1/worship/visibility/broadcast',{mode:'clear'})).status,401);
  assert.equal((await post('/v1/worship/visibility/broadcast',{mode:'clear',extra:'secret'},tokens.token)).status,400);
  assert.equal((await post('/v1/worship/visibility/broadcast',{mode:'clear'},tokens.token)).status,200);
  assert.equal(h.getBroadcastCue().visibility,'clear');
  assert.equal((await post('/v1/worship/visibility/stage',{mode:'blank'},tokens.token)).status,422);
  const stage=await fetch(base+'/v1/stage?key='+tokens.stageToken);
  assert.equal(stage.status,200);
 }finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});
test('unload and new deck clear all output curtains, including when source has private notes',async()=>{
 const h=createMcpHandler({stageGrant:tokens.stageToken,allowWorshipLookChanges:true});
 await rpc(h,1,'presentation_load_worship',{plan});
 await rpc(h,2,'presentation_worship_visibility_set',{destination:'audience',mode:'blank'});
 await rpc(h,3,'presentation_worship_visibility_set',{destination:'broadcast',mode:'clear'});
 await rpc(h,4,'presentation_unload');
 assert.equal(h.getBroadcastCue(),null);
 await rpc(h,5,'presentation_load_worship',{plan});
 assert.equal(h.getAudienceLook().visibility,'visible');
 assert.equal(h.getBroadcastCue().visibility,'visible');
});
