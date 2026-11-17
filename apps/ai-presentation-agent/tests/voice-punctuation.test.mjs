import test from 'node:test';
import assert from 'node:assert/strict';
import {interpretVoice} from '../src/voice.mjs';

test('single explicit wake-word voice commands tolerate ASR punctuation',()=>{
 for(const speech of [
   'Presentation agent, next slide.',
   'Presentation agent: next slide',
   'Presentation agent. Next slide?',
   'Presentation agent, next slide, please.'
 ]){
   assert.deepEqual(interpretVoice(speech),{action:'next'},speech);
 }
});
test('ordinary sermon speech and multi-command ASR frames cannot execute slide control',()=>{
 for(const speech of [
   'The presentation agent, next slide',
   'Presentation agents, next slide',
   'Presentation agent, next slide is important',
   'Presentation agent, next slide. Presentation agent, previous slide',
   'Next slide',
   'Presentation agent, what does next slide mean?'
 ])assert.equal(interpretVoice(speech),null,speech);
});
test('recognized hold and status voice commands tolerate natural wording',()=>{
 assert.deepEqual(interpretVoice('Presentation agent, hold slides.'),{action:'hold'});
 assert.deepEqual(interpretVoice('Presentation agent: what slide are we on?'),{action:'status'});
 assert.deepEqual(interpretVoice('Presentation agent, resume.'),{action:'resume'});
});
