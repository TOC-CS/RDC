import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createMcpHandler} from '../src/mcp.mjs';

const fromExamples=async filename=>JSON.parse(await readFile(
 new URL('../examples/'+filename,import.meta.url),'utf8'));
const call=async(h,name,args={})=>{
 const reply=await h({jsonrpc:'2.0',id:1,method:'tools/call',
  params:{name,arguments:args}});
 if(reply?.result?.isError)throw new Error(reply.result.content[0].text);
 return reply.result.structuredContent;
};
const auth='isolated-stage-owner-grant-2026';
test('complete original service rehearsal unifies verified catalog, stage-only teleprompt, private rights and three-way room draft without changing live outputs',async()=>{
 const handler=createMcpHandler({stageGrant:auth,allowTelepromptControl:true});
 const catalog=await fromExamples('toc-offline-worship-library.json');
 const plan=await fromExamples('toc-offline-worship-plan.json');
 const loaded=await call(handler,'presentation_load_worship_library',{catalog,plan});
 assert.equal(loaded.started,false);
 assert.equal(loaded.armed,false);
 assert.equal(loaded.slides.length,14);
 assert.equal(loaded.worship.issues.length,3);
 assert.equal(handler.getPrivateTeleprompt('wrong'),null);
 await call(handler,'presentation_start',{mode:'manual'});
 await call(handler,'presentation_command',{action:'goto',id:'opening-worship-s4-p1'});
 const state=await call(handler,'presentation_status');
 assert.equal(state.current.id,'opening-worship-s4-p1');
 assert.equal(state.current.occurrence,2);
 const stage=handler.getPrivateStageCue(auth);
 assert.equal(stage.current.section,'chorus');
 assert.ok(stage.current.text.length>0);
 const privatePrompt=handler.updatePrivateTeleprompt(auth,{
  action:'configure',role:'singer',fontScale:1.7,
  scrollSpeed:1.2,mirrored:true
 });
 assert.equal(privatePrompt.role,'singer');
 assert.equal(privatePrompt.mirrored,true);
 assert.equal(privatePrompt.slideId,'opening-worship-s4-p1');
 assert.equal(handler.getBroadcastCue().current.text,'');
 assert.equal(handler.getWorshipLook('broadcast').layers.text,'');
 assert.equal(handler.getWorshipLook('stage','wrong'),null);
 const room=await call(handler,'presentation_communication_prepare',{
  localSessionId:'presentation-fixture',roomMembers:[
   'presentation-fixture','rdc-fixture','bandmates-fixture'
  ],roomKey:'integration-rehearsal-2026',requestId:'status-only-1'
 });
 const published=JSON.parse(room.text);
 assert.equal(published.slideId,'opening-worship-s4-p1');
 assert.equal(published.occurrence,2);
 assert.equal(published.armed,false);
 assert.equal(room.applied,false);
 assert.equal(room.expectedRecipients.length,2);
 assert.equal(room.liveChatObserved,false);
 assert.equal(room.text.includes(stage.current.text),false);
 assert.equal(room.text.includes(String(stage.current.notes)),false);
 assert.equal(room.text.includes(privatePrompt.current),false);
 assert.equal(JSON.stringify(await call(handler,'presentation_status')).includes('teleprompt'),false);
 assert.equal((await call(handler,'presentation_status')).index,5);
 assert.equal(handler.getPrivateTeleprompt(auth).position,0);
 await call(handler,'presentation_stop');
 await call(handler,'presentation_unload');
 assert.equal(handler.getPrivateTeleprompt(auth),null);
 assert.equal(handler.getBroadcastCue(),null);
 const cleared=await call(handler,'presentation_status');
 assert.equal(cleared.slides.length,0);
 assert.equal(cleared.armed,false);
});
