import test from 'node:test';
import assert from 'node:assert/strict';
import {VoiceInputRouter} from '../src/voice.mjs';
import {PresentationDirector} from '../src/director.mjs';
import {MemoryAdapter} from '../src/adapters.mjs';

function setup(){
 const director=new PresentationDirector({adapter:new MemoryAdapter()});
 director.load({slides:[{id:'one',title:'One'},{id:'two',title:'Two'},{id:'three',title:'Three'}]});
 return director;
}
test('identical retransmitted host voice command advances one slide and speaks only once',async()=>{
 const director=setup();await director.start('automatic');
 const voice=new VoiceInputRouter(director);
 const utterance={transcript:'presentation agent next slide',confidence:.99,
   final:true,eventId:'host-voice-001',source:'chatgpt-host'};
 const [first,duplicate]=await Promise.all([voice.receive(utterance),voice.receive({...utterance})]);
 assert.equal(first.accepted,true);
 assert.equal(first.commandAccepted,true);
 assert.equal(first.speakByHost,true);
 assert.equal(duplicate.reason,'duplicate_voice_command');
 assert.equal(duplicate.speakByHost,false);
 assert.equal(duplicate.commandAccepted,false);
 assert.equal(director.snapshot().current.id,'two');
 const later=await voice.receive(utterance);
 assert.equal(later.reason,'duplicate_voice_command');
 assert.equal(director.snapshot().current.id,'two');
});
test('one voice event identity cannot be reused for another command',async()=>{
 const director=setup();await director.start('manual');
 const voice=new VoiceInputRouter(director);
 await voice.receive({transcript:'presentation agent next slide',eventId:'event-9',source:'host'});
 await assert.rejects(()=>voice.receive({transcript:'presentation agent previous slide',eventId:'event-9',source:'host'}),/voice event|identity|conflict/i);
 assert.equal(director.snapshot().current.id,'two');
});
test('new deck resets the voice receipt scope',async()=>{
 const director=setup();await director.start('manual');
 const voice=new VoiceInputRouter(director);
 await voice.receive({transcript:'presentation agent next slide',eventId:'voice-same',source:'host'});
 director.load({slides:[{id:'new1'},{id:'new2'}]});
 await director.start('manual');
 const next=await voice.receive({transcript:'presentation agent next slide',eventId:'voice-same',source:'host'});
 assert.equal(next.commandAccepted,true);
 assert.equal(director.snapshot().current.id,'new2');
});
test('invalid excessively long voice event identity is refused before a slide change',async()=>{
 const director=setup();await director.start('manual');
 const voice=new VoiceInputRouter(director);
 await assert.rejects(()=>voice.receive({transcript:'presentation agent next slide',eventId:'z'.repeat(400)}),/event.*id/i);
 assert.equal(director.snapshot().current.id,'one');
});
