import test from 'node:test';
import assert from 'node:assert/strict';
import {platform} from 'node:os';
import {access} from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {JpegFrameSplitter,makeObservation} from '../src/local-observer.mjs';
import {MemoryAdapter} from '../src/adapters.mjs';
import {PresentationDirector} from '../src/director.mjs';
import {VisualObservationRouter} from '../src/watch.mjs';

const fixture=fileURLToPath(new URL('../evidence/worship-demo-first-slide.png',import.meta.url));
const ocr=fileURLToPath(new URL('../native/macos/build/stage-ocr',import.meta.url));
async function tool(command,args,input=null){
 return await new Promise((resolve,reject)=>{
   const child=spawn(command,args,{stdio:['pipe','pipe','pipe']});
   const chunks=[];let stderr='',settled=false;
   const done=(error,value)=>{
     if(settled)return;settled=true;clearTimeout(timer);
     return error?reject(error):resolve(value);
   };
   const timer=setTimeout(()=>{child.kill('SIGKILL');done(new Error('Offline OCR/video tool timeout.'));},12000);
   child.stdout.on('data',buffer=>chunks.push(buffer));
   child.stderr.on('data',buffer=>{if(stderr.length<1000)stderr+=String(buffer);});
   child.once('error',done);
   child.once('close',code=>code===0?
     done(null,Buffer.concat(chunks)):done(new Error('Offline vision tool failed: '+stderr.slice(0,250))));
   child.stdin.end(input??undefined);
 });
}
test('real FFmpeg MJPEG frames and local Apple Vision OCR can drive a synthetic stage cue',async(t)=>{
 if(platform()!=='darwin')return t.skip('Apple Vision requires macOS');
 try{await access(fixture);await access(ocr);}catch{return t.skip('native OCR or fixture missing');}
 // A prerecorded synthetic fixture exercises the exact streaming/OCR route;
 // it does not invoke the webcam or certify physical projector behavior.
 const stream=await tool('ffmpeg',['-hide_banner','-nostdin','-loglevel','error',
   '-loop','1','-i',fixture,'-frames:v','3','-q:v','4',
   '-vcodec','mjpeg','-f','image2pipe','pipe:1']);
 const splitter=new JpegFrameSplitter();
 const chunkSize=17_213,frames=[];
 for(let i=0;i<stream.length;i+=chunkSize)
   frames.push(...splitter.feed(stream.subarray(i,i+chunkSize)));
 assert.equal(frames.length,3,'FFmpeg fixture should emit exactly three JPEG frames.');
 const results=[];
 for(const jpeg of frames){
   const raw=await tool(ocr,['-'],jpeg);
   results.push(JSON.parse(raw.toString('utf8')));
 }
 assert.ok(results.every(o=>o.engine==='Apple Vision'&&o.text.includes('Worship Service')));
 let ms=10_000;
 const now=()=>ms;
 const deck={slides:[
   {id:'intro',text:'Introduction and welcome to the gathering'},
   {id:'stage-reference',text:'Worship Service Al Presentation Agent demonstration'}
 ]};
 const director=new PresentationDirector({adapter:new MemoryAdapter(),clock:now,cooldownMs:0});
 director.load(deck);await director.start('automatic');
 const visual=new VisualObservationRouter(director,{clock:now,holdMs:200});
 const receipts=[];
 for(let i=0;i<3;i++){
   const obs=makeObservation(results[i],director.snapshot().slides,{
     frameId:'synthetic-stage-'+i,cameraRole:'stage',timestamp:ms
   });
   receipts.push(await visual.receive(obs));ms+=250;
 }
 assert.equal(receipts[0].reason,'confirming');
 assert.equal(receipts[1].changed,true);
 assert.equal(director.snapshot().current.id,'stage-reference');
});
test('presentation-output camera role cannot create a feedback loop',async()=>{
 const director=new PresentationDirector({adapter:new MemoryAdapter(),clock:()=>5000,cooldownMs:0});
 director.load({slides:[{id:'a'},{id:'b',text:'Worship Service Al Presentation Agent demonstration'}]});
 await director.start('automatic');
 const visual=new VisualObservationRouter(director,{clock:()=>5000,holdMs:0});
 const observation={cameraRole:'presentation-output',confidence:.98,final:true,
    observedText:'Worship Service Al Presentation Agent demonstration',timestamp:5000};
 for(let i=0;i<4;i++){
   const receipt=await visual.receive({...observation,frameId:'projection-frame-'+i});
   assert.equal(receipt.reason,'feedback_source');
 }
 assert.equal(director.snapshot().index,0);
});
