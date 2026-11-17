import test from 'node:test';
import assert from 'node:assert/strict';
import {WorshipLookController} from '../src/worship-look-control.mjs';

test('independent output looks begin from safe fixed defaults and use separate revisions',()=>{
 const controller=new WorshipLookController();
 const initial=controller.snapshot();
 assert.deepEqual(initial.destinations.map(x=>x.destination),['audience','stage','broadcast']);
 assert.equal(initial.destinations.find(x=>x.destination==='broadcast').background,'transparent');
 assert.equal(initial.revision,0);
 assert.equal(initial.externalActionsPerformed,false);
});
test('changing one destination does not alter another and emits only validated config',()=>{
 const events=[];
 const c=new WorshipLookController({onChange:v=>events.push(v)});
 c.set('broadcast',{layout:'minimal',background:'transparent',layers:['text']});
 const all=c.snapshot();
 assert.equal(all.revision,1);
 assert.equal(events.length,1);
 assert.deepEqual(c.get('broadcast').layers,['text']);
 assert.equal(c.get('stage').layers.includes('notes'),true);
 assert.equal(c.get('audience').layout,'fullscreen');
 assert.equal(JSON.stringify(all).includes('PRIVATE'),false);
 assert.equal(all.externalActionsPerformed,false);
});
test('a rejected Look cannot leak custom text, stage notes or change any state',()=>{
 const c=new WorshipLookController();
 for(const invalid of [
  {layout:'lower-third',layers:['notes']},
  {layout:'lower-third',layers:['text'],privateNotes:'SECRET'},
  {layout:'lower-third',layers:['chords']},
  {layout:'bad',layers:['title']}
 ]){
  assert.throws(()=>c.set('broadcast',invalid));
  assert.equal(c.snapshot().revision,0);
 }
});
test('look reset clears all customizations and increments the revision',()=>{
 const c=new WorshipLookController();
 c.set('broadcast',{layout:'minimal',layers:['text']});
 c.set('stage',{layout:'confidence',layers:['text']});
 assert.equal(c.snapshot().revision,2);
 const after=c.reset();
 assert.equal(after.revision,3);
 assert.equal(c.get('broadcast').layout,'lower-third');
 assert.equal(c.get('stage').layers.includes('notes'),true);
});
