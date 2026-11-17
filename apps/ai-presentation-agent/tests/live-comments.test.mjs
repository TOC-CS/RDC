import test from 'node:test';
import assert from 'node:assert/strict';
import {LiveCommentsController} from '../src/live-comments.mjs';

const target={provider:'youtube',streamId:'live-chat-001'};
function fixture({permission=true,mode='read-only',clock=()=>1000,moderation=true,sendResult=null}={}){
 const outbound=[];
 const connector={
   read:async()=>[
      {id:'c1',authorId:'viewerA',authorName:'Visitor',text:'Can you explain John 3:16?',createdAt:800},
      {id:'c2',authorId:'owner',authorName:'My Channel',text:'Opening message',isOwnMessage:true,createdAt:900}
   ],
   post:async msg=>{
     outbound.push(msg);
     return sendResult??{status:'sent',messageId:'posted-1',provider:target.provider,streamId:target.streamId};
   }
 };
 const controller=new LiveCommentsController({...target,connector,clock,
   authorize:async cmd=>({allowed:permission,provider:cmd.provider,streamId:cmd.streamId,commentId:cmd.commentId}),
   generateReply:async({comment})=>'In John 3:16, the Word says the Father gave His Son.',
   moderateReply:async()=>({allowed:moderation})
 });
 controller.setMode(mode);
 return {controller,outbound,connector};
}
test('live comment monitor reads new messages without publishing',async()=>{
 const {controller,outbound}=fixture();
 const first=await controller.pollOnce();
 assert.equal(first.newComments.length,1);
 assert.equal(first.newComments[0].id,'c1');
 assert.equal(first.ignoredOwn,1);
 assert.equal((await controller.pollOnce()).newComments.length,0);
 assert.equal(outbound.length,0);
 assert.equal(controller.status().mode,'read-only');
});
test('comment drafts are generated separately from sends',async()=>{
 const {controller,outbound}=fixture();
 await controller.pollOnce();
 const draft=await controller.draftReply('c1');
 assert.match(draft.text,/John 3:16/);
 assert.equal(draft.status,'draft');
 assert.equal(outbound.length,0);
});
test('writes require explicit arm, per-stream authorization and content review',async()=>{
 const {controller,outbound}=fixture({mode:'automatic'});
 await controller.pollOnce();
 await assert.rejects(()=>controller.reply('c1','Thanks for watching'),/armed|authorization|permission/i);
 controller.arm(true);
 const posted=await controller.reply('c1','Thanks for watching');
 assert.equal(posted.status,'sent');
 assert.equal(outbound.length,1);
 assert.equal(outbound[0].streamId,target.streamId);
 assert.equal(outbound[0].replyToId,'c1');
 assert.ok(!JSON.stringify(outbound).includes('accessToken'));
 assert.equal(controller.status().sentCount,1);
});
test('denied authorization and moderation never produce platform writes',async()=>{
 for(const options of [{permission:false},{moderation:false}]){
   const {controller,outbound}=fixture({...options,mode:'automatic'});
   await controller.pollOnce();controller.arm(true);
   await assert.rejects(()=>controller.reply('c1','Thank you'),/denied|moderation|approval|authorization/i);
   assert.equal(outbound.length,0);
 }
});
test('provider or stream mismatch comments are refused, not imported',async()=>{
 const {controller,connector}=fixture();
 connector.read=async()=>[{id:'evil',provider:'other',streamId:'someone-else',authorId:'x',text:'hello'}];
 await assert.rejects(()=>controller.pollOnce(),/provider|stream|source/i);
 assert.equal(controller.status().knownComments,0);
});
test('confirmed chat posts are idempotent and cannot spam a viewer',async()=>{
 const {controller,outbound}=fixture({mode:'assisted'});
 await controller.pollOnce();controller.arm(true);
 await controller.reply('c1','Thank you');
 const duplicate=await controller.reply('c1','Again');
 assert.equal(duplicate.status,'already_sent');
 assert.equal(outbound.length,1);
});
test('ambiguous network response is not resent and remains unresolved',async()=>{
 const {controller,outbound}=fixture({mode:'automatic',sendResult:{status:'pending',provider:'youtube',streamId:'live-chat-001'}});
 await controller.pollOnce();controller.arm(true);
 await assert.rejects(()=>controller.reply('c1','Thank you'),/pending|unknown|confirm/i);
 await assert.rejects(()=>controller.reply('c1','Retry me'),/pending|unknown|inspection/i);
 assert.equal(outbound.length,1);
});
test('automatic responses obey rate limits and never post merely from reading',async()=>{
 let now=1000;
 const {controller,connector,outbound}=fixture({mode:'automatic',clock:()=>now});
 connector.read=async()=>[
   {id:'a',authorId:'a',text:'Question a',createdAt:now},
   {id:'b',authorId:'b',text:'Question b',createdAt:now}
 ];
 await controller.pollOnce();
 assert.equal(outbound.length,0);
 controller.arm(true);
 await controller.reply('a','First answer');
 await assert.rejects(()=>controller.reply('b','Second answer'),/rate|wait|throttl/i);
 now+=13000;
 await controller.reply('b','Second answer');
 assert.equal(outbound.length,2);
});
test('an unconfirmed send reserves its rate slot so a second comment cannot bypass throttling',async()=>{
 let now=1000;
 const {controller,connector,outbound}=fixture({mode:'automatic',clock:()=>now,
   sendResult:{status:'pending',provider:'youtube',streamId:'live-chat-001'}
 });
 connector.read=async()=>[
  {id:'c1',authorId:'user1',text:'First question'},
  {id:'c3',authorId:'user3',text:'Second question'}
 ];
 await controller.pollOnce();controller.arm(true);
 await assert.rejects(()=>controller.reply('c1','First attempt'),/pending|unknown/i);
 await assert.rejects(()=>controller.reply('c3','Second attempt'),/rate|wait|throttl/i);
 assert.equal(outbound.length,1);
});
test('autonomous live comment replies require a model, moderation and explicit arming',async()=>{
 const sent=[];
 const controller=new LiveCommentsController({
  provider:'youtube',streamId:'chat',
  connector:{read:async()=>[{id:'x1',text:'What verse?',authorId:'u1'}],
    post:async x=>{sent.push(x);return {status:'sent',provider:'youtube',streamId:'chat',messageId:'post1'};}
  },
  authorize:async ctx=>({allowed:true,provider:ctx.provider,streamId:ctx.streamId}),
  generateReply:async()=> 'John 3:16'
 });
 await controller.pollOnce();
 controller.setMode('automatic');controller.arm(true);
 await assert.rejects(()=>controller.respondToPending({max:1}),/moderation|approval/i);
 assert.equal(sent.length,0);
});
test('authorized automatic response loop posts a bounded approved reply without duplicating',async()=>{
 let now=1000;const outbound=[];
 const controller=new LiveCommentsController({
  provider:'youtube',streamId:'chat-1',clock:()=>now,
  connector:{
    read:async()=>[{id:'q1',text:'What passage is that?',authorId:'viewer'}],
    post:async payload=>{outbound.push(payload);return {status:'sent',provider:'youtube',streamId:'chat-1',messageId:'posted-1'};}
  },
  generateReply:async()=> 'John 3:16',
  moderateReply:async()=>({allowed:true}),
  authorize:async req=>({allowed:true,provider:req.provider,streamId:req.streamId,commentId:req.commentId})
 });
 await controller.pollOnce();
 controller.setMode('automatic');
 controller.arm(true);
 const first=await controller.respondToPending({max:1});
 assert.equal(first.sent,1);
 assert.equal(outbound.length,1);
 now+=13000;
 const second=await controller.respondToPending({max:1});
 assert.equal(second.sent,0);
 assert.equal(outbound.length,1);
});
test('simultaneous replies to one viewer comment cannot create duplicate public posts',async()=>{
 let allow;
 const pending=new Promise(resolve=>{allow=resolve;});
 const outbound=[];
 const controller=new LiveCommentsController({
  provider:'youtube',streamId:'race-chat',
  connector:{
   read:async()=>[{id:'same',text:'Hello',authorId:'viewer'}],
   post:async payload=>{
     outbound.push(payload);
     return {status:'sent',provider:'youtube',streamId:'race-chat',messageId:'sent-race'};
   }
  },
  authorize:async ctx=>{
   await pending;
   return {allowed:true,provider:ctx.provider,streamId:ctx.streamId,commentId:ctx.commentId};
  },
  moderateReply:async()=>({allowed:true}),
  clock:()=>1000
 });
 await controller.pollOnce();
 controller.setMode('automatic');controller.arm(true);
 const one=controller.reply('same','First response');
 const two=controller.reply('same','Duplicate response');
 allow();
 const outcomes=await Promise.allSettled([one,two]);
 assert.equal(outcomes.filter(v=>v.status==='fulfilled').length,1);
 assert.equal(outcomes.filter(v=>v.status==='rejected').length,1);
 assert.equal(outbound.length,1);
});
test('operator disarming a comment stream while authorization is pending blocks publication',async()=>{
 let resolveApproval,started;
 const wait=new Promise(resolve=>{resolveApproval=resolve;});
 const authStarted=new Promise(resolve=>{started=resolve;});
 const outbound=[];
 const controller=new LiveCommentsController({
  provider:'youtube',streamId:'revoked-chat',
  connector:{
   read:async()=>[{id:'question',text:'Hello',authorId:'viewer'}],
   post:async payload=>{outbound.push(payload);return {status:'sent',provider:'youtube',streamId:'revoked-chat',messageId:'result'};}
  },
  authorize:async ctx=>{
   started();
   await wait;
   return {allowed:true,provider:ctx.provider,streamId:ctx.streamId,commentId:ctx.commentId};
  },
  moderateReply:async()=>({allowed:true})
 });
 await controller.pollOnce();
 controller.setMode('automatic');controller.arm(true);
 const request=controller.reply('question','Thank you');
 await authStarted;
 controller.arm(false);
 resolveApproval();
 await assert.rejects(request,/armed|revoked|permission|authorization/i);
 assert.equal(outbound.length,0);
});
