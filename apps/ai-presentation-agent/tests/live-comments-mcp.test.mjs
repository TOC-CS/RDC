import test from 'node:test';
import assert from 'node:assert/strict';
import {createMcpHandler} from '../src/mcp.mjs';
import {LiveCommentsController} from '../src/live-comments.mjs';

const rpc=(name,args={})=>({jsonrpc:'2.0',id:1,method:'tools/call',params:{name,arguments:args}});
function fakeLiveController(){
 const sent=[];
 const comments=new LiveCommentsController({
  provider:'youtube',streamId:'livechat-test',
  clock:()=>1000,
  connector:{
   read:async()=>[{id:'viewer-01',text:'What verse is that?',authorId:'viewer01',createdAt:1}],
   post:async msg=>{sent.push(msg);return {status:'sent',provider:'youtube',streamId:'livechat-test',messageId:'sent-001'};}
  },
  authorize:async ({provider,streamId,commentId})=>({allowed:true,provider,streamId,commentId}),
  moderateReply:async()=>({allowed:true}),
  generateReply:async()=> 'The reference is John 3:16.'
 });
 return {comments,sent};
}
test('social comment tools advertise unavailable and cannot access accounts by default',async()=>{
 const host=createMcpHandler();
 const caps=(await host(rpc('presentation_capabilities'))).result.structuredContent;
 assert.equal(caps.liveComments.connected,false);
 const result=await host(rpc('live_comments_read'));
 assert.equal(result.result.isError,true);
 assert.match(result.result.content[0].text,/not connected|unavailable|configure/i);
});
test('connected comment agent reads and drafts through MCP but does not post without independent operator grant',async()=>{
 const {comments,sent}=fakeLiveController();
 const host=createMcpHandler({liveCommentsAgent:comments,allowLiveCommentPosting:false});
 const caps=(await host(rpc('presentation_capabilities'))).result.structuredContent;
 assert.equal(caps.liveComments.connected,true);
 const toolList=await host({jsonrpc:'2.0',id:1,method:'tools/list',params:{}});
 assert.ok(toolList.result.tools.some(t=>t.name==='live_comments_read'));
 const read=(await host(rpc('live_comments_read'))).result.structuredContent;
 assert.equal(read.newComments[0].id,'viewer-01');
 const draft=(await host(rpc('live_comments_draft',{commentId:'viewer-01'}))).result.structuredContent;
 assert.equal(draft.text,'The reference is John 3:16.');
 const arm=await host(rpc('live_comments_arm',{enabled:true}));
 assert.equal(arm.result.isError,true);
 const post=await host(rpc('live_comments_reply',{commentId:'viewer-01',text:'The reference is John 3:16.'}));
 assert.equal(post.result.isError,true);
 assert.equal(sent.length,0);
});
test('independent comment grant plus connector authorization allows exactly one confirmed comment',async()=>{
 const {comments,sent}=fakeLiveController();
 const host=createMcpHandler({liveCommentsAgent:comments,allowLiveCommentPosting:true});
 async function call(name,args={}){
  const out=(await host(rpc(name,args))).result;
  assert.equal(out.isError,undefined,JSON.stringify(out));
  return out.structuredContent;
 }
 await call('live_comments_read');
 await call('live_comments_mode',{mode:'automatic'});
 await call('live_comments_arm',{enabled:true});
 const posted=await call('live_comments_reply',{commentId:'viewer-01',text:'The reference is John 3:16.'});
 assert.equal(posted.status,'sent');
 assert.equal(sent.length,1);
 const duplicate=await call('live_comments_reply',{commentId:'viewer-01',text:'Again'});
 assert.equal(duplicate.status,'already_sent');
 assert.equal(sent.length,1);
});
