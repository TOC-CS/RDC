import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createMcpHandler} from '../src/mcp.mjs';
import {LiveCommentsController} from '../src/live-comments.mjs';

const rpc=(name,args={})=>({
 jsonrpc:'2.0',id:1,method:'tools/call',params:{name,arguments:args}
});
test('one AI host can create a presentation, follow music, prepare a live reply, and export PowerPoint without public writes',async()=>{
 const directory=await mkdtemp(join(tmpdir(),'ai-presentation-integrated-'));
 let networkWrites=0;
 const comments=new LiveCommentsController({
  provider:'youtube',streamId:'mock-broadcast',
  connector:{
    read:async()=>[{id:'viewer01',text:'Which Scripture comes next?',authorId:'audience'}],
    post:async()=>{networkWrites++;return {status:'sent',provider:'youtube',streamId:'mock-broadcast',messageId:'posted'};}
  },
  authorize:async()=>({allowed:false}),
  generateReply:async()=> 'The next Scripture reading will be John 3:16.',
  moderateReply:async()=>({allowed:true})
 });
 const handler=createMcpHandler({
  exportRoot:directory,
  liveCommentsAgent:comments,
  allowLiveCommentPosting:false,
  clock:()=>10000
 });
 const call=async(name,args)=>{
  const out=(await handler(rpc(name,args))).result;
  assert.equal(out.isError,undefined,JSON.stringify(out));
  return out.structuredContent;
 };
 try{
  const caps=await call('presentation_capabilities',{});
  assert.equal(caps.liveComments.connected,true);
  assert.equal(caps.liveComments.postingAllowed,false);
  assert.ok(caps.exportFormats.includes('pptx'));
  await call('presentation_create',{
    title:'Service in Progress',theme:'dark',
    sections:[
      {title:'Song',kind:'lyrics',song:'Original Song',section:'chorus',
        points:['We give thanks together'],cues:['we give thanks together']},
      {title:'Scripture Reading',kind:'scripture',reference:'John 3:16',
        points:['The Gospel reading']}
    ]
  });
  await call('presentation_start',{mode:'automatic'});
  const cue=await call('presentation_cue',{
    source:'bandmates',type:'song.section',song:'Original Song',section:'chorus',
    occurrence:1,eventId:'song-chorus-1'
  });
  assert.equal(cue.changed,true);
  const status=await call('presentation_status',{});
  assert.equal(status.current.section,'chorus');
  const voice=await call('presentation_voice',{
    transcript:'presentation agent what slide are we on',confidence:1,final:true
  });
  assert.equal(voice.accepted,true);
  assert.equal(voice.speakByHost,true);
  const page=await call('live_comments_read',{});
  assert.equal(page.newComments.length,1);
  const draft=await call('live_comments_draft',{commentId:'viewer01'});
  assert.match(draft.text,/John 3:16/);
  const refused=await handler(rpc('live_comments_arm',{enabled:true}));
  assert.equal(refused.result.isError,true);
  assert.equal(networkWrites,0);
  const exported=await call('presentation_export_pptx',{name:'service-intro'});
  assert.equal(exported.format,'pptx');
  const bytes=await readFile(exported.file);
  assert.equal(bytes.subarray(0,2).toString('ascii'),'PK');
  const after=await call('presentation_status',{});
  assert.equal(after.current.id,status.current.id);
 }finally{await rm(directory,{recursive:true,force:true});}
});
