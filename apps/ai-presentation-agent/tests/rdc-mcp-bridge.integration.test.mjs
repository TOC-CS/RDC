import test from 'node:test';
import assert from 'node:assert/strict';
import {registerPresentationAdapter} from '../src/adapters.mjs';
import {RdcPresentationAdapter} from '../integrations/rdc-bridge.mjs';
import {createMcpHandler} from '../src/mcp.mjs';

const protocol={deviceId:'worker-a',sourceId:'window-live-worship'};
const deck={title:'Worship',slides:[
  {id:'welcome',title:'Welcome'},
  {id:'song-chorus',title:'Chorus',song:'Original Song',section:'chorus',text:'We sing together'},
  {id:'sermon',title:'Message',text:'The teaching starts right now',cues:['the teaching starts right now']}
]};
const rpc=(name,arguments_)=>({
  jsonrpc:'2.0',id:1,method:'tools/call',
  params:{name,arguments:arguments_}
});
test('RDC window plugin + MCP + BandMates + host voice share an exactly scoped live session',async()=>{
 let verifiedIndex=0,canOperate=true,grants=0;
 const dispatched=[];
 const transport={
   execute:async cmd=>{
     dispatched.push(cmd);
     verifiedIndex=cmd.index;
     return {status:'applied',commandId:cmd.commandId,deviceId:cmd.deviceId,sourceId:cmd.sourceId};
   },
   readState:async()=>({...protocol,currentSlideIndex:verifiedIndex})
 };
 const unregister=registerPresentationAdapter('rdc-owner-window-v1',()=>new RdcPresentationAdapter({
   ...protocol,transport,
   authorize:async req=>{grants++;return {allowed:canOperate,deviceId:req.deviceId,sourceId:req.sourceId,action:req.action};},
   clock:()=>10000
 }));
 try{
   const handler=createMcpHandler({allowExternalControl:true,clock:()=>10000});
   async function call(name,args){
     const reply=await handler(rpc(name,args));
     if(reply.result.isError)throw new Error(reply.result.content[0].text);
     return reply.result.structuredContent;
   }
   await call('presentation_load',{deck});
   const selected=await call('presentation_select_output',{kind:'rdc-owner-window-v1'});
   assert.equal(selected.armed,false);
   await call('presentation_arm',{enabled:true});
   await call('presentation_start',{mode:'automatic'});
   assert.equal(dispatched.at(-1).action,'goto');
   assert.equal(verifiedIndex,0);
   const next=await call('presentation_cue',{source:'bandmates',type:'song.section',song:'Original Song',section:'chorus',eventId:'music1'});
   assert.equal(next.changed,true);
   assert.equal(next.slide.id,'song-chorus');
   assert.equal(verifiedIndex,1);
   const voice=await call('presentation_voice',{transcript:'presentation agent next slide',final:true,confidence:1});
   assert.equal(voice.accepted,true);
   assert.equal(voice.speakByHost,true);
   assert.equal(verifiedIndex,2);
   assert.equal((await call('presentation_readback',{})).confirmed,true);
   assert.equal((await call('presentation_status',{})).current.id,'sermon');
   assert.deepEqual(new Set(dispatched.map(c=>c.sourceId)),new Set([protocol.sourceId]));
   assert.deepEqual(new Set(dispatched.map(c=>c.deviceId)),new Set([protocol.deviceId]));
   assert.equal(grants,4);
   canOperate=false;
   const refused=await handler(rpc('presentation_command',{action:'previous'}));
   assert.equal(refused.result.isError,true);
   assert.equal((await call('presentation_status',{})).current.id,'sermon');
   assert.equal(dispatched.length,3);
 }finally{unregister();}
});
test('RDC presentation readback never treats another owner window as a confirmed slide',async()=>{
 const unregister=registerPresentationAdapter('rdc-owner-verify-v1',()=>new RdcPresentationAdapter({
   ...protocol,
   authorize:async req=>({allowed:true,deviceId:req.deviceId,sourceId:req.sourceId}),
   transport:{
     execute:async cmd=>({status:'applied',commandId:cmd.commandId,deviceId:cmd.deviceId,sourceId:cmd.sourceId}),
     readState:async()=>({deviceId:protocol.deviceId,sourceId:'window-another-chat',currentSlideIndex:0})
   }
 }));
 try{
   const handler=createMcpHandler({allowExternalControl:true});
   const tool=async(name,args)=>(await handler(rpc(name,args))).result;
   await tool('presentation_load',{deck});
   await tool('presentation_select_output',{kind:'rdc-owner-verify-v1'});
   await tool('presentation_arm',{enabled:true});
   const start=await tool('presentation_start',{mode:'automatic'});
   assert.equal(start.isError,true);
   const status=await tool('presentation_status',{});
   assert.equal(status.structuredContent.started,false);
 }finally{unregister();}
});
