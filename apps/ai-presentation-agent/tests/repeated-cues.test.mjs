import test from 'node:test';
import assert from 'node:assert/strict';
import {PresentationDirector} from '../src/director.mjs';
import {MemoryAdapter} from '../src/adapters.mjs';
import {BandMatesPresentationBridge} from '../integrations/bandmates.mjs';

const deck={title:'Repeated Chorus',slides:[
 {id:'welcome',title:'Welcome'},
 {id:'first-chorus',title:'Chorus A',song:'Sample Song',section:'chorus',occurrence:1,text:'We will sing with joy tonight'},
 {id:'verse',title:'Verse',song:'Sample Song',section:'verse 2',text:'A new morning breaks over us'},
 {id:'second-chorus',title:'Chorus B',song:'Sample Song',section:'chorus',occurrence:2,text:'We will sing with joy tonight'}
]};
function setup(){
 let now=10000;
 const director=new PresentationDirector({adapter:new MemoryAdapter(),clock:()=>now,cooldownMs:250});
 director.load(deck);
 return {director,advance:ms=>now+=ms};
}
test('multiple sensors seeing the same chorus do not jump to a repeated chorus',async()=>{
 const {director,advance}=setup();
 await director.start('automatic');
 assert.equal((await director.ingest({source:'bandmates',type:'song.section',song:'Sample Song',section:'chorus',eventId:'b1'})).changed,true);
 advance(1500);
 const duplicate=await director.ingest({source:'vision',type:'song.section',song:'Sample Song',section:'chorus',eventId:'v2'});
 assert.equal(duplicate.changed,false);
 assert.equal(duplicate.reason,'same_cue_still_active');
 assert.equal(director.snapshot().current.id,'first-chorus');
 advance(1000);
 await director.ingest({source:'bandmates',type:'song.section',song:'Sample Song',section:'verse 2',eventId:'v3'});
 assert.equal(director.snapshot().current.id,'verse');
 advance(1000);
 await director.ingest({source:'bandmates',type:'song.section',song:'Sample Song',section:'chorus',eventId:'b4'});
 assert.equal(director.snapshot().current.id,'second-chorus');
});
test('explicit BandMates occurrence increments allow consecutive repeated choruses',async()=>{
 const {director,advance}=setup();await director.start('automatic');
 await director.ingest({source:'bandmates',type:'song.section',song:'Sample Song',section:'chorus',occurrence:1,eventId:'occ1'});
 assert.equal(director.snapshot().current.id,'first-chorus');
 advance(2500);
 const next=await director.ingest({source:'bandmates',type:'song.section',song:'Sample Song',section:'chorus',occurrence:2,eventId:'occ2'});
 assert.equal(next.changed,true);
 assert.equal(director.snapshot().current.id,'second-chorus');
 advance(2500);
 const duplicate=await director.ingest({source:'bandmates',type:'song.section',song:'Sample Song',section:'chorus',occurrence:2,eventId:'newid'});
 assert.equal(duplicate.changed,false);
 assert.equal(duplicate.reason,'same_cue_still_active');
});
test('ordinary speaker transcript held on same chorus does not repeat the slide',async()=>{
 const {director,advance}=setup();await director.start('automatic');
 const one=await director.ingest({source:'speech',type:'transcript',text:'we will sing with joy tonight',confidence:.98,final:true,eventId:'speech1'});
 assert.equal(one.changed,true);
 advance(1800);
 const another=await director.ingest({source:'speech',type:'transcript',text:'we will sing with joy tonight',confidence:.98,final:true,eventId:'speech2'});
 assert.equal(another.changed,false);
 assert.equal(director.snapshot().current.id,'first-chorus');
});
test('BandMates bridge publishes only verified performed occurrence metadata',async()=>{
 const events=[];
 const bridge=new BandMatesPresentationBridge({song:'Sample Song',clock:()=>10000,
  ingest:async e=>{events.push(e);return {changed:true};}});
 const section=(occurrence,eventId)=>({sessionId:'s1',songDynamics:{
  section:'chorus',occurrence,beatIndex:(occurrence-1)*32,
  stateKind:'performed',performanceConfirmed:true,confidence:.99,
  eventId,timestamp:10000
 }});
 await bridge.observe(section(1,'occ-1'));
 await bridge.observe(section(2,'occ-2'));
 assert.deepEqual(events.map(x=>x.occurrence),[1,2]);
});
