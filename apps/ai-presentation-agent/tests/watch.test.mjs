import test from 'node:test';
import assert from 'node:assert/strict';
import {VisualObservationRouter} from '../src/watch.mjs';
import {PresentationDirector} from '../src/director.mjs';
import {MemoryAdapter} from '../src/adapters.mjs';
const deck={slides:[{id:'intro',title:'Welcome',text:'Welcome to the service'},
  {id:'verse',title:'Test Song',song:'Test Song',section:'verse 1',text:'Come and see the morning sun'},
  {id:'chorus',title:'Test Song',song:'Test Song',section:'chorus',text:'We will sing and rejoice'},
  {id:'scripture',title:'John 3:16',reference:'John 3:16',text:'For God so loved the world'}]};
function make(){
 let now=10000;const director=new PresentationDirector({adapter:new MemoryAdapter(),clock:()=>now,cooldownMs:150});
 director.load(deck);
 const vision=new VisualObservationRouter(director,{clock:()=>now,holdMs:90});
 return {director,vision,setTime:v=>{now=v}};
}
test('visual route forbids screenshot feedback from presentation output',async()=>{
 const {director,vision}=make();await director.start('automatic');
 const r=await vision.receive({frameId:'f1',cameraRole:'presentation-output',confidence:.99,final:true,recognizedSong:'Test Song',recognizedSection:'chorus'});
 assert.equal(r.changed,false);assert.equal(r.reason,'feedback_source');
 assert.equal(director.snapshot().current.id,'intro');
});
test('visual confidence and repeated stable observations needed before changing lyrics',async()=>{
 const {director,vision,setTime}=make();await director.start('automatic');
 const frame={cameraRole:'stage',confidence:.98,final:true,recognizedSong:'Test Song',recognizedSection:'chorus'};
 const a=await vision.receive({...frame,frameId:'first'});assert.equal(a.reason,'confirming');
 setTime(10100);
 const b=await vision.receive({...frame,frameId:'second'});assert.equal(b.changed,true);
 assert.equal(director.snapshot().current.id,'chorus');
 const c=await vision.receive({...frame,frameId:'second'});assert.equal(c.reason,'duplicate');
});
test('visual observation rejects stale and weak frames',async()=>{
 const {director,vision,setTime}=make();await director.start('automatic');
 const weak=await vision.receive({frameId:'f1',cameraRole:'speaker',confidence:.52,final:true,recognizedReference:'John 3:16'});
 assert.equal(weak.reason,'uncertain');
 setTime(12000);
 const stale=await vision.receive({frameId:'f2',cameraRole:'speaker',confidence:.95,final:true,recognizedReference:'John 3:16',timestamp:100});
 assert.equal(stale.reason,'stale');
});
test('watching gesture advance is confirmed over two independent frames and does not repeat endlessly',async()=>{
 const {director,vision,setTime}=make();await director.start('automatic');
 const one=await vision.receive({frameId:'g1',cameraRole:'stage',confidence:.99,final:true,gesture:'next'});
 assert.equal(one.changed,false);
 setTime(10120);
 const two=await vision.receive({frameId:'g2',cameraRole:'stage',confidence:.99,final:true,gesture:'next'});
 assert.equal(two.changed,true);assert.equal(director.snapshot().current.id,'verse');
 setTime(10500);
 const repeat=await vision.receive({frameId:'g3',cameraRole:'stage',confidence:.99,final:true,gesture:'next'});
 assert.equal(repeat.changed,false);assert.equal(director.snapshot().current.id,'verse');
});
test('visual cue respects manual hold and source mode',async()=>{
 const {director,vision,setTime}=make();await director.start('automatic');
 await director.command({action:'hold'});
 const cue={cameraRole:'speaker',confidence:.99,final:true,recognizedReference:'John 3:16'};
 await vision.receive({...cue,frameId:'a'});setTime(10100);
 const r=await vision.receive({...cue,frameId:'b'});
 assert.equal(r.reason,'held');assert.equal(director.snapshot().current.id,'intro');
});
