import test from 'node:test';
import assert from 'node:assert/strict';
import {
  createWorshipLibrary,compileWorshipFromLibrary,buildServiceFromWorshipLibrary
} from '../src/worship-library.mjs';

const DENIED_ANNOUNCEMENT='ROOM_ONLY_MUST_NOT_STREAM';
const DENIED_SCRIPTURE='LICENSED_LOCAL_NKJV_FIXTURE_MUST_NOT_STREAM';

function setup({
  songStream=true,announcementStream=false,scriptureStream=false,
  songLines=['An original lyric line'],
  ids={song:'opening',announcement:'opening-s1-p2',scripture:'opening-s1-p3'},
  order=['song','announcement','scripture']
}={}){
 const library=createWorshipLibrary({
   schema:'toc.worship-library/v1',
   songs:[{
     id:'original-song',revision:'r1',title:'Original Worship Song',
     rights:{source:'original',displayAuthorized:true,streamAuthorized:songStream},
     sections:[{
       id:'v',label:'verse',lines:songLines,
       notes:'PRIVATE_SONG_REHEARSAL_NOTES',chords:['C']
     }],
     arrangements:[{id:'a',sectionIds:['v']}]
   }],
   scriptures:[{
     id:'licensed-scripture',revision:'r1',title:'Scripture Reference',
     reference:'John 3:16',translation:'NKJV',
     text:DENIED_SCRIPTURE,notes:'PRIVATE_PASTOR_NOTES',
     scriptureRights:{
       source:'licensed',licenseId:'local-owner-permission-fixture',
       displayAuthorized:true,streamAuthorized:scriptureStream
     }
   }],
   segments:[{
     id:'room-notice',revision:'r1',type:'announcement',
     title:'Room-only announcement',text:DENIED_ANNOUNCEMENT,
     publicAuthorized:true,streamAuthorized:announcementStream,
     notes:'PRIVATE_OPERATOR_NOTES'
   }]
 });
 const catalog=Object.fromEntries(library.listEntries().map(e=>[e.id,e]));
 const info={
   song:{slot:ids.song,sourceId:'original-song',sourceType:'song',arrangementId:'a'},
   announcement:{slot:ids.announcement,sourceId:'room-notice',sourceType:'segment'},
   scripture:{slot:ids.scripture,sourceId:'licensed-scripture',sourceType:'scripture'}
 };
 const plan={
   title:'TOC Owner Library Rights Test',theme:'dark',
   items:order.map(name=>{
     const def=info[name],record=catalog[def.sourceId];
     return {
       id:def.slot,sourceType:def.sourceType,sourceId:def.sourceId,
       revision:record.revision,sha256:record.sha256,
       ...(def.arrangementId?{arrangementId:def.arrangementId}:{})
     };
   })
 };
 return {library,plan,ids};
}
function compile(opts){const x=setup(opts);return {...x,compiled:compileWorshipFromLibrary(x.plan,x.library,{stageGrant:'private-owner'})};}
function assertSource(result,id,sourceId,sourceType,expectedSlot=id){
 const index=result.compiled.publicDeck.slides.findIndex(s=>s.id===id);
 assert.notEqual(index,-1,'Slide missing for '+id);
 const provenance=result.compiled.getCueSource(index,'private-owner');
 assert.equal(provenance.slotId,expectedSlot,'Wrong service slot for '+id);
 assert.equal(provenance.assetId,sourceId);
 assert.equal(provenance.sourceType,sourceType);
 assert.equal(result.compiled.getCueSource(index,'invalid'),null);
 return {
   audience:result.compiled.publicDeck.slides[index],
   broadcast:result.compiled.broadcastDeck.slides[index]
 };
}

test('P1 reproduction: stream-allowed song cannot authorize a generated-looking room-only announcement',()=>{
 const result=compile();
 const song=assertSource(result,'opening-s1-p1','original-song','song','opening');
 assert.equal(song.broadcast.text,'An original lyric line');
 const announcement=assertSource(result,'opening-s1-p2','room-notice','announcement');
 assert.equal(announcement.audience.text,DENIED_ANNOUNCEMENT);
 assert.equal(announcement.broadcast.text,'');
 const scripture=assertSource(result,'opening-s1-p3','licensed-scripture','scripture');
 assert.equal(scripture.audience.text,DENIED_SCRIPTURE);
 assert.equal(scripture.broadcast.text,'');
 assert.ok(!JSON.stringify(result.compiled.broadcastDeck).includes(DENIED_ANNOUNCEMENT));
 assert.ok(!JSON.stringify(result.compiled.broadcastDeck).includes(DENIED_SCRIPTURE));
 assert.ok(!JSON.stringify(result.compiled.broadcastDeck).includes('PRIVATE_'));
});

