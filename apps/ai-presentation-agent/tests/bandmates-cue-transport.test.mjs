import test from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {createBandMatesCueTransport} from '../integrations/bandmates-cue-transport.mjs';
import {VerifiedBandMatesSectionRelay} from '../integrations/bandmates-verified-relay.mjs';
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';

const token='a'.repeat(64);
const native={schema:'bandmates.performance-section/v1',
 sessionId:'native-001',eventId:'native-section-001',song:'Song One',
 section:'verse',occurrence:1,stateKind:'performed',
 performanceConfirmed:true,confidence:.99,timestamp:10000};

test('authorized native BandMates cue goes through actual local HTTP presentation API once',async()=>{
 const handler=createMcpHandler({clock:()=>10000});
 const server=createHttpServer({handler,token});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const port=server.address().port;
 const invoke=async(name,args={})=>{
   const response=await handler({jsonrpc:'2.0',id:1,method:'tools/call',
     params:{name,arguments:args}});
   assert.equal(response.result.isError,undefined);
   return response.result.structuredContent;
 };
 try{
   await invoke('presentation_load',{deck:{slides:[
     {id:'intro'},{id:'verse',song:'Song One',section:'Verse 1'}
   ]}});
   await invoke('presentation_start',{mode:'automatic'});
   const send=createBandMatesCueTransport({readState:async()=>({port,token})});
   const relay=new VerifiedBandMatesSectionRelay({sessionId:'native-001',
      clock:()=>10000,send});
   const result=await relay.accept(native);
   assert.equal(result.changed,true);
   assert.equal((await invoke('presentation_status')).current.id,'verse');
   assert.equal((await relay.accept(native)).reason,'duplicate_verified_section');
 }finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});
test('cue sender never retries after connection failure or leaks local private token in errors',async()=>{
 let calls=0;
 const sender=createBandMatesCueTransport({
   readState:async()=>({port:12345,token}),
   fetcher:async()=>{calls++;throw Error('Authorization: Bearer '+token);}
 });
 await assert.rejects(()=>sender({type:'song.section'}),error=>{
   assert.match(error.message,/unknown/i);
   assert.equal(error.message.includes(token),false);
   return true;
 });
 assert.equal(calls,1);
});
test('cue sender validates session metadata before network I/O',async()=>{
 let calls=0;
 const sender=createBandMatesCueTransport({
   readState:async()=>({port:12345,token:'invalid'}),
   fetcher:async()=>{calls++;return {ok:true,json:async()=>({changed:true})};}
 });
 await assert.rejects(()=>sender({}),/private.*session/i);
 assert.equal(calls,0);
});
