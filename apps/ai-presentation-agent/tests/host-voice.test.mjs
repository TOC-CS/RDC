import test from 'node:test';
import assert from 'node:assert/strict';
import {VoiceChat, VoiceInputRouter, voiceCapabilities} from '../src/voice.mjs';
import {PresentationDirector} from '../src/director.mjs';
import {MemoryAdapter} from '../src/adapters.mjs';

const deck={slides:[{id:'intro',title:'Introduction'},{id:'one',title:'Test Slide',text:'Raise your voices together now',cues:['raise your voices together now']}]};
test('voice defaults to host AI platform and does not require local STT/TTS',async()=>{
 const director=new PresentationDirector({adapter:new MemoryAdapter()});
 director.load(deck); await director.start('assisted');
 const router=new VoiceInputRouter(director);
 const result=await router.receive({transcript:'presentation agent next slide',final:true,confidence:1});
 assert.equal(result.accepted,true);
 assert.equal(result.delivery,'host');
 assert.equal(result.speakByHost,true);
 assert.equal(director.snapshot().current.id,'one');
 assert.equal(voiceCapabilities().default,'host');
});
test('host voice ignores unconfirmed transcript fragments and weak recognition',async()=>{
 const director=new PresentationDirector({adapter:new MemoryAdapter()});
 director.load(deck); await director.start('automatic');
 const router=new VoiceInputRouter(director);
 for(const item of [{transcript:'presentation agent next slide',final:false,confidence:1},
                    {transcript:'presentation agent next slide',final:true,confidence:.55}]){
  const res=await router.receive(item);
  assert.equal(res.accepted,false);
 }
 assert.equal(director.snapshot().current.id,'intro');
});
test('host voice can route ordinary speech as the live-presentation signal without executing commands',async()=>{
 const director=new PresentationDirector({adapter:new MemoryAdapter(),clock:()=>5000});
 director.load(deck); await director.start('automatic');
 const router=new VoiceInputRouter(director);
 const r=await router.receive({transcript:'raise your voices together now',confidence:.96,final:true});
 assert.equal(r.commandAccepted,false);
 assert.equal(r.follow.changed,true);
 assert.equal(director.snapshot().current.id,'one');
});
test('local voice is an explicit optional selection and needs configured engines',()=>{
 assert.deepEqual(voiceCapabilities({localSttModel:'/tmp/locally-supplied-model.bin'}).modes,['host','local']);
 assert.equal(voiceCapabilities().local.sttReady,false);
});
