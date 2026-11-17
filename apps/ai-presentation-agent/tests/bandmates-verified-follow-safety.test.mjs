import test from 'node:test';
import assert from 'node:assert/strict';
import {BandMatesPresentationBridge} from '../integrations/bandmates.mjs';
import {PresentationDirector} from '../src/director.mjs';
import {MemoryAdapter} from '../src/adapters.mjs';

const now=1_000_000;
const deck={title:'Owner-authored service',slides:[
 {id:'welcome',title:'Opening'},
 {id:'chorus-one',song:'Original Hymn',section:'chorus',occurrence:1,text:'Original chorus'},
 {id:'verse',song:'Original Hymn',section:'verse 2',occurrence:1,text:'Original verse'},
 {id:'chorus-two',song:'Original Hymn',section:'chorus',occurrence:2,text:'Original chorus'}
]};
const verified=(overrides={})=>({
 sessionId:'verified-live-session',songDynamics:{
  stateKind:'performed',section:'chorus',occurrence:1,beatIndex:4,
  performanceConfirmed:true,confidence:0.98,
  eventId:'native-occurred-1',timestamp:now,
  ...overrides
 }
});

test('planned accompaniment sections stay preview-only and never invoke presentation auto-advance',async()=>{
 const director=new PresentationDirector({adapter:new MemoryAdapter(),clock:()=>now,cooldownMs:0});
 director.load(deck);
 await director.start('automatic');
 let calls=0;
 const bridge=new BandMatesPresentationBridge({
  song:'Original Hymn',clock:()=>now,
  ingest:cue=>{calls++;return director.ingest(cue);}
 });
 const planned=verified({stateKind:'planned'});
 assert.equal((await bridge.observe(planned)).changed,false);
 assert.equal(calls,0);
 assert.equal(director.snapshot().current.id,'welcome');
});

test('missing, stale, weak or unverified performer evidence cannot emit a cue',async()=>{
 const sent=[];
 const bridge=new BandMatesPresentationBridge({
  song:'Original Hymn',clock:()=>now,ingest:cue=>{sent.push(cue);return {changed:true};}
 });
 const cases=[
  verified({performanceConfirmed:false}),
  verified({confidence:.7}),
  verified({timestamp:now-5001}),
  verified({timestamp:now+5001}),
  verified({timestamp:undefined}),
  verified({eventId:undefined}),
  verified({eventId:'../unsafe'}),
  verified({occurrence:0}),
  verified({occurrence:undefined}),
  verified({stateKind:undefined}),
  {...verified(),sessionId:undefined},
  {...verified(),sessionId:'../foreign'}
 ];
 for(const candidate of cases){
  const result=await bridge.observe(candidate);
  assert.equal(result.changed,false,JSON.stringify(candidate));
 }
 assert.equal(sent.length,0);
});

test('confirmed performer occurrence advances in the existing director exactly once',async()=>{
 const director=new PresentationDirector({adapter:new MemoryAdapter(),clock:()=>now,cooldownMs:0});
 director.load(deck);
 await director.start('automatic');
 let sends=0;
 const bridge=new BandMatesPresentationBridge({
  song:'Original Hymn',clock:()=>now,
  ingest:cue=>{sends++;return director.ingest(cue);}
 });
 const first=await bridge.observe(verified());
 assert.equal(first.changed,true);
 assert.equal(director.snapshot().current.id,'chorus-one');
 const duplicate=await bridge.observe(verified());
 assert.equal(duplicate.changed,false);
 assert.equal(sends,1);
 const second=await bridge.observe(verified({occurrence:2,eventId:'native-occurred-2'}));
 assert.equal(second.changed,true);
 assert.equal(director.snapshot().current.id,'chorus-two');
 assert.equal(sends,2);
});

test('explicit nonexistent chorus occurrence is held instead of silently choosing another repeated chorus',async()=>{
 const director=new PresentationDirector({adapter:new MemoryAdapter(),clock:()=>now,cooldownMs:0});
 director.load(deck);
 await director.start('automatic');
 const result=await director.ingest({
  source:'bandmates',type:'song.section',song:'Original Hymn',
  section:'chorus',occurrence:3,eventId:'native-occurrence-not-in-plan',timestamp:now
 });
 assert.equal(result.changed,false);
 assert.equal(result.reason,'no_confident_match');
 assert.equal(director.snapshot().current.id,'welcome');
});

test('single unnumbered legacy verse may still match its first verified occurrence',async()=>{
 const director=new PresentationDirector({adapter:new MemoryAdapter(),clock:()=>now,cooldownMs:0});
 director.load({slides:[
  {id:'opening'}, {id:'verse',song:'Original Hymn',section:'verse 1'}
 ]});
 await director.start('automatic');
 const first=await director.ingest({
  source:'bandmates',type:'song.section',song:'Original Hymn',section:'verse',
  occurrence:1,eventId:'verified-first-verse',timestamp:now
 });
 assert.equal(first.changed,true);
 assert.equal(director.snapshot().current.id,'verse');
});
