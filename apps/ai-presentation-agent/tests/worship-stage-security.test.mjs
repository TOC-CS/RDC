import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';

const file=fileURLToPath(new URL('../skills/ai-presentation-agent/worship/examples/sunday-service.json',import.meta.url));
const plan=JSON.parse(await readFile(file,'utf8'));
plan.items[0].notes='SECRET_PRE_SERVICE_OPERATOR_NOTE';
plan.items[1].notes='SECRET_WELCOME_OPERATOR_NOTE';
plan.items[2].sections[0].notes='SECRET_WORSHIP_MONITOR_NOTE';
const control='controller-fixture-private-2026';
const stage='stage-monitor-fixture-private-2026';
const audience='audience-view-fixture-private-2026';

async function fixture(){
 const handler=createMcpHandler({stageGrant:stage});
 const server=createHttpServer({handler,token:control,viewerToken:audience,stageToken:stage});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const base='http://127.0.0.1:'+server.address().port;
 const post=async(route,body)=>{
   const r=await fetch(base+route,{method:'POST',
     headers:{Authorization:'Bearer '+control,'Content-Type':'application/json'},
     body:JSON.stringify(body),signal:AbortSignal.timeout(2500)});
   return {status:r.status,text:await r.text()};
 };
 return {base,server,post};
}
const stop=async server=>{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));};
test('stage confidence has an independent viewer token; audience token and bearer cannot read private stage',async()=>{
 const {server,base,post}=await fixture();
 try{
   const loaded=await post('/v1/worship/load',{plan});
   assert.equal(loaded.status,200);
   for(const key of [audience,control,'wrong']){
     const r=await fetch(base+'/v1/stage?key='+encodeURIComponent(key));
     assert.equal(r.status,401,'Stage private auth must reject '+key.slice(0,10));
   }
   const authorized=await fetch(base+'/v1/stage?key='+encodeURIComponent(stage));
   assert.equal(authorized.status,200);
   const html=await authorized.text();
   assert.match(html,/Confidence/);
   assert.ok(!html.includes('SECRET_PRE_SERVICE_OPERATOR_NOTE'),
     'Initial stage HTML should obtain private data only through authenticated SSE');
   const publicPage=await (await fetch(base+'/v1/viewer?key='+audience)).text();
   assert.equal(publicPage.includes('SECRET_PRE_SERVICE_OPERATOR_NOTE'),false);
   assert.equal(publicPage.includes(stage),false);
   assert.equal(publicPage.includes('/v1/stage-events'),false);
   const bad=await fetch(base+'/v1/stage-events?key='+audience);
   assert.equal(bad.status,401);
 }finally{await stop(server);}
});
test('authorized stage SSE shows private notes and next lyric, updates on cue, clears after unload',async()=>{
 const {server,base,post}=await fixture();
 const ac=new AbortController();
 let reader=null,buffer='';
 try{
   await post('/v1/worship/load',{plan});
   const r=await fetch(base+'/v1/stage-events?key='+stage,{signal:ac.signal});
   assert.equal(r.status,200);
   reader=r.body.getReader();
   const decoder=new TextDecoder();
   const event=async()=>{
     for(let i=0;i<8;i++){
       const next=await Promise.race([reader.read(),
         new Promise((_,reject)=>setTimeout(()=>reject(new Error('Stage stream timed out.')),700))]);
       if(next.done)throw new Error('Stage stream closed');
       buffer+=decoder.decode(next.value);
       const match=buffer.match(/data: (.+)\n\n/);
       if(match){buffer=buffer.slice(match.index+match[0].length);return JSON.parse(match[1]);}
     }
     throw Error('No stage event');
   };
   const first=await event();
   assert.equal(first.current.notes,'SECRET_PRE_SERVICE_OPERATOR_NOTE');
   assert.equal(first.next.id,'welcome');
   await post('/v1/start',{mode:'manual'});
   await post('/v1/command',{action:'next'});
   let second;
   for(let i=0;i<3;i++){
     const next=await event();if(next.index===1){second=next;break;}
   }
   assert.equal(second.current.notes,'SECRET_WELCOME_OPERATOR_NOTE');
   await post('/v1/stop',{});
   await post('/v1/unload',{});
   let cleared;
   for(let i=0;i<4;i++){
     const next=await event();if(next.loaded===false){cleared=next;break;}
   }
   assert.equal(cleared.current,null);
   assert.equal(JSON.stringify(cleared).includes('SECRET'),false);
 }finally{
   ac.abort();try{await reader?.cancel();}catch{}
   await stop(server);
 }
});
test('stage viewer feature remains disabled when no separate stageToken is configured',async()=>{
 const handler=createMcpHandler({stageGrant:null});
 const server=createHttpServer({handler,token:control,viewerToken:audience});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try{
   const base='http://127.0.0.1:'+server.address().port;
   const r=await fetch(base+'/v1/stage?key='+stage);
   assert.equal(r.status,404);
 }finally{await stop(server);}
});
