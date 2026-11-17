import test from 'node:test';
import assert from 'node:assert/strict';
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';
import {renderDeckHtml} from '../src/deck.mjs';

const token='presentation-clear-control-token-2026',viewerToken='presentation-clear-viewer-token-2026';
test('live event stream notifies a connected viewer when a stopped presentation is unloaded',
 {timeout:4500},async()=>{
 const handler=createMcpHandler();
 const server=createHttpServer({handler,token,viewerToken});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const base='http://127.0.0.1:'+server.address().port;
 const call=async(route,value)=>{
   const r=await fetch(base+route,{method:'POST',
     headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},
     body:JSON.stringify(value)});
   if(r.status!==200)throw new Error('Unexpected unload HTTP '+r.status+': '+await r.text());return r.json();
 };
 let reader=null;const abort=new AbortController();
 try{
   await call('/v1/load',{deck:{title:'Private lyric text',
     slides:[{id:'one',title:'Private material'},{id:'two',title:'Second slide'}]}});
   await call('/v1/start',{mode:'manual'});
   const res=await fetch(base+'/v1/view-events?key='+viewerToken,{signal:abort.signal});
   reader=res.body.getReader();
   let buffer='';
   const nextEvent=async()=>{
     for(let i=0;i<15;i++){
       const {value,done}=await Promise.race([
         reader.read(),
         new Promise((_,reject)=>setTimeout(()=>reject(Error('No viewer unload event.')),900))
       ]);
       if(done)throw Error('Viewer event stream ended.');
       buffer+=new TextDecoder().decode(value);
       const hit=buffer.match(/data: ([^\n]+)\n\n/);
       if(hit){buffer=buffer.slice(hit.index+hit[0].length);return JSON.parse(hit[1]);}
     }
     throw Error('No viewer state event received.');
   };
   const first=await nextEvent();
   assert.equal(first.loaded,true);
   await call('/v1/stop',{});
   await nextEvent();
   await call('/v1/unload',{});
   const cleared=await nextEvent();
   assert.equal(cleared.loaded,false);
   assert.equal(cleared.index,null);
   assert.equal(cleared.started,false);
 }finally{
   abort.abort();try{await reader?.cancel();}catch{}
   server.closeAllConnections();await new Promise(r=>server.close(r));
 }
});
test('live player removes sensitive slide DOM when the controller unloads',()=>{
 const html=renderDeckHtml({title:'private',slides:[{id:'one',text:'private lyric'}]},
   {liveEventsPath:'/v1/view-events?key=private-token-in-test',deckVersion:'deck-v1'});
 assert.match(html,/state\.loaded===false/);
 assert.match(html,/replaceChildren\(\)/);
 assert.match(html,/PRESENTATION CLEARED/);
});
