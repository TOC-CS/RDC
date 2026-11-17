import test from 'node:test';
import assert from 'node:assert/strict';
import {PresentationDirector} from '../src/director.mjs';

const deck={slides:[{id:'opening',song:'Original',section:'intro'},
  {id:'chorus',song:'Original',section:'chorus'}]};

test('unknown physical output after a mismatched readback faults closed and blocks further cues',async()=>{
 let actual=0,writes=0;
 const adapter={name:'unsafe-external',external:true,requiresReadback:true,
   show:async(index)=>{actual=index;return {ok:true};},
   next:async()=>{writes++;actual=1;return {ok:true};},
   readback:async({expectedIndex})=>({supported:true,index:0,confirmed:expectedIndex===0})
 };
 const director=new PresentationDirector({adapter,cooldownMs:0});
 director.load(deck);await director.arm(true);await director.start('automatic');
 await assert.rejects(()=>director.command({action:'next'}),/readback|mismatch/i);
 const state=director.snapshot();
 assert.equal(state.index,0);
 assert.equal(state.held,true);
 assert.equal(state.armed,false);
 assert.equal(state.outputFaulted,true);
 assert.equal(writes,1);
 const event=await director.ingest({source:'bandmates',type:'song.section',song:'Original',section:'chorus',eventId:'replay-1'});
 assert.equal(event.reason,'output_fault');
 await assert.rejects(()=>director.command({action:'next'}),/fault|reload|resync/i);
 await assert.rejects(()=>director.command({action:'resume'}),/fault|reload|resync/i);
 await assert.rejects(()=>director.arm(true),/fault|reload|resync/i);
 assert.equal(writes,1);
 // Read-only reporting remains available without attempting another write.
 assert.equal((await director.command({action:'status'})).state.outputFaulted,true);
});

test('operator-controlled deck reload clears the fault without silently rearming an output',async()=>{
 let writes=0;
 const adapter={name:'no-ack',external:true,show:async()=>({ok:true}),next:async()=>{writes++;return {ok:false};}};
 const director=new PresentationDirector({adapter});
 director.load(deck);await director.arm(true);await director.start('manual');
 await assert.rejects(()=>director.command({action:'next'}),/rejected/i);
 assert.equal(director.snapshot().outputFaulted,true);
 director.load(deck);
 assert.equal(director.snapshot().outputFaulted,false);
 assert.equal(director.snapshot().armed,false);
 assert.equal(director.snapshot().started,false);
 assert.equal(writes,1);
});

test('native startup acknowledgment followed by failed readback remains faulted until operator reload',async()=>{
 let shows=0;
 const adapter={name:'external-first-frame',external:true,requiresReadback:true,
   show:async()=>{shows++;return {ok:true};},
   readback:async()=>({supported:true,confirmed:false,index:7})};
 const director=new PresentationDirector({adapter});
 director.load(deck);await director.arm(true);
 await assert.rejects(()=>director.start('automatic'),/readback|mismatch/i);
 const state=director.snapshot();
 assert.equal(state.started,false);
 assert.equal(state.armed,false);
 assert.equal(state.outputFaulted,true);
 await assert.rejects(()=>director.start('automatic'),/fault|reload/i);
 assert.equal(shows,1);
 director.load(deck);
 assert.equal(director.snapshot().outputFaulted,false);
});
