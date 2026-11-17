import test from 'node:test';
import assert from 'node:assert/strict';
import {PresentationDirector} from '../src/director.mjs';
import {MemoryAdapter} from '../src/adapters.mjs';
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';

const deck={slides:[{id:'welcome'},{id:'teaching'},{id:'closing'}]};
test('operator stop preserves last slide, disarms output, prevents further auto cues and permits a deliberate fresh start',async()=>{
 const output=new MemoryAdapter();
 const director=new PresentationDirector({adapter:output,cooldownMs:0});
 director.load(deck);
 await director.start('automatic');
 await director.command({action:'next'});
 const writes=output.events.length;
 const result=await director.command({action:'stop'});
 assert.equal(result.reason,'stopped');
 assert.equal(director.snapshot().started,false);
 assert.equal(director.snapshot().armed,false);
 assert.equal(director.snapshot().held,true);
 assert.equal(director.snapshot().current.id,'teaching');
 assert.equal(output.events.length,writes);
 assert.equal((await director.ingest({type:'scripture',reference:'John 3:16'})).reason,'not_running');
 await assert.rejects(()=>director.command({action:'next'}),/must be running/i);
 await director.start('manual');
 assert.equal(director.snapshot().current.id,'welcome');
});
test('stop remains allowed after a fault without resetting the external output fault',async()=>{
 const adapter={name:'output',external:true,
   async show(){return {ok:true};},
   async next(){throw Error('ambiguous physical timeout');}
 };
 const director=new PresentationDirector({adapter});
 director.load(deck);await director.arm(true);await director.start('automatic');
 await assert.rejects(()=>director.command({action:'next'}),/ambiguous/);
 assert.equal(director.snapshot().outputFaulted,true);
 const stopped=await director.command({action:'stop'});
 assert.equal(stopped.reason,'stopped');
 assert.equal(stopped.state.outputFaulted,true);
 assert.equal(stopped.state.armed,false);
 await assert.rejects(()=>director.start('automatic'),/fault|reload/i);
});
test('authenticated HTTP stop endpoint is read-only with respect to external projection writes',async()=>{
 const handler=createMcpHandler();
 const server=createHttpServer({handler,token:'operator-stop-test-2026'});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const base='http://127.0.0.1:'+server.address().port;
 const post=async(path,payload)=>{
  const response=await fetch(base+path,{method:'POST',
   headers:{'Content-Type':'application/json',Authorization:'Bearer operator-stop-test-2026'},
   body:JSON.stringify(payload)});
  return {status:response.status,body:await response.json()};
 };
 try{
   await post('/v1/load',{deck});
   await post('/v1/start',{mode:'automatic'});
   const stop=await post('/v1/stop',{});
   assert.equal(stop.status,200);
   assert.equal(stop.body.started,false);
   assert.equal(stop.body.armed,false);
 }finally{server.closeAllConnections();await new Promise(r=>server.close(r));}
});
