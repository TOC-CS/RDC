import test from 'node:test';
import assert from 'node:assert/strict';
import {BandMatesPresentationBridge} from '../integrations/bandmates.mjs';
import {PresentationDirector} from '../src/director.mjs';
import {MemoryAdapter} from '../src/adapters.mjs';

const deck={slides:[{id:'title',title:'Song'},
 {id:'verse',title:'Song',song:'New Song',section:'verse 1',text:'Bring the first verse'},
 {id:'chorus',title:'Song',song:'New Song',section:'chorus',text:'Raise the chorus'}]};
const performed=(section,occurrence,eventId,{sessionId='sid',timestamp=10000,beatIndex=0}={})=>({
 sessionId,
 songDynamics:{section,occurrence,beatIndex,stateKind:'performed',
  confidence:.99,performanceConfirmed:true,timestamp,eventId}
});
const planned=(section,occurrence,beatIndex=0)=>({
 sessionId:'sid',songDynamics:{section,occurrence,beatIndex,stateKind:'planned'}
});

test('BandMates planned accompaniment never drives lyrics; only independently verified performance does',async()=>{
 let now=10000;
 const director=new PresentationDirector({adapter:new MemoryAdapter(),clock:()=>now,cooldownMs:0});
 director.load(deck);await director.start('automatic');
 const bridge=new BandMatesPresentationBridge({song:'New Song',ingest:cue=>director.ingest(cue),clock:()=>now});
 assert.equal((await bridge.observe(planned('verse 1',1))).reason,'planned_section_requires_live_confirmation');
 assert.equal(director.snapshot().current.id,'title');
 assert.equal((await bridge.observe(performed('verse 1',1,'verified-verse'))).changed,true);
 assert.equal(director.snapshot().current.id,'verse');
 assert.equal((await bridge.observe(performed('verse 1',1,'verified-verse'))).reason,'unchanged');
 now+=500;
 assert.equal((await bridge.observe(planned('chorus',1,16))).changed,false);
 assert.equal(director.snapshot().current.id,'verse');
 assert.equal((await bridge.observe(performed('chorus',1,'verified-chorus',{beatIndex:16,timestamp:now}))).changed,true);
 assert.equal(director.snapshot().current.id,'chorus');
});

test('BandMates bridge does not infer live sections from MIDI notes, chords or tempo',async()=>{
 let sends=0;const bridge=new BandMatesPresentationBridge({song:'New Song',ingest:async()=>{sends++;}});
 const result=await bridge.observe({note:60,chord:'C',tempo:120,songDynamics:null});
 assert.equal(result.reason,'no_section');
 assert.equal(sends,0);
});

test('verified BandMates section identity follows song changes and separately confirmed repeated choruses',async()=>{
 const sent=[];const bridge=new BandMatesPresentationBridge({song:'First Song',
  clock:()=>10000,ingest:async cue=>{sent.push(cue);return {changed:true};}});
 await bridge.observe(performed('chorus',1,'first-chorus'));
 await bridge.observe(performed('chorus',2,'second-chorus',{beatIndex:64}));
 bridge.setSong('New Song');
 await bridge.observe(performed('chorus',1,'new-song-chorus'));
 assert.deepEqual(sent.map(x=>x.song),['First Song','First Song','New Song']);
 assert.deepEqual(sent.map(x=>x.occurrence),[1,2,1]);
 assert.ok(sent.every(x=>x.source==='bandmates'&&x.type==='song.section'));
});

test('confirmed cue rejected during presentation cooldown can retry with a distinct safe event ID',async()=>{
 let now=10000;
 const director=new PresentationDirector({adapter:new MemoryAdapter(),clock:()=>now,cooldownMs:350});
 director.load(deck);await director.start('automatic');
 const sent=[];
 const bridge=new BandMatesPresentationBridge({song:'New Song',clock:()=>now,
  ingest:async cue=>{sent.push(cue.eventId);return director.ingest(cue);}});
 const first=performed('verse 1',1,'verse-confirmed');
 const second=performed('chorus',1,'chorus-confirmed',{beatIndex:4});
 assert.equal((await bridge.observe(first)).changed,true);
 now+=15;
 assert.equal((await bridge.observe(second)).reason,'cooldown');
 now+=400;
 assert.equal((await bridge.observe(second)).changed,true);
 assert.equal(director.snapshot().current.id,'chorus');
 assert.notEqual(sent[1],sent[2],'Definitive non-delivery permits a new retry receipt');
});

test('verified cue rejected in assisted mode may advance after operator enables automatic mode',async()=>{
 let now=5000;
 const director=new PresentationDirector({adapter:new MemoryAdapter(),clock:()=>now});
 director.load(deck);await director.start('assisted');
 const bridge=new BandMatesPresentationBridge({song:'New Song',clock:()=>now,ingest:e=>director.ingest(e)});
 const chorus=performed('chorus',1,'assisted-chorus',{timestamp:now});
 assert.equal((await bridge.observe(chorus)).reason,'assisted_mode');
 await director.command({action:'mode',mode:'automatic'});
 assert.equal((await bridge.observe(chorus)).changed,true);
});

test('unknown transport outcome keeps the same verified event identity and does not invent a new send',async()=>{
 let n=0;const ids=[];
 const bridge=new BandMatesPresentationBridge({song:'New Song',clock:()=>10000,
  ingest:async e=>{
   ids.push(e.eventId);
   if(++n===1)throw new Error('network timeout after possible remote write');
   return {changed:false,reason:'duplicate'};
  }});
 const current=performed('chorus',1,'stable-native-chorus',{sessionId:'S',beatIndex:4});
 await assert.rejects(()=>bridge.observe(current),/network timeout/);
 assert.equal((await bridge.observe(current)).reason,'duplicate');
 assert.equal(ids[0],ids[1],'An uncertain transport reuses the exact original event ID');
});
