import test from 'node:test';
import assert from 'node:assert/strict';
import {prepareWorshipMacro} from '../src/worship-macro-plan.mjs';

const base=[
 {action:'hold'},
 {action:'show-slide',slideId:'sermon'},
 {action:'clear-broadcast-graphics'},
 {action:'set-obs-preview',scene:'Pastor Camera'},
 {action:'set-obs-program',scene:'Sermon Camera'},
 {action:'stage-message',text:'PRIVATE_UNANNOUNCED_PASTOR_MESSAGE'},
 {action:'start-stream'}
];
const deck={slides:[{id:'worship'},{id:'sermon'}]};

test('professional service transition compiles to a safe unexecuted operator plan',()=>{
 const plan=prepareWorshipMacro({name:'Worship to Sermon',steps:base},{deck});
 assert.equal(plan.schema,'toc.worship.macro-preview/v1');
 assert.equal(plan.executionAllowed,false);
 assert.equal(plan.applied,false);
 assert.equal(plan.steps.length,base.length);
 assert.ok(plan.requiredGrants.includes('obs.program'));
 assert.ok(plan.requiredGrants.includes('obs.start-stream'));
 assert.ok(plan.steps.every(s=>s.previewOnly===true));
 assert.ok(plan.steps.some(s=>s.action==='set-obs-preview'&&s.target==='obs-preview'));
 assert.ok(plan.steps.some(s=>s.action==='set-obs-program'&&s.target==='obs-program'));
 assert.ok(plan.steps.some(s=>s.action==='start-stream'&&s.critical===true));
});
test('private stage message is never included in publicly serializable macro preview',()=>{
 const plan=prepareWorshipMacro({name:'Quiet Stage Notice',steps:[
   {action:'stage-message',text:'PRIVATE_UNANNOUNCED_PASTOR_MESSAGE'}
 ]},{deck});
 assert.equal(JSON.stringify(plan).includes('PRIVATE_UNANNOUNCED_PASTOR_MESSAGE'),false);
 assert.equal(JSON.stringify(plan).includes('text'),false);
 assert.equal(plan.steps[0].privatePayloadRequired,true);
 assert.equal(plan.steps[0].target,'stage-private');
});
test('service title and Scripture cue remain reference-only without an authorized Bible data source',()=>{
 const plan=prepareWorshipMacro({name:'Scripture',steps:[
  {action:'show-scripture-reference',reference:'John 3:16',translation:'NKJV'}
 ]},{deck});
 assert.equal(plan.steps[0].reference,'John 3:16');
 assert.equal(plan.steps[0].translation,'NKJV');
 assert.equal(plan.steps[0].authorizedVerseTextIncluded,false);
 assert.equal(JSON.stringify(plan).includes('For God so loved'),false);
});
test('broadcast stop and recording stop are different critical operator actions',()=>{
 const plan=prepareWorshipMacro({name:'End Service',steps:[
   {action:'stop-stream'},{action:'stop-record'}
 ]},{deck});
 assert.deepEqual(plan.requiredGrants,['obs.stop-stream','obs.stop-record']);
 assert.equal(plan.steps[0].target,'obs-stream');
 assert.equal(plan.steps[1].target,'obs-record');
 assert.ok(plan.steps.every(s=>s.critical&&s.operatorApprovalRequired));
});
test('unknown macro operations, arbitrary OBS requests and unsafe source payloads are refused',()=>{
 for(const step of [
   {action:'ExecuteShell',cmd:'rm -rf /'},
   {action:'start-stream',streamKey:'SENSITIVE'},
   {action:'set-obs-program',scene:'Scene',password:'secret'},
   {action:'show-slide',slideId:'unknown'},
   {action:'stage-message',scene:'PRIVATE'},
   {action:'show-scripture-reference',reference:'John 3:16',translation:'ASV'}
 ])assert.throws(()=>prepareWorshipMacro({name:'Bad',steps:[step]},{deck}),/unknown|invalid|unsupported|slide|translation/i);
});
test('macro planner never mutates service deck or requester actions',()=>{
 const steps=structuredClone(base);
 const before=JSON.stringify({steps,deck});
 const out=prepareWorshipMacro({name:'Safe',steps},{deck});
 assert.equal(JSON.stringify({steps,deck}),before);
 assert.equal(Object.isFrozen(out),true);
 assert.equal(Object.isFrozen(out.steps),true);
});
