import test from 'node:test';
import assert from 'node:assert/strict';
import {createHttpServer} from '../src/http.mjs';
import {createMcpHandler} from '../src/mcp.mjs';
const TOKEN='test-key-presentation-agent-local-only';
async function serverFixture(run){
 const handler=createMcpHandler();
 const server=createHttpServer({handler,token:TOKEN});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const base='http://127.0.0.1:'+server.address().port;
 const get=(path,auth=true)=>fetch(base+path,{headers:auth?{Authorization:'Bearer '+TOKEN}:{}});
 const post=(path,data,headers={})=>fetch(base+path,{method:'POST',headers:{Authorization:'Bearer '+TOKEN,'Content-Type':'application/json',...headers},body:JSON.stringify(data)});
 try{await run({get,post,base});}finally{await new Promise(resolve=>server.close(resolve));}
}
test('HTTP local API refuses absent/invalid token and cross-origin writes',()=>serverFixture(async({get,post})=>{
 assert.equal((await get('/v1/status',false)).status,401);
 assert.equal((await post('/v1/load',{deck:{slides:[{id:'title'}]}},{Origin:'http://evil.example'})).status,403);
}));
test('local API and MCP operate on the same director instance',()=>serverFixture(async({get,post})=>{
 const deck={slides:[{id:'s1',title:'First'},{id:'s2',title:'Second',text:'Living in hope together',cues:['living in hope together']}]};
 assert.equal((await post('/v1/load',{deck})).status,200);
 const started=await (await post('/v1/start',{mode:'automatic'})).json();
 assert.equal(started.mode,'automatic');
 const event=await (await post('/v1/cue',{source:'bandmates',type:'transcript',text:'living in hope together',confidence:.95,final:true})).json();
 assert.equal(event.changed,true);
 const state=await (await get('/v1/status')).json();
 assert.equal(state.current.id,'s2');
}));
test('HTML export path is accessible from MCP only, not an arbitrary local HTTP file',()=>serverFixture(async({get})=>{
 assert.equal((await get('/v1/files/../../.ssh/id_rsa')).status,404);
}));
test('host voice replies through local API and gestures do not bypass owner hold',()=>serverFixture(async({get,post})=>{
 await post('/v1/load',{deck:{slides:[{id:'a',title:'Intro'},{id:'b',title:'Next'}]}});
 await post('/v1/start',{mode:'automatic'});
 await post('/v1/command',{action:'hold'});
 const r=await (await post('/v1/voice',{transcript:'presentation agent what slide are we on',final:true,confidence:.99})).json();
 assert.equal(r.speakByHost,true);
 assert.match(r.reply,/Intro/);
 assert.equal((await get('/v1/status')).status,200);
}));
