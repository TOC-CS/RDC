import test from 'node:test';
import assert from 'node:assert/strict';
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';
const CONTROL='owner-control-secret-token-2026';
const AUDIENCE='audience-only-secret-token-2026';
const STAGE='stage-only-secret-token-2026';
const STREAM='broadcast-only-secret-token-2026';
const SECRET='PRIVATE_PASTOR_MESSAGE_FOR_STAGE_ONLY';
const LYRICS='ORIGINAL_UNLICENSED_FOR_STREAM_TEST_LYRICS';
const plan={
 title:'Worship Look Demo',items:[
  {id:'prayer',type:'prayer',title:'Prayer',text:'Prayer Time',notes:SECRET},
  {id:'song',type:'song',title:'Original Song',
    rights:{source:'original',displayAuthorized:true,streamAuthorized:false},
    sections:[{label:'chorus',lines:[LYRICS],chords:['C#m'],notes:SECRET}],
    order:['chorus']}
 ]
};
async function fixture(fn){
 const handler=createMcpHandler({stageGrant:STAGE});
 const server=createHttpServer({handler,token:CONTROL,viewerToken:AUDIENCE,
   stageToken:STAGE,streamToken:STREAM});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const base='http://127.0.0.1:'+server.address().port;
 const post=async(path,body)=>{
   const r=await fetch(base+path,{method:'POST',
     headers:{Authorization:'Bearer '+CONTROL,'Content-Type':'application/json'},
     body:JSON.stringify(body)});
   return {status:r.status,body:await r.json()};
 };
 const get=async(path,key)=>{
   const r=await fetch(base+path+'?key='+encodeURIComponent(key));
   return {status:r.status,body:await r.json()};
 };
 try{await fn({handler,base,post,get});}
 finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
}
test('HTTP endpoint Look permissions isolate audience, stage and broadcast payloads by independent token',()=>fixture(async({post,get})=>{
 const loaded=await post('/v1/worship/load',{plan});
 assert.equal(loaded.status,200);
 for(const [route,allowed] of [
  ['/v1/look/audience',AUDIENCE],
  ['/v1/look/stage',STAGE],
  ['/v1/look/broadcast',STREAM]
 ]){
   for(const key of [AUDIENCE,STAGE,STREAM,CONTROL,'invalid']){
     const value=await get(route,key);
     assert.equal(value.status,key===allowed?200:401,route+': '+key.slice(0,6));
   }
 }
 const room=await get('/v1/look/audience',AUDIENCE);
 const stage=await get('/v1/look/stage',STAGE);
 const broadcast=await get('/v1/look/broadcast',STREAM);
 assert.equal(room.body.destination,'audience');
 assert.equal(stage.body.destination,'stage');
 assert.equal(broadcast.body.destination,'broadcast');
 assert.match(stage.body.layers.notes,/PRIVATE_PASTOR/);
 for(const value of [room.body,broadcast.body]){
   const text=JSON.stringify(value);
   assert.equal(text.includes(SECRET),false);
   assert.equal(text.includes('C#m'),false);
   assert.equal(text.includes(STAGE),false);
 }
 await post('/v1/start',{mode:'manual'});
 await post('/v1/command',{action:'next'});
 const audienceLyric=await get('/v1/look/audience',AUDIENCE);
 const broadcastLyric=await get('/v1/look/broadcast',STREAM);
 assert.equal(audienceLyric.body.layers.text,LYRICS);
 assert.equal(broadcastLyric.body.layers.text,'');
}));
test('worship Look endpoints do not expose stale private stage data after unload or non-worship replacement',()=>fixture(async({post,get})=>{
 await post('/v1/worship/load',{plan});
 assert.equal((await get('/v1/look/stage',STAGE)).status,200);
 await post('/v1/unload',{});
 assert.equal((await get('/v1/look/stage',STAGE)).status,409);
 assert.equal((await get('/v1/look/audience',AUDIENCE)).status,409);
 assert.equal((await get('/v1/look/broadcast',STREAM)).status,409);
 await post('/v1/load',{deck:{slides:[{id:'safe',text:'Public regular deck'}]}});
 assert.equal((await get('/v1/look/stage',STAGE)).status,409);
}));
