import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {compileWorshipService} from '../src/worship-service.mjs';
import {buildWorshipOperatorRundown} from '../src/worship-rundown.mjs';

const plan=JSON.parse(await readFile(fileURLToPath(new URL(
 '../skills/ai-presentation-agent/worship/examples/sunday-service.json',import.meta.url)),'utf8'));
plan.items[0].notes='PRIVATE_STAGE_PASTOR_PRAYER_CARD';
plan.items[2].sections[0].notes='PRIVATE_MUSICIAN_STANDBY';
const session=compileWorshipService(plan,{stageGrant:'private-grant-test'});

test('operator rundown summarizes authorized service order and current/next cue without private data',()=>{
 const result=buildWorshipOperatorRundown(session,{index:0,started:false,held:false,mode:'manual'});
 assert.equal(result.schema,'toc.worship.operator-rundown/v1');
 assert.equal(result.current.id,'pre-service');
 assert.equal(result.next.id,'welcome');
 assert.equal(result.items.length,plan.items.length);
 assert.equal(result.items[2].type,'song');
 assert.equal(result.items[2].title,'Light of the Morning');
 assert.equal(result.status.started,false);
 assert.equal(JSON.stringify(result).includes('PRIVATE_'),false);
 assert.equal(JSON.stringify(result).includes('chords'),false);
 assert.equal(JSON.stringify(result).includes('notes'),false);
});
test('operator follows precise repeated chorus occurrence identity without altering service cursor',()=>{
 const index=session.publicDeck.slides.findIndex(s=>s.section==='chorus'&&s.occurrence===2);
 assert.ok(index>0);
 const result=buildWorshipOperatorRundown(session,{index,started:true,held:false,mode:'automatic'});
 assert.equal(result.current.section,'chorus');
 assert.equal(result.current.occurrence,2);
 assert.equal(result.current.song,'Light of the Morning');
 assert.equal(result.index,index);
 assert.equal(result.current.id,session.publicDeck.slides[index].id);
 assert.equal(session.publicDeck.slides[index].position,undefined);
});
test('rundown never includes unlicensed Scripture bodies, entire lyric text, or stage grants',()=>{
 const result=buildWorshipOperatorRundown(session,{index:0});
 const raw=JSON.stringify(result);
 for(const secret of [
  'PRIVATE_STAGE_PASTOR_PRAYER_CARD','PRIVATE_MUSICIAN_STANDBY',
  'private-grant-test','We lift our voices in the morning light'
 ])assert.equal(raw.includes(secret),false);
 assert.ok(raw.includes('Psalm 100:1-2')===false ||
   result.items.some(x=>x.type==='scripture'));
});
test('invalid cursor/mode/output status fails before generating a misleading operator rundown',()=>{
 for(const state of [{index:-1},{index:1.2},{index:20000},{index:0,mode:'unknown'}])
   assert.throws(()=>buildWorshipOperatorRundown(session,state),/index|mode|state|range/i);
 assert.throws(()=>buildWorshipOperatorRundown({publicDeck:{slides:[]}},{}),/compiled|validated|service/i);
});
test('operator status may mention an output fault but cannot imply projector or livestream verification',()=>{
 const result=buildWorshipOperatorRundown(session,{index:0,started:true,
   held:true,mode:'automatic',outputFaulted:true,
   looks:{destinations:[{destination:'audience',layout:'minimal',layers:['text']}]},
   visibility:{outputs:[{destination:'audience',mode:'blank'}]}
 });
 assert.equal(result.status.outputFaulted,true);
 assert.equal(result.nativeProjectionVerified,false);
 assert.equal(result.broadcastProviderVerified,false);
 assert.equal(result.current.id,'pre-service');
 assert.equal(result.looks.find(x=>x.destination==='audience').layout,'minimal');
 assert.equal(result.visibility.find(x=>x.destination==='audience').mode,'blank');
});