test('generated-looking segment and Scripture IDs cannot inherit song rights in varied service order',()=>{
 for(const order of [
   ['song','announcement','scripture'],
   ['announcement','song','scripture'],
   ['scripture','song','announcement'],
   ['announcement','scripture','song'],
   ['scripture','announcement','song'],
   ['song','scripture','announcement']
 ]){
   const result=compile({order});
   assert.equal(assertSource(result,'opening-s1-p2','room-notice','announcement').broadcast.text,'',order.join(','));
   assert.equal(assertSource(result,'opening-s1-p3','licensed-scripture','scripture').broadcast.text,'',order.join(','));
   assert.equal(assertSource(result,'opening-s1-p1','original-song','song','opening').broadcast.text,'An original lyric line');
 }
});

test('stream-approved announcement is visible even when generated-looking song source is stream-denied',()=>{
 const result=compile({songStream:false,announcementStream:true,scriptureStream:false});
 const song=assertSource(result,'opening-s1-p1','original-song','song','opening');
 const announcement=assertSource(result,'opening-s1-p2','room-notice','announcement');
 const scripture=assertSource(result,'opening-s1-p3','licensed-scripture','scripture');
 assert.equal(song.audience.text,'An original lyric line');
 assert.equal(song.broadcast.text,'');
 assert.equal(announcement.broadcast.text,DENIED_ANNOUNCEMENT);
 assert.equal(scripture.broadcast.text,'');
});

test('individual medium rights cannot spill between neighboring generated-looking slots',()=>{
 for(const combination of [
   {songStream:true,announcementStream:false,scriptureStream:true},
   {songStream:false,announcementStream:true,scriptureStream:false},
   {songStream:false,announcementStream:false,scriptureStream:true},
   {songStream:true,announcementStream:true,scriptureStream:false}
 ]){
   const result=compile(combination);
   const song=assertSource(result,'opening-s1-p1','original-song','song','opening');
   const ann=assertSource(result,'opening-s1-p2','room-notice','announcement');
   const scripture=assertSource(result,'opening-s1-p3','licensed-scripture','scripture');
   assert.equal(song.broadcast.text,combination.songStream?'An original lyric line':'');
   assert.equal(ann.broadcast.text,combination.announcementStream?DENIED_ANNOUNCEMENT:'');
   assert.equal(scripture.broadcast.text,combination.scriptureStream?DENIED_SCRIPTURE:'');
 }
});

test('true generated song slide ID colliding with exact segment slot is rejected in either ordering',()=>{
 for(const order of [['song','announcement'],['announcement','song']]){
   const {library,plan}=setup({songLines:['first line','second line','third line'],order});
   assert.throws(()=>compileWorshipFromLibrary(plan,library),/duplicate|collision|ambiguous|slide id|ownership/i);
 }
});

test('duplicate true service slot identifiers are rejected before compilation',()=>{
 const {library,plan}=setup({order:['song','announcement']});
 plan.items[1].id=plan.items[0].id;
 assert.throws(()=>compileWorshipFromLibrary(plan,library),/duplicate|collision/i);
});

test('generated-syntax exact slot preceding a real second song page fails closed on collision',()=>{
 const {library,plan}=setup({
   order:['scripture','announcement','song'],
   songLines:['first','second','third','fourth']
 });
 // The announcement's exact slot is now the song's actual second page ID.
 // Neither public nor stream output may claim two owners for this slide.
 assert.throws(()=>compileWorshipFromLibrary(plan,library),/duplicate|collision|ambiguous|ownership/i);
});

test('legacy library compatibility routes through same guarded provenance and denies room-only stream',()=>{
 const legacy={
   schema:'toc.worship.song-library/v1',songs:[{
     id:'original-song',title:'Original Worship Song',
     rights:{source:'original',displayAuthorized:true,streamAuthorized:true},
     sections:[{label:'verse',lines:['An original lyric line']}],
     defaultOrder:['verse']
   }]
 };
 const plan={
   title:'TOC Legacy Provenance Test',
   items:[
     {id:'opening',type:'song',songId:'original-song'},
     {id:'opening-s1-p2',type:'announcement',title:'Room-only announcement',
       text:DENIED_ANNOUNCEMENT,publicAuthorized:true,streamAuthorized:false}
   ]
 };
 const result=buildServiceFromWorshipLibrary(legacy,plan,{stageGrant:'private'});
 const index=result.publicDeck.slides.findIndex(s=>s.id==='opening-s1-p2');
 assert.ok(index>=0);
 assert.equal(result.publicDeck.slides[index].text,DENIED_ANNOUNCEMENT);
 assert.equal(result.broadcastDeck.slides[index].text,'');
 assert.equal(result.getCueSource(index,'private').slotId,'opening-s1-p2');
 assert.equal(result.getCueSource(index,'private').sourceType,'announcement');
});
