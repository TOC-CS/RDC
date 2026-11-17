import test from 'node:test';
import assert from 'node:assert/strict';
import {PcmSlidingWindowQueue,LocalVoiceCommandGate} from '../src/sliding-audio.mjs';

test('sliding PCM windows overlap across chunk boundaries and preserve exact sample order',()=>{
 const stream=new PcmSlidingWindowQueue({framesPerWindow:8,hopFrames:4,maxBytes:64});
 const pcm=Buffer.alloc(16*2);
 for(let i=0;i<16;i++)pcm.writeInt16LE(i,2*i);
 const windows=[
   ...stream.feed(pcm.subarray(0,12)),
   ...stream.feed(pcm.subarray(12,28)),
   ...stream.feed(pcm.subarray(28))
 ];
 assert.equal(windows.length,3);
 assert.deepEqual(windows.map(b=>Array.from({length:8},(_,i)=>b.readInt16LE(2*i))),[
   [0,1,2,3,4,5,6,7],
   [4,5,6,7,8,9,10,11],
   [8,9,10,11,12,13,14,15]
 ]);
});
test('large PCM read cannot grow past its configured memory limit or return stale unbounded windows',()=>{
 const q=new PcmSlidingWindowQueue({framesPerWindow:8,hopFrames:2,maxBytes:48});
 const frames=q.feed(Buffer.alloc(2000));
 assert.ok(q.buffer.length<=48);
 assert.ok(frames.length<=2);
 assert.ok(frames.every(b=>b.length===16));
});
test('same voice command requires independent confirmation and remains latched',()=>{
 const g=new LocalVoiceCommandGate();
 const cmd={action:'next'};
 assert.equal(g.observe(cmd,1000).reason,'confirming');
 assert.equal(g.observe(cmd,1200).confirmed,true);
 for(let at=1400;at<=2600;at+=200)
   assert.equal(g.observe(cmd,at).reason,'already_executed');
 assert.equal(g.observe(null,2700).confirmed,false);
 assert.equal(g.observe(null,2900).confirmed,false);
 assert.equal(g.observe(cmd,3000).confirmed,false);
 assert.equal(g.observe(cmd,3200).confirmed,true);
});
test('distinct hold command can execute after next without waiting for the stale latch to expire',()=>{
 const g=new LocalVoiceCommandGate();
 g.observe({action:'next'},1000);assert.equal(g.observe({action:'next'},1200).confirmed,true);
 assert.equal(g.observe({action:'hold'},1400).confirmed,false);
 assert.equal(g.observe({action:'hold'},1600).confirmed,true);
});
test('uncertain or stale speech never becomes a confirmed command',()=>{
 const g=new LocalVoiceCommandGate();
 g.observe({action:'next'},1000);
 assert.equal(g.observe(null,1200).confirmed,false);
 assert.equal(g.observe({action:'next'},1400).confirmed,false);
 assert.equal(g.observe({action:'next'},10000).confirmed,false);
 assert.equal(g.observe({action:'next'},10100).confirmed,true);
});
test('invalid window sizes and malformed voice commands fail fast',()=>{
 assert.throws(()=>new PcmSlidingWindowQueue({framesPerWindow:3,hopFrames:4}),/window/i);
 assert.throws(()=>new LocalVoiceCommandGate({confirmations:1}),/confirmation/i);
 assert.throws(()=>new LocalVoiceCommandGate().observe({action:null}),/command/i);
});
