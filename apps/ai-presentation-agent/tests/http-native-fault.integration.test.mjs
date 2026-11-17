import test from 'node:test';
import assert from 'node:assert/strict';
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';

const token='test-native-fault-isolation-2026';
const slides={slides:[
  {id:'intro',title:'Opening',song:'Original Song',section:'intro'},
  {id:'chorus',title:'Chorus',song:'Original Song',section:'chorus'}
]};
const request=async(base,path,body=null)=>{
 const response=await fetch(base+path,{
   method:body===null?'GET':'POST',
   headers:{Authorization:'Bearer '+token,
     ...(body===null?{}:{'Content-Type':'application/json'})},
   ...(body===null?{}:{body:JSON.stringify(body)}),
   signal:AbortSignal.timeout(4000)
 });
 return {status:response.status,body:await response.json()};
};
async function fixture(adapter){
 const handler=createMcpHandler({adapter,allowExternalControl:true});
 const server=createHttpServer({handler,token});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 return {server,base:'http://127.0.0.1:'+server.address().port};
}
async function close(server){server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}

test('authenticated HTTP latches uncertain external output, disarms and blocks native follow-up writes',async()=>{
 let actual=0,writes=0;
 const adapter={name:'simulated-physical',external:true,requiresReadback:true,
   async show(index){actual=index;return {ok:true};},
   async next(){writes++;actual=1;return {ok:true};},
   async readback({expectedIndex}){
     // Native app acknowledged a write, but its output readback still shows
     // the previous slide, indicating uncertain audience projection.
     return {supported:true,confirmed:expectedIndex===0,
       index:0,source:'simulated-independent-output'};
   }
 };
 const {server,base}=await fixture(adapter);
 try{
   assert.equal((await request(base,'/v1/load',{deck:slides})).status,200);
   assert.equal((await request(base,'/v1/arm',{enabled:true})).status,200);
   assert.equal((await request(base,'/v1/start',{mode:'automatic'})).status,200);
   const failed=await request(base,'/v1/command',{action:'next',idempotencyKey:'one-ambiguous-output'});
   assert.equal(failed.status,422);
   assert.match(failed.body.error,/readback|mismatch/i);
   assert.equal(writes,1);
   const status=await request(base,'/v1/status');
   assert.equal(status.status,200);
   assert.equal(status.body.outputFaulted,true);
   assert.equal(status.body.armed,false);
   assert.equal(status.body.held,true);
   assert.equal(status.body.current.id,'intro');
   assert.equal((await request(base,'/v1/cue',{
     source:'bandmates',type:'song.section',song:'Original Song',
     section:'chorus',eventId:'chorus-1'
   })).body.reason,'output_fault');
   assert.equal((await request(base,'/v1/start',{mode:'automatic'})).status,422);
   assert.equal((await request(base,'/v1/arm',{enabled:true})).status,422);
   assert.equal((await request(base,'/v1/command',{action:'next'})).status,422);
   assert.equal(writes,1,'A known-uncertain physical output cannot receive a second change.');
   // Explicit operator reload drops the old native authorization.
   const reloaded=await request(base,'/v1/load',{deck:slides});
   assert.equal(reloaded.status,200);
   assert.equal(reloaded.body.outputFaulted,false);
   assert.equal(reloaded.body.armed,false);
   assert.equal(reloaded.body.started,false);
 }finally{await close(server);}
});

test('simultaneous authenticated HTTP start retries retain the live slide without duplicate native commands',async()=>{
 let writes=0;
 const adapter={name:'external-ack',external:true,
   async show(){writes++;await new Promise(resolve=>setTimeout(resolve,12));return {ok:true};},
   async next(){writes++;return {ok:true};}
 };
 const {server,base}=await fixture(adapter);
 try{
   await request(base,'/v1/load',{deck:slides});
   await request(base,'/v1/arm',{enabled:true});
   const starts=await Promise.all([
     request(base,'/v1/start',{mode:'manual'}),
     request(base,'/v1/start',{mode:'manual'})
   ]);
   assert.deepEqual(starts.map(r=>r.status),[200,200]);
   assert.equal(writes,1);
   assert.equal((await request(base,'/v1/command',{action:'next'})).status,200);
   assert.equal(writes,2);
   const again=await request(base,'/v1/start',{mode:'manual'});
   assert.equal(again.status,200);
   assert.equal(again.body.current.id,'chorus');
   assert.equal(writes,2);
   const conflict=await request(base,'/v1/start',{mode:'automatic'});
   assert.equal(conflict.status,422);
   assert.equal(writes,2);
 }finally{await close(server);}
});
