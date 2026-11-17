import test from 'node:test';
import assert from 'node:assert/strict';
import {JpegFrameSplitter,findCueMatch,makeObservation} from '../src/local-observer.mjs';

test('MJPEG splitter recovers complete frames across transport chunk boundaries',()=>{
 const splitter=new JpegFrameSplitter();
 const frameA=Buffer.from([255,216,1,2,3,255,217]);
 const frameB=Buffer.from([255,216,4,5,255,217]);
 const output=[...splitter.feed(Buffer.from([0,255,216,1])),
   ...splitter.feed(Buffer.concat([Buffer.from([2,3,255]),frameA.subarray(6),frameB]))];
 assert.equal(output.length,2);
 assert.deepEqual(output[0],frameA);
 assert.deepEqual(output[1],frameB);
});
test('OCR/transcript cue confidence comes from match against actual deck text',()=>{
 const slides=[{id:'one',title:'Title',text:'A new morning is coming'},
               {id:'two',title:'Chorus',text:'We will sing and rejoice'}];
 const cue=findCueMatch('WE WILL SING AND REJOICE',slides);
 assert.equal(cue.slide.id,'two');
 assert.equal(cue.score,1);
 assert.ok(findCueMatch('someone is walking outside',slides).score<.83);
});
test('vision observation rejects low-signal text and preserves source context',()=>{
 const slides=[{id:'one',text:'We will sing and rejoice'}];
 const good=makeObservation({text:'We will sing and rejoice',confidence:.5},slides,{
    frameId:'a',cameraRole:'stage',timestamp:1000
 });
 assert.equal(good.frameId,'a');
 assert.equal(good.cameraRole,'stage');
 assert.ok(good.confidence>=.88);
 const bad=makeObservation({text:'random shadows',confidence:.08},slides,{
    frameId:'b',cameraRole:'speaker',timestamp:1001
 });
 assert.ok(bad.confidence<.88);
});
test('JPEG splitter rejects oversized frames to bound memory',()=>{
 const splitter=new JpegFrameSplitter({maxFrameBytes:16});
 const frame=Buffer.concat([Buffer.from([255,216]),Buffer.alloc(40,9),Buffer.from([255,217])]);
 assert.equal(splitter.feed(frame).length,0);
});
