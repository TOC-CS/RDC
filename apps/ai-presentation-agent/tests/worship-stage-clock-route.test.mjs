import test from 'node:test';
import assert from 'node:assert/strict';
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';
import {WorshipStageClock} from '../src/worship-timing.mjs';

const control='owner-stage-clock-test-control-token-2026';
const stage='owner-stage-clock-test-private-token-2026';
const stream='owner-stage-clock-test-stream-token-2026';
const audience='owner-stage-clock-test-audience-token-2026';
const secretLabel='PRIVATE_PASTOR_SERMON_CLOCK_ONLY';
const plan={title:'Service',items:[
  {id:'welcome',type:'announcement',title:'Welcome',text:'Welcome',notes:'PASTOR_PRIVATE_MESSAGE'}
]};
async function scenario(enabled,fn){
 let now=10000;
 const clock=new WorshipStageClock({clock:()=>now});
 const handler=createMcpHandler({
   stageGrant:stage,stageClock:clock,allowStageClockControl:enabled
 });
 const server=createHttpServer({handler,token:control,stageToken:stage,
   streamToken:stream,viewerToken:audience});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const base='http://127.0.0.1:'+server.address().port;
 const call=async(name,args={})=>{
   const resp=await handler({jsonrpc:'2.0',id:1,method:'tools/call',
     params:{name,arguments:args}});
   if(resp?.result?.isError)throw new Error(resp.result.content[0].text);
   return resp.result.structuredContent;
 };
 const post=async(path,body,opts={})=>{
   const resp=await fetch(base+path,{method:'POST',
     headers:{Authorization:'Bearer '+(opts.token??control),'Content-Type':'application/json',
       ...(opts.stage?{'X-Stage-Credential':opts.stage}:{})},
     body:JSON.stringify(body)});
   return {status:resp.status,body:await resp.json()};
 };
 const get=async(path,key)=>{
   const resp=await fetch(base+path+'?key='+encodeURIComponent(key));
   return {status:resp.status,body:await resp.json()};
 };
 try{await fn({handler,base,call,post,get,setNow:v=>now=v});}
 finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
}
test('separate operator and private stage credential are both needed to configure the stage timer',()=>scenario(true,async({call,post,get})=>{
 await call('presentation_load_worship',{plan});
 assert.equal((await post('/v1/stage/clock',{action:'configure',label:secretLabel,durationMs:60000})).status,401);
 assert.equal((await post('/v1/stage/clock',{action:'configure',label:secretLabel,durationMs:60000},{stage:audience})).status,401);
 const accepted=await post('/v1/stage/clock',{action:'configure',label:secretLabel,durationMs:60000},{stage});
 assert.equal(accepted.status,200);
 assert.equal(accepted.body.label,secretLabel);
 assert.equal((await get('/v1/stage/clock',audience)).status,401);
 assert.equal((await get('/v1/stage/clock',stage)).body.label,secretLabel);
}));
test('stage clock starts, pauses and resumes on monotonically increasing time without advancing slides',()=>scenario(true,async({call,post,get,setNow})=>{
 await call('presentation_load_worship',{plan});
 const before=await call('presentation_status');
 await post('/v1/stage/clock',{action:'configure',label:secretLabel,durationMs:60000},{stage});
 await post('/v1/stage/clock',{action:'start'},{stage});
 setNow(14500);
 const active=await get('/v1/stage/clock',stage);
 assert.equal(active.body.remainingMs,55500);
 await post('/v1/stage/clock',{action:'pause'},{stage});
 setNow(24400);
 assert.equal((await get('/v1/stage/clock',stage)).body.remainingMs,55500);
 await post('/v1/stage/clock',{action:'resume'},{stage});
 setNow(30000);
 assert.equal((await get('/v1/stage/clock',stage)).body.remainingMs,49900);
 const after=await call('presentation_status');
 assert.deepEqual(before,after);
}));
test('no timer content appears in public status, audience, broadcast Look, stream SSE, or rundown',()=>scenario(true,async({call,post,get,base})=>{
 await call('presentation_load_worship',{plan});
 await post('/v1/stage/clock',{action:'configure',label:secretLabel,durationMs:60000},{stage});
 const privateState=await get('/v1/stage/clock',stage);
 assert.equal(privateState.body.label,secretLabel);
 const publicReads=[
   await call('presentation_status'),
   await call('presentation_worship_rundown'),
   await get('/v1/look/audience',audience),
   await get('/v1/look/broadcast',stream),
   await (await fetch(base+'/v1/viewer?key='+audience)).text(),
   await (await fetch(base+'/v1/stream-overlay?key='+stream)).text()
 ];
 for(const read of publicReads)assert.equal(JSON.stringify(read).includes(secretLabel),false);
 const privateCue=await get('/v1/stage/clock',stage);
 assert.equal(privateCue.status,200);
}));
test('timer mutation without local stage-clock operator grant is refused, even with both bearer credentials',()=>scenario(false,async({call,post,get})=>{
 await call('presentation_load_worship',{plan});
 const denied=await post('/v1/stage/clock',{action:'configure',label:secretLabel,durationMs:60000},{stage});
 assert.equal(denied.status,422);
 assert.match(JSON.stringify(denied.body),/operator|grant/i);
 assert.equal((await get('/v1/stage/clock',stage)).body.label,'');
}));
test('loading new service or unload clears previous stage timer label and seconds',()=>scenario(true,async({call,post,get})=>{
 await call('presentation_load_worship',{plan});
 await post('/v1/stage/clock',{action:'configure',label:secretLabel,durationMs:60000},{stage});
 await post('/v1/stage/clock',{action:'start'},{stage});
 await call('presentation_unload');
 assert.notEqual((await get('/v1/stage/clock',stage)).status,200);
 await call('presentation_load_worship',{plan});
 const restored=await get('/v1/stage/clock',stage);
 assert.equal(restored.status,200);
 assert.equal(restored.body.label,'');
 assert.equal(restored.body.durationMs,0);
 assert.equal(restored.body.running,false);
}));
test('stopping a worship service pauses the private stage countdown without changing external output',()=>scenario(true,async({call,post,get,setNow})=>{
 await call('presentation_load_worship',{plan});
 await call('presentation_start',{mode:'manual'});
 await post('/v1/stage/clock',{action:'configure',label:secretLabel,durationMs:60000},{stage});
 await post('/v1/stage/clock',{action:'start'},{stage});
 setNow(17000);
 await call('presentation_stop');
 const stopped=await get('/v1/stage/clock',stage);
 assert.equal(stopped.status,200);
 assert.equal(stopped.body.paused,true);
 assert.equal(stopped.body.running,false);
 assert.equal(stopped.body.remainingMs,53000);
 const presentation=await call('presentation_status');
 assert.equal(presentation.started,false);
 assert.equal(presentation.armed,false);
 assert.equal(JSON.stringify(presentation).includes(secretLabel),false);
}));
