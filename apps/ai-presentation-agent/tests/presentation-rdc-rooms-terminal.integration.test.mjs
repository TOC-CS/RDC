import test from 'node:test';
import assert from 'node:assert/strict';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {mkdtemp,rm} from 'node:fs/promises';
import {existsSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath} from 'node:url';
import {
 preparePresentationRoomStatus,PresentationRoomDelivery
} from '../src/rdc-communications.mjs';

const exec=promisify(execFile);
const workspace=fileURLToPath(new URL('..',import.meta.url));
const rdc=resolve(workspace,'../rdc-chat-interconnect-20261117');
const atlas=resolve(workspace,'../Atlas-Build-Bus');
const python=process.env.PRESENTATION_RDC_PYTHON??'python3';
const supported=existsSync(join(rdc,'rdc/chatctl.py'))&&
 existsSync(join(atlas,'atlasbus/store.py'));
const members=['presentation-fixture','rdc-fixture','bandmates-fixture'];
const roomKey='original-worship-synthetic-room';

test('Presentation Agent drafts join actual existing three-party RDC/Atlas terminal sandbox with shared correlation and replies',
 {timeout:14000},async t=>{
 if(!supported)return t.skip('RDC/Atlas synthetic source absent on this host. No live connection implied.');
 const directory=await mkdtemp(join(tmpdir(),'toc-presentation-rdc-room-'));
 const db=join(directory,'chat-room-fixture.sqlite3');
 const command=async(...args)=>{
  const {stdout}=await exec(python,['-m','rdc.chatctl',
   '--synthetic-only','--atlas-source',atlas,'--db',db,...args],{
   cwd:rdc,env:{...process.env,PYTHONPATH:rdc},timeout:3000,maxBuffer:40000
  });
  const data=JSON.parse(stdout);
  assert.equal(data.ok,true,JSON.stringify(data));
  assert.equal(data.scope,'synthetic_fixture_only');
  return data;
 };
 try{
  const initialized=await command('init',
   '--session','presentation-fixture',
   '--session','rdc-fixture',
   '--session','bandmates-fixture');
  assert.deepEqual(initialized.sessions,[...members].sort());
  const room=await command('room-id','--as','presentation-fixture',
   '--members',members.join(','),'--room-key',roomKey);
  assert.equal(room.room_size,3);
  const draft=preparePresentationRoomStatus({
   localSessionId:'presentation-fixture',roomMembers:members,roomKey,
   requestId:'presentation-status-fixture-1',
   snapshot:{index:1,mode:'automatic',started:true,held:false,
    armed:false,outputFaulted:false,
    current:{id:'original-chorus',kind:'song',section:'chorus',occurrence:2,
     text:'PRIVATE_STAGE_LYRICS_MUST_NOT_ENTER_BUS'}}
  });
  const transport=new PresentationRoomDelivery({
   boundPrincipal:{project:'rdc',sessionId:'presentation-fixture',verified:true},
   operatorApproved:true,
   roomSend:({members,roomKey,key,text})=>command('room-send',
    '--from','presentation-fixture','--members',members.join(','),
    '--room-key',roomKey,'--key',key,'--text',text)
  });
  const published=await transport.send(draft);
  assert.equal(published.state,'SYNTHETIC_ENQUEUED');
  assert.equal(published.recipientCount,2);
  assert.equal(published.roomId,room.room_id);
  assert.equal(published.liveChatObserved,false);
  const receiver=async recipient=>{
   const holder='presentation-test-'+recipient;
   const c=await command('claim','--as',recipient,'--holder',holder);
   const claim=c.claim;
   assert.equal(claim.envelope.correlation_id,room.room_id);
   assert.equal(claim.envelope.source_session_id,'presentation-fixture');
   assert.equal(claim.envelope.destination_session_id,recipient);
   assert.equal(claim.envelope.payload.text,draft.text);
   assert.equal(JSON.stringify(claim).includes('PRIVATE_STAGE_LYRICS'),false);
   await command('fetch','--as',recipient,'--holder',holder,
    '--message-id',claim.message_id,'--revision',String(claim.revision));
   const ack=await command('ack','--as',recipient,'--message-id',claim.message_id);
   assert.equal(ack.receipt.state,'SESSION_ACKNOWLEDGED');
   return claim;
  };
  const rdcClaim=await receiver('rdc-fixture');
  const bandmatesClaim=await receiver('bandmates-fixture');
  assert.notEqual(rdcClaim.message_id,bandmatesClaim.message_id);
  const reply=await command('room-send','--from','rdc-fixture',
   '--members',members.join(','),'--room-key',roomKey,
   '--key','rdc-reply-1','--parent-id',rdcClaim.message_id,
   '--text','Status received in the synthetic room');
  assert.equal(reply.room_id,room.room_id);
  const incoming=await command('claim','--as','presentation-fixture',
   '--holder','presentation-test-recipient');
  assert.equal(incoming.claim.envelope.correlation_id,room.room_id);
  assert.equal(incoming.claim.envelope.causation_id,rdcClaim.message_id);
  assert.equal(incoming.claim.envelope.source_session_id,'rdc-fixture');
  const duplicate=await transport.send(draft);
  assert.equal(duplicate.duplicate,true);
  assert.equal(duplicate.liveChatObserved,false);
 }finally{await rm(directory,{recursive:true,force:true});}
});
