import test from 'node:test';
import assert from 'node:assert/strict';
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';
import {WorshipStageClock} from '../src/worship-timing.mjs';

test('private stage SSE advances an active timer independently of presentation cues and never leaks to the public stream',
 {timeout:8000},async()=>{
 const auth={
   token:'owner-control-stage-sse-test-2026',
   stageToken:'private-stage-sse-authentication-2026',
   viewerToken:'public-audience-stage-sse-test-2026',
   streamToken:'public-stream-stage-sse-test-2026'
 };
 let ms=15000;
 const clock=new WorshipStageClock({clock:()=>ms});
 const handler=createMcpHandler({
   stageGrant:auth.stageToken,allowStageClockControl:true,stageClock:clock
 });
 const invoke=async(name,args={})=>{
   const reply=await handler({jsonrpc:'2.0',id:1,method:'tools/call',params:{name,arguments:args}});
   if(reply?.result?.isError)throw new Error(reply.result.content[0].text);
   return reply?.result?.structuredContent;
 };
 await invoke('presentation_load_worship',{plan:{title:'Test',items:[
   {id:'one',type:'announcement',title:'Welcome',text:'Welcome',
     notes:'PRIVATE_PASTOR_STAGE_CLOCK_TEST'}
 ]}});
 const server=createHttpServer({handler,...auth});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const base='http://127.0.0.1:'+server.address().port;
 const abort=new AbortController();
 let reader=null,buffer='';
 const decode=new TextDecoder();
 const receive=async()=>{
   while(true){
     const next=await Promise.race([reader.read(),
       new Promise((_,reject)=>setTimeout(()=>reject(new Error('Timer SSE event timeout')),2300))]);
     if(next.done)throw new Error('Private timer SSE closed.');
     buffer+=decode.decode(next.value);
     const match=buffer.match(/data: (.+)\n\n/);
     if(match){buffer=buffer.slice(match.index+match[0].length);return JSON.parse(match[1]);}
   }
 };
 try{
   const response=await fetch(base+'/v1/stage-events?key='+auth.stageToken,{signal:abort.signal});
   assert.equal(response.status,200);
   reader=response.body.getReader();
   const initial=await receive();
   assert.equal(initial.loaded,true);
   assert.equal(initial.clock.label,'');
   handler.updatePrivateStageClock(auth.stageToken,{
     action:'configure',label:'PRIVATE_CLOCK_DO_NOT_STREAM',durationMs:10000
   });
   let configured=await receive();
   assert.equal(configured.clock.label,'PRIVATE_CLOCK_DO_NOT_STREAM');
   assert.equal(configured.clock.remainingMs,10000);
   handler.updatePrivateStageClock(auth.stageToken,{action:'start'});
   const started=await receive();
   assert.equal(started.clock.running,true);
   ms+=2600;
   // There were no presentation or OBS commands, only independent timer ticks.
   const later=await receive();
   assert.ok(later.clock.remainingMs<=7400,later.clock.remainingMs);
   const status=await invoke('presentation_status');
   assert.equal(status.index,0);
   assert.equal(status.started,false);
   assert.equal(JSON.stringify(status).includes('PRIVATE_CLOCK_DO_NOT_STREAM'),false);
   const broadcast=handler.getBroadcastCue();
   assert.equal(JSON.stringify(broadcast).includes('PRIVATE_CLOCK_DO_NOT_STREAM'),false);
   assert.equal(broadcast.current.id,'one');
 }finally{
   abort.abort();
   try{await reader?.cancel();}catch{}
   server.closeAllConnections();
   await new Promise(resolve=>server.close(resolve));
 }
});
