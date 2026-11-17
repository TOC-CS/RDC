import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {compileWorshipService} from '../src/worship-service.mjs';
import {compileWorshipLook,validateWorshipLook} from '../src/worship-looks.mjs';

const plan=JSON.parse(await readFile(fileURLToPath(new URL(
 '../skills/ai-presentation-agent/worship/examples/sunday-service.json',import.meta.url)),'utf8'));
plan.items[0].notes='SECRET_STAGE_OPERATOR_TEXT';
plan.items[2].sections[0].notes='SECRET_STAGE_WORSHIP_NOTES';
plan.items[2].sections[0].chords=['A','F#m'];
plan.items[2].rights.streamAuthorized=false;
const session=compileWorshipService(plan,{stageGrant:'secret-stage-one'});
const lyricIndex=session.publicDeck.slides.findIndex(s=>s.section==='verse 1');
assert.ok(lyricIndex>0);

test('congregation look produces only source-verified public content',()=>{
 const output=compileWorshipLook(session,{
   destination:'audience',index:lyricIndex,
   look:{layout:'fullscreen',background:'dark',layers:['title','text','reference']}
 });
 assert.equal(output.destination,'audience');
 assert.equal(output.layout,'fullscreen');
 assert.equal(output.current.text,session.publicDeck.slides[lyricIndex].text);
 assert.equal(output.layers.title,session.publicDeck.slides[lyricIndex].title);
 assert.equal(output.layers.text,session.publicDeck.slides[lyricIndex].text);
 assert.equal(JSON.stringify(output).includes('SECRET_'),false);
 assert.equal(JSON.stringify(output).includes('F#m'),false);
});
test('stream look uses separately authorized broadcast rights and remains public-safe',()=>{
 const output=compileWorshipLook(session,{
   destination:'broadcast',index:lyricIndex,
   look:{layout:'lower-third',background:'transparent',layers:['text','reference']}
 });
 assert.equal(output.destination,'broadcast');
 assert.equal(output.background,'transparent');
 assert.equal(output.layers.text,'','Room-only lyrics must remain absent from stream');
 assert.equal(JSON.stringify(output).includes('SECRET_'),false);
 assert.equal(JSON.stringify(output).includes('F#m'),false);
});
test('private stage look requires stage grant and may show chords, current and next lyric',()=>{
 assert.throws(()=>compileWorshipLook(session,{
   destination:'stage',index:lyricIndex,look:{layout:'confidence',layers:['notes','chords']}
 }),/stage|authorization/i);
 const output=compileWorshipLook(session,{
   destination:'stage',index:lyricIndex,stageGrant:'secret-stage-one',
   look:{layout:'confidence',background:'dark',layers:['text','next','notes','chords']}
 });
 assert.match(output.layers.notes,/SECRET_STAGE_WORSHIP_NOTES/);
 assert.deepEqual(output.layers.chords,['A','F#m']);
 assert.ok(typeof output.layers.next==='string');
 assert.equal(output.destination,'stage');
});
test('public output cannot request private notes, chords, next cue or operator fields',()=>{
 for(const destination of ['audience','broadcast']){
   for(const layer of ['notes','chords','next','operator','timer']){
     assert.throws(()=>compileWorshipLook(session,{
       destination,index:lyricIndex,stageGrant:'secret-stage-one',
       look:{layout:'fullscreen',layers:[layer]}
     }),/not allowed|private|layer|destination/i);
   }
 }
});
test('public look rejects caller-supplied arbitrary fields and private-looking payload overrides',()=>{
 for(const look of [
   {layout:'fullscreen',layers:['title'],notes:'SECRET'},
   {layout:'fullscreen',layers:['title'],text:'SECRET'},
   {layout:'fullscreen',layers:['title'],background:'#unsafe'},
   {layout:'confidence',layers:['title']},
   {layout:'fullscreen',layers:['title','title']},
   {layout:'fullscreen',layers:['stageMessage']},
 ]){
   assert.throws(()=>compileWorshipLook(session,{destination:'audience',index:0,look}),/invalid|unknown|layout|layer|duplicate|not allowed/i);
 }
});
test('independent looks are immutable detached packets and never change source state',()=>{
 const output=compileWorshipLook(session,{destination:'broadcast',index:0,
    look:{layout:'lower-third',layers:['title','text']}});
 assert.equal(Object.isFrozen(output),true);
 assert.equal(Object.isFrozen(output.layers),true);
 assert.notEqual(output.current,session.broadcastDeck.slides[0]);
 assert.equal(JSON.stringify(session).includes('SECRET_'),false);
 assert.equal(JSON.stringify(output).includes('SECRET_'),false);
});
test('out of range indexes and untrusted service packages fail before any content is returned',()=>{
 for(const index of [-1,1e10,1.2])
  assert.throws(()=>compileWorshipLook(session,{destination:'audience',index}),/index|range/i);
 assert.throws(()=>validateWorshipLook('audience',{layout:'x'}),/layout/i);
 assert.throws(()=>compileWorshipLook({publicDeck:{slides:[{id:'x',notes:'SECRET'}]}},{
   destination:'audience',index:0}),/validated|compiled|session/i);
});
test('existing content-addressed worship library compiles into the same privacy-partitioned Looks',async()=>{
 const {createWorshipLibrary,compileWorshipFromLibrary}=await import('../src/worship-library.mjs');
 const base=new URL('../examples/',import.meta.url);
 const source=JSON.parse(await readFile(fileURLToPath(new URL('toc-offline-worship-library.json',base)),'utf8'));
 const order=JSON.parse(await readFile(fileURLToPath(new URL('toc-offline-worship-plan.json',base)),'utf8'));
 const service=compileWorshipFromLibrary(order,createWorshipLibrary(source),{stageGrant:'stage-only'});
 const index=service.publicDeck.slides.findIndex(s=>s.kind==='song');
 assert.ok(index>=0);
 const audience=compileWorshipLook(service,{destination:'audience',index});
 const broadcast=compileWorshipLook(service,{destination:'broadcast',index});
 const stage=compileWorshipLook(service,{destination:'stage',index,stageGrant:'stage-only'});
 assert.equal(audience.current.id,broadcast.current.id);
 assert.equal(stage.slideId,audience.slideId);
 assert.equal(JSON.stringify(audience).includes('PRIVATE'),false);
 assert.equal(JSON.stringify(broadcast).includes('PRIVATE'),false);
});
