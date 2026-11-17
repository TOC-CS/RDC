import test from 'node:test';
import assert from 'node:assert/strict';
import {PresentationDirector} from '../src/director.mjs';
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';

const deck={title:'Uncertain-start regression',slides:[{id:'opening',title:'Opening'},{id:'next',title:'Next'}]};

function assertFaulted(director){
 const state=director.snapshot();
 assert.equal(state.started,false,'Startup must never claim running after an unverified native commit.');
 assert.equal(state.armed,false,'Native output must be disarmed on unknown commit.');
 assert.equal(state.held,true,'Presentation must hold when external output is unverified.');
 assert.equal(state.outputFaulted,true,'Physical output fault must latch.');
 assert.equal(state.outputFaultReason,'native_start_unverified');
 assert.equal(state.index,0,'Presentation index must not advance on unknown native startup.');
}

test('P1: show committed then threw: fault latches, viewer notified and no duplicate retry is possible',async()=>{
 let writes=0,actualOutput=null;
 const adapter={name:'committed-then-timeout',external:true,
  async show(index){writes++;actualOutput=index;throw new Error('timeout after simulated external commit');}
 };
 const director=new PresentationDirector({adapter});
 const observed=[];
 director.subscribe(snapshot=>observed.push({
  faulted:snapshot.outputFaulted,held:snapshot.held,armed:snapshot.armed,started:snapshot.started
 }));
 director.load(deck);
 await director.arm(true);
 await assert.rejects(()=>director.start('automatic'),/timeout after simulated external commit/);
 assert.equal(writes,1);assert.equal(actualOutput,0);
 assertFaulted(director);
 assert.ok(observed.some(x=>x.faulted===true&&x.held===true&&x.armed===false&&x.started===false),
  'Subscribing viewer must receive the output fault even though index remains unchanged.');
 await assert.rejects(()=>director.start('automatic'),/fault|reload|resync/i);
 await assert.rejects(()=>director.arm(true),/fault|reload|resync/i);
 assert.equal(writes,1,'An uncertain native start must never be repeated without an explicit reload.');
 director.load(deck);
 assert.equal(director.snapshot().outputFaulted,false);
 assert.equal(director.snapshot().armed,false,'Reload must never silently rearm external output.');
 assert.equal(director.snapshot().started,false);
});

test('P1: concurrent and queued starts after commit-then-timeout cannot replay native output',async()=>{
 let writes=0,release;
 let entered;
 const enteredPromise=new Promise(resolve=>{entered=resolve;});
 const adapter={name:'slow-uncertain',external:true,
  async show(){
   writes++;
   if(writes>1)throw new Error('unexpected duplicate native show after uncertain start');
   entered();
   return await new Promise((_,reject)=>{
     release=()=>reject(new Error('write may have completed before timeout'));
   });
  }
 };
 const director=new PresentationDirector({adapter});
 director.load(deck);await director.arm(true);
 const first=director.start('automatic');
 const second=director.start('automatic');
 const third=director.start('automatic');
 const concurrentRearm=director.arm(true);
 await enteredPromise;
 assert.equal(writes,1,'Only one external write may be in flight.');
 release();
 const settled=await Promise.allSettled([first,second,third,concurrentRearm]);
 assert.equal(settled.filter(x=>x.status==='rejected').length,4,
  'Queued starts and a queued rearm must all fail after a latched output fault.');
 assert.match(String(settled[0].reason),/write may have completed/);
 for(const event of settled.slice(1))assert.match(String(event.reason),/fault|reload|resync/i);
 assert.equal(writes,1);
 assertFaulted(director);
});

test('P1: acknowledged startup with a throwing independent readback fails closed',async()=>{
 let writes=0,reads=0;
 const adapter={name:'readback-timeout',external:true,requiresReadback:true,
  async show(){writes++;return {ok:true};},
  async readback(){reads++;throw new Error('readback connection lost after native command');}
 };
 const director=new PresentationDirector({adapter});
 director.load(deck);await director.arm(true);
 await assert.rejects(()=>director.start('automatic'),/readback connection lost/);
 assert.equal(writes,1);assert.equal(reads,1);
 assertFaulted(director);
 await assert.rejects(()=>director.start('automatic'),/fault|reload|resync/i);
 assert.equal(writes,1);assert.equal(reads,1);
});

test('P1: the read-only SSE viewer receives committed-then-thrown startup fault with unchanged index',
 {timeout:6000},async()=>{
 const token='review-p1-control-token-2026';
 const viewerToken='review-p1-viewer-token-2026';
 let writes=0;
 const adapter={name:'review-physical-simulation',external:true,
  async show(){writes++;throw new Error('simulated native timeout after commit');}
 };
 const handler=createMcpHandler({adapter,allowExternalControl:true});
 const server=createHttpServer({handler,token,viewerToken});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const base='http://127.0.0.1:'+server.address().port;
 const post=async(path,body)=>{
  const response=await fetch(base+path,{method:'POST',headers:{
   'Authorization':'Bearer '+token,'Content-Type':'application/json'},
   body:JSON.stringify(body),signal:AbortSignal.timeout(2400)});
  return {status:response.status,body:await response.json()};
 };
 const abort=new AbortController();
 let reader=null;
 try{
  assert.equal((await post('/v1/load',{deck})).status,200);
  assert.equal((await post('/v1/arm',{enabled:true})).status,200);
  const response=await fetch(base+'/v1/view-events?key='+viewerToken,{signal:abort.signal});
  assert.equal(response.status,200);
  reader=response.body.getReader();
  const decoder=new TextDecoder();
  let pending='';
  const takeEvent=async()=>{
   for(let n=0;n<25;n++){
    const match=pending.match(/data: ([^\n]+)\n\n/);
    if(match){
      pending=pending.slice(match.index+match[0].length);
      return JSON.parse(match[1]);
    }
    const {done,value}=await Promise.race([reader.read(),
      new Promise((_,reject)=>setTimeout(()=>reject(new Error('Viewer SSE event timeout')),600))]);
    if(done)throw new Error('Viewer stream terminated');
    pending+=decoder.decode(value);
   }
   throw new Error('No viewer state event arrived.');
  };
  const first=await takeEvent();
  assert.equal(first.outputFaulted,false);
  assert.equal(first.index,0);
  const start=await post('/v1/start',{mode:'automatic'});
  assert.equal(start.status,422);
  assert.match(start.body.error,/simulated native timeout/);
  const fault=await takeEvent();
  assert.equal(fault.outputFaulted,true);
  assert.equal(fault.held,true);
  assert.equal(fault.armed,false);
  assert.equal(fault.started,false);
  assert.equal(fault.index,0);
  assert.equal(fault.source,'review-physical-simulation');
  assert.equal((await post('/v1/start',{mode:'automatic'})).status,422);
  assert.equal((await post('/v1/arm',{enabled:true})).status,422);
  assert.equal(writes,1);
 }finally{
  abort.abort();
  try{await reader?.cancel();}catch{}
  server.closeAllConnections();
  await new Promise(resolve=>server.close(resolve));
 }
});
