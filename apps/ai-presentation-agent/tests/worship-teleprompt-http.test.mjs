import test from 'node:test';
import assert from 'node:assert/strict';
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';
import {WorshipTeleprompter} from '../src/worship-teleprompt.mjs';

const operator='operator-controller-token-for-teleprompt-2026';
const stage='stage-independent-token-for-teleprompt-2026';
const viewer='audience-independent-token-for-teleprompt-2026';
const stream='stream-independent-token-for-teleprompt-2026';
const PRIVATE='PRIVATE_PASTOR_TELEPROMPT_SCRIPT_ONLY_FOR_STAGE';
const LINES='We sing together today\nWe lift our voices higher\nWe give thanks together';
const plan={title:'Original Teleprompt Rehearsal',items:[
 {id:'worship',type:'song',title:'Original Song',
  rights:{source:'original',displayAuthorized:true,streamAuthorized:false},
  sections:[{label:'chorus',lines:LINES.split('\n'),notes:PRIVATE}],
  order:['chorus','chorus']}
]};
const rpc=(name,args={})=>({jsonrpc:'2.0',id:1,method:'tools/call',params:{name,arguments:args}});
async function call(h,name,args={}){
 const x=await h(rpc(name,args));
 if(x?.result?.isError)throw new Error(x.result.content[0].text);
 return x.result.structuredContent;
}
async function fixture(enabled,fn){
 const teleprompter=new WorshipTeleprompter({clock:()=>10000});
 const handler=createMcpHandler({stageGrant:stage,teleprompter,
  allowTelepromptControl:enabled});
 const server=createHttpServer({handler,token:operator,viewerToken:viewer,
  stageToken:stage,streamToken:stream});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const base='http://127.0.0.1:'+server.address().port;
 const post=(body,{bearer=operator,stageCredential=stage}={})=>fetch(base+'/v1/stage/teleprompt',{
  method:'POST',headers:{'Content-Type':'application/json',
   ...(bearer?{Authorization:'Bearer '+bearer}:{}),
   ...(stageCredential?{'X-Stage-Credential':stageCredential}:{})},
  body:JSON.stringify(body)
 });
 try{await call(handler,'presentation_load_worship',{plan});await fn({handler,base,post});}
 finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
}

test('independent stage token is required to read private speaker prompt; audience and stream never receive it',()=>{
 return fixture(true,async({handler,base})=>{
  for(const key of [viewer,stream,operator,'wrong']){
   assert.equal((await fetch(base+'/v1/stage/teleprompt?key='+key)).status,401);
  }
  const authorized=await fetch(base+'/v1/stage/teleprompt?key='+stage);
  assert.equal(authorized.status,200);
  const prompt=await authorized.json();
  assert.equal(prompt.loaded,true);
  assert.equal(prompt.role,'speaker');
  assert.equal(prompt.current,PRIVATE);
  assert.equal(prompt.automaticSlideAdvance,false);
  const audience=await fetch(base+'/v1/look/audience?key='+viewer);
  const streamLook=await fetch(base+'/v1/look/broadcast?key='+stream);
  assert.equal(audience.status,200);assert.equal(streamLook.status,200);
  for(const rendered of [await audience.text(),await streamLook.text(),
   JSON.stringify(await call(handler,'presentation_status')),
   JSON.stringify(await call(handler,'presentation_worship_rundown'))]){
    assert.equal(rendered.includes(PRIVATE),false);
    assert.equal(rendered.includes('teleprompt'),false);
  }
 });
});

test('mutating private prompt requires both operator bearer, stage credential and explicit startup grant',()=>{
 return fixture(true,async({handler,base,post})=>{
  for(const opts of [
   {bearer:null},{bearer:viewer},{bearer:stage},{bearer:stream},
   {stageCredential:null},{stageCredential:viewer},{stageCredential:operator}
  ]){
   const denied=await post({action:'next'},opts);
   assert.equal(denied.status,401);
  }
  const before=await call(handler,'presentation_status');
  const changed=await post({action:'configure',role:'singer',
   fontScale:1.5,scrollSpeed:1.25,mirrored:true});
  assert.equal(changed.status,200);
  const data=await changed.json();
  assert.equal(data.role,'singer');
  assert.equal(data.mirrored,true);
  assert.equal(data.current,'We sing together today');
  const follow=await post({action:'follow',text:'We lift our voices higher',
   final:true,confidence:.98,eventId:'confirmed-asr-2',timestamp:10000});
  assert.equal(follow.status,200);
  const advanced=await follow.json();
  assert.equal(advanced.position,1);
  assert.equal(advanced.current,'We lift our voices higher');
  const hold=await post({action:'hold'});
  assert.equal((await hold.json()).held,true);
  const suspended=await post({action:'follow',text:'We give thanks together',
   final:true,confidence:.98,eventId:'held-asr-3',timestamp:10000});
  assert.equal((await suspended.json()).position,1);
  // A three-line song is paginated: the singer's prompt cannot run ahead
  // onto text belonging to the next physical slide.
  assert.equal((await (await post({action:'next'})).json()).position,1);
  assert.equal((await call(handler,'presentation_status')).index,before.index);
  assert.equal((await call(handler,'presentation_status')).started,false);
  const stageView=await fetch(base+'/v1/stage/teleprompt?key='+stage);
  assert.equal((await stageView.json()).current,'We lift our voices higher');
  await call(handler,'presentation_unload');
  assert.equal((await fetch(base+'/v1/stage/teleprompt?key='+stage)).status,409);
 });
});

test('unapproved teleprompt launch and malformed actions cannot change stage or public output',()=>{
 return fixture(false,async({handler,base,post})=>{
  const before=await call(handler,'presentation_status');
  assert.equal((await post({action:'next'})).status,422);
  assert.equal((await post({action:'configure',role:'speaker',fontScale:999})).status,422);
  assert.equal((await post({action:'follow',text:PRIVATE,confidence:1,final:true,eventId:'x',timestamp:10000})).status,422);
  assert.equal((await post({action:'stream-start'})).status,422);
  assert.deepEqual(await call(handler,'presentation_status'),before);
  assert.equal((await fetch(base+'/v1/stage/teleprompt?key='+stage)).status,200);
 });
});
