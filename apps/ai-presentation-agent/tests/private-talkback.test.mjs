import test from 'node:test';
import assert from 'node:assert/strict';
import {EventEmitter} from 'node:events';
import {parseMacSpeechOutputs,listMacSpeechOutputs,verifyPrivateSpeechOutput,speakMacPrivate}
 from '../src/private-talkback.mjs';

const sample='   94 USB Audio CODEC\n   88 USB Audio Device\n   76 iMac Speakers\n';
test('macOS speech output device discovery parses CoreAudio IDs without audio playback',async()=>{
 const outputs=await listMacSpeechOutputs({platform:'darwin',run:async(command,args)=>{
   assert.equal(command,'/usr/bin/say');
   assert.deepEqual(args,['-a','?']);
   return {stdout:sample};
 }});
 assert.deepEqual(outputs.map(x=>x.id),[94,88,76]);
 assert.deepEqual(parseMacSpeechOutputs(sample),outputs);
});
test('local spoken replies are forbidden without confirmed private device routing',async()=>{
 for(const opts of [
   {deviceId:null,confirmed:true},
   {deviceId:76,confirmed:false},
   {deviceId:111,confirmed:true}
 ]){
   await assert.rejects(()=>speakMacPrivate('A private status reply.',{
     ...opts,platform:'darwin',availableOutputs:[{id:76,name:'iMac Speakers'}],
     executor:()=>{throw Error('Must not try playback');}
   }),/private|explicit|unavailable|confirm/i);
 }
});
test('private speech routing invokes only the selected output ID after explicit operator confirmation',async()=>{
 const invocation=[];
 const executor=(command,args)=>{
   invocation.push({command,args});
   const child=new EventEmitter();
   queueMicrotask(()=>child.emit('close',0));
   return child;
 };
 const reply=await speakMacPrivate('Showing the chorus.',{
   deviceId:88,confirmed:true,
   availableOutputs:[{id:88,name:'Operator headphones'}],
   platform:'darwin',executor
 });
 assert.equal(reply.spoken,true);
 assert.deepEqual(invocation[0],{
   command:'/usr/bin/say',args:['-a','88','--','Showing the chorus.']
 });
});
test('invalid speech output text is rejected before audio commands',async()=>{
 await assert.rejects(()=>speakMacPrivate('a'.repeat(500),{
   deviceId:88,confirmed:true,availableOutputs:[{id:88}],platform:'darwin'
 }),/400/);
 assert.throws(()=>verifyPrivateSpeechOutput({deviceId:76,confirmed:false,
   availableOutputs:[{id:76}]}),/operator/i);
});
