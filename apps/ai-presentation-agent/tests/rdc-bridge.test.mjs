import test from 'node:test';
import assert from 'node:assert/strict';
import {RdcPresentationAdapter, BRIDGE_PROTOCOL_VERSION} from '../integrations/rdc-bridge.mjs';
import {PresentationDirector} from '../src/director.mjs';

const address={deviceId:'verified-mac-01',sourceId:'window-slide-show-921'};
const permit=async ({deviceId,sourceId,action})=>({
  allowed:deviceId===address.deviceId&&sourceId===address.sourceId,
  sourceId,deviceId,action
});
const deck={title:'Sample',slides:[{id:'intro',title:'Intro'},{id:'lyrics',title:'Song'}]};
const fixture=({permission=permit,execute=null,readState=null}={})=>{
  const dispatched=[];
  const transport={
    execute:execute??(async payload=>{
      dispatched.push(payload);
      return {status:'applied',commandId:payload.commandId,deviceId:payload.deviceId,sourceId:payload.sourceId};
    }),
    readState:readState??(async()=>({deviceId:address.deviceId,sourceId:address.sourceId,currentSlideIndex:1}))
  };
  return {adapter:new RdcPresentationAdapter({...address,transport,authorize:permission,clock:()=>1000}),dispatched};
};
test('bridge has a stable version and rejects ambiguous global desktop locations',()=>{
 assert.equal(BRIDGE_PROTOCOL_VERSION,'rdc.presentation.v1');
 assert.throws(()=>new RdcPresentationAdapter({
  deviceId:'d1',sourceId:'desktop',
  transport:{execute:async()=>{}},authorize:permit
 }),/source|window|browser/i);
 assert.throws(()=>new RdcPresentationAdapter({
  deviceId:'d1',sourceId:'window-x',transport:{execute:async()=>{}}
 }),/authoriz|permission/i);
});
test('RDC output cannot run without an exact-session owner grant',async()=>{
 const {adapter,dispatched}=fixture({permission:async()=>({allowed:false})});
 await assert.rejects(()=>adapter.show(1,deck.slides[1]),/authorization|denied|permission/i);
 assert.equal(dispatched.length,0);
});
test('RDC output requires source-bound approval for every command',async()=>{
 let authorizations=0;
 const {adapter,dispatched}=fixture({permission:async a=>{
  authorizations++;
  if(authorizations>1)return {allowed:false};
  return {allowed:true,deviceId:a.deviceId,sourceId:a.sourceId,action:a.action};
 }});
 const a=await adapter.show(1,deck.slides[1]);
 assert.equal(a.confirmed,true);
 await assert.rejects(()=>adapter.next(deck.slides[1]),/authorization|denied|permission/i);
 assert.equal(authorizations,2);
 assert.equal(dispatched.length,1);
});
test('RDC executes only a bounded slide command with protocol/source/receipt identity',async()=>{
 const {adapter,dispatched}=fixture();
 await adapter.show(1,{id:'lyrics',position:1,text:'never forward this to host <script>alert(1)</script>'});
 assert.equal(dispatched.length,1);
 const command=dispatched[0];
 assert.equal(command.protocol,BRIDGE_PROTOCOL_VERSION);
 assert.equal(command.deviceId,address.deviceId);
 assert.equal(command.sourceId,address.sourceId);
 assert.equal(command.action,'goto');
 assert.equal(command.index,1);
 assert.equal(command.expiresAt,3500);
 assert.match(command.commandId,/^[A-Za-z0-9-]{20,60}$/);
 assert.deepEqual(Object.keys(command).sort(),['action','commandId','deviceId','expiresAt','index','issuedAt','protocol','sourceId'].sort());
});
test('RDC refuses a success receipt from any other worker or viewer session',async()=>{
 const {adapter}=fixture({execute:async a=>({
   status:'applied',commandId:a.commandId,deviceId:'different-device',sourceId:a.sourceId
 })});
 await assert.rejects(()=>adapter.show(1,deck.slides[1]),/identity|source|device/i);
});
test('RDC does not claim success when the native presentation readback differs',async()=>{
 const {adapter}=fixture({readState:async()=>({
   deviceId:address.deviceId,sourceId:address.sourceId,currentSlideIndex:0
 })});
 await assert.rejects(()=>adapter.show(1,deck.slides[1]),/mismatch|readback/i);
});
test('RDC does not replay uncertain commands, even when worker reports pending',async()=>{
 let count=0;
 const {adapter}=fixture({execute:async a=>{count++;return {
  status:'pending',commandId:a.commandId,deviceId:a.deviceId,sourceId:a.sourceId
 };}});
 await assert.rejects(()=>adapter.show(1,deck.slides[1]),/pending|unknown|incomplete/i);
 assert.equal(count,1);
});
test('Director stays on existing slide when native RDC verification fails',async()=>{
 const {adapter}=fixture({readState:async()=>({
   deviceId:address.deviceId,sourceId:address.sourceId,currentSlideIndex:1
 })});
 const controller=new PresentationDirector({adapter});
 controller.load(deck);
 await controller.arm(true);
 await assert.rejects(()=>controller.start('automatic'),/mismatch|readback/i);
 assert.equal(controller.snapshot().started,false);
 assert.equal(controller.snapshot().current.id,'intro');
});

test('read-only RDC presentation observation still requires exact source authorization',async()=>{
 const seen=[];
 const {adapter}=fixture({
   permission:async request=>{
     seen.push(request.action);
     return {allowed:request.action!=='readback',
       sourceId:request.sourceId,deviceId:request.deviceId,action:request.action};
   }
 });
 await assert.rejects(()=>adapter.readback({expectedIndex:1}),
   /authorization|permission|denied/i);
 assert.deepEqual(seen,['readback']);
});
test('RDC readback command must request the same exact viewer source',async()=>{
 const reads=[];
 const {adapter}=fixture({
   readState:async context=>{
     reads.push(context);
     return {deviceId:context.deviceId,sourceId:context.sourceId,currentSlideIndex:1};
   }
 });
 const observed=await adapter.readback({expectedIndex:1});
 assert.equal(observed.confirmed,true);
 assert.equal(reads.length,1);
 assert.equal(reads[0].sourceId,address.sourceId);
 assert.equal(reads[0].deviceId,address.deviceId);
});
