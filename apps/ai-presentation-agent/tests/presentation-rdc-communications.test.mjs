import test from 'node:test';
import assert from 'node:assert/strict';
import {
 preparePresentationRoomStatus,preparePresentationRoomReply,
 PresentationRoomDelivery
} from '../src/rdc-communications.mjs';

const snapshot={title:'Private Sermon Title',started:false,armed:false,
 held:true,outputFaulted:false,mode:'manual',index:1,
 current:{id:'chorus-2',section:'chorus',occurrence:2,
  text:'PRIVATE_SINGER_SCRIPT_DO_NOT_SEND',
  notes:'PRIVATE_PASTOR_NOTES_DO_NOT_SEND',kind:'song'},
 slides:[{id:'intro'},{id:'chorus-2',text:'PRIVATE_SINGER_SCRIPT_DO_NOT_SEND'}],
 stageCredential:'PRIVATE_CONTROL_TOKEN_DO_NOT_SEND',
 history:[{action:'voice',transcript:'PRIVATE_STT_DATA_DO_NOT_SEND'}]};
const base={snapshot,roomMembers:['presentation-fixture','rdc-fixture','bandmates-fixture'],
 localSessionId:'presentation-fixture',roomKey:'service-coordination',
 requestId:'status-001'};

test('three-way room status draft selects only safe cue metadata and never sends anything',()=>{
 const result=preparePresentationRoomStatus(base);
 assert.equal(result.schema,'toc.presentation.rdc-room-draft/v1');
 assert.equal(result.roomSize,3);
 assert.deepEqual(result.expectedRecipients,['bandmates-fixture','rdc-fixture']);
 assert.equal(result.sourceSessionId,'presentation-fixture');
 assert.equal(result.roomKey,'service-coordination');
 assert.equal(result.key,'status-001');
 assert.equal(result.requiresAuthenticatedRdcBinding,true);
 assert.equal(result.directChatPushAllowed,false);
 assert.equal(result.applied,false);
 const body=JSON.parse(result.text);
 assert.equal(body.schema,'toc.presentation.room-status/v1');
 assert.equal(body.slideId,'chorus-2');
 assert.equal(body.occurrence,2);
 assert.equal(body.index,1);
 assert.equal(body.started,false);
 for(const privateValue of ['PRIVATE_','PRIVATE STT','TOKEN','pastor','stageCredential',
   'history','slides','notes','transcript']){
  assert.equal(JSON.stringify(result).includes(privateValue),false,privateValue);
 }
 assert.ok(result.text.length<3000);
});

test('two-way rooms work, but duplicate or excessive members and untrusted IDs fail validation',()=>{
 const result=preparePresentationRoomStatus({...base,
  roomMembers:['presentation-fixture','rdc-fixture']});
 assert.equal(result.roomSize,2);
 assert.deepEqual(result.expectedRecipients,['rdc-fixture']);
 for(const roomMembers of [
  ['presentation-fixture'],
  ['presentation-fixture','presentation-fixture'],
  ['rdc-fixture','bandmates-fixture'],
  ['presentation-fixture','rdc-fixture','bandmates-fixture','operator-fixture'],
  ['presentation-fixture','../escape']
 ]){
  assert.throws(()=>preparePresentationRoomStatus({...base,roomMembers}),/room|participant|member|identity/i);
 }
 assert.throws(()=>preparePresentationRoomStatus({...base,requestId:'bad key with spaces'}),/request|key/i);
 assert.throws(()=>preparePresentationRoomStatus({...base,roomKey:'../unsafe'}),/room|key/i);
});

test('delivery is held until independently authorized RDC room transport is actually injected',async()=>{
 const draft=preparePresentationRoomStatus(base);
 let sends=0;
 const disabled=new PresentationRoomDelivery({roomSend:async()=>{sends++;}});
 assert.equal((await disabled.send(draft)).state,'HELD');
 assert.equal(sends,0);
 const bound=new PresentationRoomDelivery({
  boundPrincipal:{sessionId:'presentation-fixture',project:'rdc',verified:true},
  operatorApproved:true,roomSend:async params=>{
   sends++;
   assert.deepEqual(params.members,draft.roomMembers);
   assert.equal(params.roomKey,draft.roomKey);
   assert.equal(params.key,draft.key);
   assert.equal(params.text,draft.text);
   return {scope:'synthetic_fixture_only',room_id:'75d88e94-ff70-4f73-99ca-f81ca0fd75ce',
    receipts:{'rdc-fixture':{message_id:'id-rdc'},
     'bandmates-fixture':{message_id:'id-bandmates'}}};
  }
 });
 const outcome=await bound.send(draft);
 assert.equal(outcome.state,'SYNTHETIC_ENQUEUED');
 assert.equal(outcome.liveChatObserved,false);
 assert.equal(outcome.actionConfirmed,false);
 assert.equal(sends,1);
 const again=await bound.send(draft);
 assert.equal(again.duplicate,true);
 assert.equal(sends,1);
 await assert.rejects(()=>bound.send({...draft,text:'changed content'}),/conflict|validated|trusted/i);
});

