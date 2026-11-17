import test from 'node:test';
import assert from 'node:assert/strict';
import {WorshipTeleprompter} from '../src/worship-teleprompt.mjs';

const speaker='PRIVATE SPEAKER: Welcome to the service.\nPRIVATE SPEAKER: We will explain the passage.\nPRIVATE SPEAKER: Thank you for listening.';
const lyric='We sing with joy today\nWe lift our voices higher\nWe sing together now';
const cue=(id='chorus-1')=>({id,title:'Original service',text:lyric,notes:speaker,section:'chorus'});

test('private prompt uses the current stage cue and separate singer/speaker/reader source',()=>{
 const t=new WorshipTeleprompter({clock:()=>10000});
 assert.equal(t.snapshot().loaded,false);
 t.configure({role:'singer',fontScale:1.4,scrollSpeed:1.25,mirrored:true});
 t.syncCue(cue());
 const singer=t.snapshot();
 assert.equal(singer.loaded,true);
 assert.equal(singer.role,'singer');
 assert.equal(singer.current,'We sing with joy today');
 assert.equal(singer.next,'We lift our voices higher');
 assert.equal(singer.mirrored,true);
 assert.equal(singer.fontScale,1.4);
 assert.equal(singer.scrollSpeed,1.25);
 assert.equal(singer.slideId,'chorus-1');
 t.configure({role:'speaker',fontScale:1.2,scrollSpeed:1,mirrored:false});
 assert.match(t.snapshot().current,/PRIVATE SPEAKER/);
 t.configure({role:'reader',fontScale:1.3,scrollSpeed:1.1,mirrored:false});
 assert.equal(t.snapshot().current,'We sing with joy today');
});

test('final verified speech advances private scroll cursor without moving the actual presentation',()=>{
 let time=10000;
 const t=new WorshipTeleprompter({clock:()=>time});
 t.configure({role:'singer',scrollSpeed:1,fontScale:1.3,mirrored:false});
 t.syncCue(cue());
 for(const candidate of [
  {text:'We lift our voices higher',confidence:.99,final:false,eventId:'partial',timestamp:time},
  {text:'We lift our voices higher',confidence:.6,final:true,eventId:'weak',timestamp:time},
  {text:'We lift our voices higher',confidence:.99,final:true,eventId:'old',timestamp:time-6000},
  {text:'unrelated speech about announcements',confidence:.99,final:true,eventId:'unknown',timestamp:time}
 ]){
  const receipt=t.follow(candidate);
  assert.equal(receipt.changed,false);
  assert.equal(t.snapshot().position,0);
 }
 const valid={text:'We lift our voices higher',confidence:.99,final:true,
  eventId:'actual-phrase-2',timestamp:time};
 const result=t.follow(valid);
 assert.equal(result.changed,true);
 assert.equal(t.snapshot().position,1);
 assert.equal(t.snapshot().current,'We lift our voices higher');
 assert.equal(t.snapshot().next,'We sing together now');
 assert.equal(t.snapshot().automaticSlideAdvance,false);
 const repeat=t.follow(valid);
 assert.equal(repeat.changed,false);
 assert.equal(repeat.reason,'duplicate');
 assert.throws(()=>t.follow({...valid,text:'Different words entered'}),/identity conflict/i);
});

test('manual hold blocks speech while manual next/previous remain independently available',()=>{
 const t=new WorshipTeleprompter({clock:()=>20000});
 t.configure({role:'singer',fontScale:1.5,scrollSpeed:1,mirrored:false});
 t.syncCue(cue());
 assert.equal(t.hold().held,true);
 assert.equal(t.follow({text:'We sing together now',confidence:.99,final:true,eventId:'held',timestamp:20000}).reason,'held');
 assert.equal(t.snapshot().position,0);
 assert.equal(t.next().position,1);
 assert.equal(t.previous().position,0);
 assert.equal(t.resume().held,false);
 assert.equal(t.follow({text:'We sing together now',confidence:.99,final:true,eventId:'resumed',timestamp:20000}).changed,true);
 assert.equal(t.snapshot().position,2);
});

test('repeated same-title song sections reset only when authoritative slide ID changes',()=>{
 const t=new WorshipTeleprompter({clock:()=>30000});
 t.configure({role:'singer',fontScale:1.3,scrollSpeed:1,mirrored:false});
 t.syncCue(cue('chorus-occ-1'));
 t.next();
 t.syncCue(cue('chorus-occ-1'));
 assert.equal(t.snapshot().position,1);
 t.syncCue(cue('chorus-occ-2'));
 assert.equal(t.snapshot().position,0);
 assert.equal(t.snapshot().slideId,'chorus-occ-2');
 t.clear();
 assert.equal(t.snapshot().loaded,false);
 assert.equal(JSON.stringify(t.snapshot()).includes('PRIVATE SPEAKER'),false);
});

test('invalid role, configuration, oversized scripts and future partial events fail closed',()=>{
 const t=new WorshipTeleprompter({clock:()=>40000});
 assert.throws(()=>t.configure({role:'admin',fontScale:1.3,scrollSpeed:1,mirrored:false}),/role/i);
 assert.throws(()=>t.configure({role:'singer',fontScale:99,scrollSpeed:1,mirrored:false}),/font/i);
 assert.throws(()=>t.configure({role:'singer',fontScale:1.3,scrollSpeed:1,mirrored:'true'}),/mirror/i);
 assert.throws(()=>t.syncCue({id:'bad',text:'a'.repeat(30000),notes:''}),/too long|size|text/i);
 t.configure({role:'singer',fontScale:1.3,scrollSpeed:1,mirrored:false});
 t.syncCue(cue());
 assert.equal(t.follow({text:'We lift our voices higher',confidence:.99,final:true,eventId:'future',timestamp:50000}).changed,false);
 assert.equal(t.snapshot().position,0);
});
