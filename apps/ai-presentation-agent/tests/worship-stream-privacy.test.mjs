import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';

const src=fileURLToPath(new URL('../skills/ai-presentation-agent/worship/examples/sunday-service.json',import.meta.url));
const plan=JSON.parse(await readFile(src,'utf8'));
const secret='PRIVATE_PASTOR_NOTES_FOR_STAGE_ONLY';
plan.items[0].notes=secret;
plan.items[2].sections[0].notes=secret;
const control='production-controller-test-secret';
const audience='production-audience-test-secret';
const stage='production-stage-test-secret';
const stream='production-stream-test-secret';

async function fixture(){
 const handler=createMcpHandler({stageGrant:stage});
 const server=createHttpServer({handler,token:control,
   viewerToken:audience,stageToken:stage,streamToken:stream});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const base='http://127.0.0.1:'+server.address().port;
 const post=async(path,value)=>{
   const response=await fetch(base+path,{method:'POST',headers:{
     Authorization:'Bearer '+control,'Content-Type':'application/json'},
     body:JSON.stringify(value),signal:AbortSignal.timeout(2500)});
   if(response.status!==200)throw Error('Stream fixture control rejected HTTP '+response.status+': '+await response.text());
   return response.json();
 };
 return {handler,server,base,post};
}
const close=async server=>{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));};
test('stream Browser Source requires a separate read-only token; all public paths exclude stage information',async()=>{
 const {server,base,post}=await fixture();
 try{
   await post('/v1/worship/load',{plan});
   for(const wrong of [audience,stage,control,'wrong']){
     const reply=await fetch(base+'/v1/stream-overlay?key='+wrong);
     assert.equal(reply.status,401);
   }
   const right=await fetch(base+'/v1/stream-overlay?key='+stream);
   assert.equal(right.status,200);
   const html=await right.text();
   assert.match(html,/transparent/i);
   assert.match(html,/EventSource/);
   assert.equal(html.includes(secret),false);
   assert.equal(html.includes(stage),false);
   assert.equal(html.includes(control),false);
   const privateStage=await fetch(base+'/v1/stage?key='+stream);
   assert.equal(privateStage.status,401);
   const denied=await fetch(base+'/v1/stream-events?key='+audience);
   assert.equal(denied.status,401);
 }finally{await close(server);}
});
test('stream SSE only receives authorized public cue fields and clears on unload',async()=>{
 const {server,base,post}=await fixture();
 const ac=new AbortController();let reader=null,buffer='';
 try{
   await post('/v1/worship/load',{plan});
   const response=await fetch(base+'/v1/stream-events?key='+stream,{signal:ac.signal});
   assert.equal(response.status,200);
   reader=response.body.getReader();
   const decoder=new TextDecoder();
   async function next(){
     for(let j=0;j<10;j++){
       const next=await Promise.race([reader.read(),
         new Promise((_,reject)=>setTimeout(()=>reject(new Error('stream cue timed out')),650))]);
       if(next.done)throw new Error('Stream cue unexpectedly closed');
       buffer+=decoder.decode(next.value);
       const match=buffer.match(/data: (.+)\n\n/);
       if(match){buffer=buffer.slice(match.index+match[0].length);return JSON.parse(match[1]);}
     }
     throw Error('No stream cue');
   }
   const first=await next();
   assert.equal(first.loaded,true);
   assert.equal(first.current.title,'Service Begins Soon');
   assert.equal(JSON.stringify(first).includes(secret),false);
   assert.equal('chords' in first.current,false);
   await post('/v1/start',{mode:'manual'});
   await post('/v1/command',{action:'next'});
   let moved=null;
   for(let i=0;i<4;i++){let value=await next();if(value.index===1){moved=value;break;}}
   assert.equal(moved.current.id,'welcome');
   await post('/v1/stop',{});
   await post('/v1/unload',{});
   let cleared=null;
   for(let i=0;i<5;i++){let value=await next();if(value.loaded===false){cleared=value;break;}}
   assert.equal(cleared.current,null);
   assert.equal(JSON.stringify(cleared).includes(secret),false);
 }finally{ac.abort();try{await reader?.cancel();}catch{}await close(server);}
});
test('stream overlays remain disabled by default and do not authorize OBS streaming',async()=>{
 const handler=createMcpHandler();
 const server=createHttpServer({handler,token:control,viewerToken:audience});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try{
   const base='http://127.0.0.1:'+server.address().port;
   assert.equal((await fetch(base+'/v1/stream-overlay?key='+stream)).status,404);
 }finally{await close(server);}
});