test('uncertain room send is never blindly repeated and cannot masquerade as chat delivery',async()=>{
 const draft=preparePresentationRoomStatus(base);
 let sends=0;
 const bridge=new PresentationRoomDelivery({
  boundPrincipal:{sessionId:'presentation-fixture',project:'rdc',verified:true},
  operatorApproved:true,roomSend:async()=>{sends++;throw new Error('timeout after possible enqueue');}
 });
 const first=await bridge.send(draft);
 assert.equal(first.state,'OUTCOME_UNKNOWN');
 assert.equal(first.liveChatObserved,false);
 assert.equal((await bridge.send(draft)).state,'OUTCOME_UNKNOWN');
 assert.equal(sends,1);
});

test('inbound room message is inert unless sender is independently bound and asking for read-only status',()=>{
 const envelope={
  schema_version:'atlas.bus.message.v1',
  message_id:'75d88e94-ff70-4f73-99ca-f81ca0fd75ce',
  correlation_id:'ec33e724-12c4-4e65-a324-d66aa85910d5',
  causation_id:null,source_project:'rdc',source_session_id:'rdc-fixture',
  destination_project:'rdc',destination_session_id:'presentation-fixture',
  message_type:'question',priority:'normal',hop_count:0,
  idempotency_key:'ask-1',
  payload:{text:'presentation status?',channel:'chat-room',
   room_id:'ec33e724-12c4-4e65-a324-d66aa85910d5',
   participants:['presentation-fixture','rdc-fixture','bandmates-fixture']}
 };
 const ignored=preparePresentationRoomReply(envelope,{localSessionId:'presentation-fixture',
  authenticatedSource:null,snapshot});
 assert.equal(ignored.state,'UNVERIFIED_SOURCE');
 const prepared=preparePresentationRoomReply(envelope,{localSessionId:'presentation-fixture',
  authenticatedSource:'rdc-fixture',snapshot});
 assert.equal(prepared.state,'DRAFT_ONLY');
 assert.equal(prepared.replyTo,envelope.message_id);
 assert.equal(prepared.roomId,envelope.correlation_id);
 assert.equal(JSON.parse(prepared.text).slideId,'chorus-2');
 assert.equal(JSON.stringify(prepared).includes('PRIVATE_'),false);
 const command=preparePresentationRoomReply({...envelope,payload:{...envelope.payload,
  text:'presentation agent next slide'}},{localSessionId:'presentation-fixture',
  authenticatedSource:'rdc-fixture',snapshot});
 assert.equal(command.state,'MANUAL_REVIEW');
 assert.equal(command.executionAllowed,false);
 assert.equal(command.stageOrStreamModified,false);
 assert.throws(()=>preparePresentationRoomReply({...envelope,destination_session_id:'other'},
  {localSessionId:'presentation-fixture',authenticatedSource:'rdc-fixture',snapshot}),/recipient|destination/i);
});

test('fabricated or cloned room drafts are refused before any external room transport',async()=>{
 const safe=preparePresentationRoomStatus(base);
 let sends=0;
 const bridge=new PresentationRoomDelivery({
  boundPrincipal:{sessionId:'presentation-fixture',project:'rdc',verified:true},
  operatorApproved:true,
  roomSend:async()=>{sends++;return {scope:'synthetic_fixture_only',receipts:{}};}
 });
 const forged={
  ...safe,text:'PRIVATE_PASTOR_SCRIPT_STAGE_ONLY_DO_NOT_SEND'
 };
 await assert.rejects(()=>bridge.send(forged),/validated|trusted|draft|untrusted/i);
 await assert.rejects(()=>bridge.send(structuredClone(safe)),/validated|trusted|draft|untrusted/i);
 assert.equal(sends,0);
 const first=await bridge.send(safe);
 assert.equal(first.state,'OUTCOME_UNKNOWN');
 assert.equal(sends,1);
});

test('non-question or elevated-priority peer envelopes cannot obtain even status drafts',()=>{
 const envelope={
  schema_version:'atlas.bus.message.v1',
  message_id:'75d88e94-ff70-4f73-99ca-f81ca0fd75ce',
  correlation_id:'ec33e724-12c4-4e65-a324-d66aa85910d5',
  causation_id:null,source_project:'rdc',source_session_id:'rdc-fixture',
  destination_project:'rdc',destination_session_id:'presentation-fixture',
  message_type:'question',priority:'normal',hop_count:0,
  idempotency_key:'ask-1',payload:{
   text:'presentation status?',channel:'chat-room',
   room_id:'ec33e724-12c4-4e65-a324-d66aa85910d5',
   participants:['presentation-fixture','rdc-fixture','bandmates-fixture']
  }
 };
 for(const patch of [
  {message_type:'stop'},
  {message_type:'pause'},
  {message_type:'review.decision'},
  {priority:'control'},
  {source_project:'presentation'},
  {destination_project:'bandmates'},
  {hop_count:4}
 ]){
  const result=preparePresentationRoomReply({...envelope,...patch},{
   localSessionId:'presentation-fixture',authenticatedSource:'rdc-fixture',snapshot
  });
  assert.equal(result.state,'MANUAL_REVIEW',JSON.stringify(patch));
  assert.equal(result.executionAllowed,false);
  assert.equal(result.text,undefined);
 }
});
