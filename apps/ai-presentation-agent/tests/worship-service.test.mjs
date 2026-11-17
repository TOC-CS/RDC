import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {compileWorshipService} from '../src/worship-service.mjs';
import {PresentationDirector} from '../src/director.mjs';
import {MemoryAdapter} from '../src/adapters.mjs';

const sample=fileURLToPath(new URL('../skills/ai-presentation-agent/worship/examples/sunday-service.json',import.meta.url));
const service=JSON.parse(await readFile(sample,'utf8'));
test('research example compiles a reusable public service deck, independent stream cues and private stage state',()=>{
 const result=compileWorshipService(service,{stageGrant:'private-stage-only'});
 assert.ok(result.publicDeck.slides.length>=10);
 assert.equal(result.publicDeck.theme,'dark');
 assert.equal(result.publicDeck.slides[0].id,'pre-service');
 assert.equal(result.broadcastDeck.slides.length,result.publicDeck.slides.length);
 const serialized=JSON.stringify(result);
 assert.ok(!serialized.includes('PRIVATE:'));
 assert.ok(!serialized.includes('Am'));
 assert.ok(!serialized.includes('stage cue, piano intro'));
 assert.equal(result.getStageCue(0,'invalid'),null);
 assert.match(result.getStageCue(0,'private-stage-only').notes,/PRIVATE:/);
 assert.equal(result.getStageCue(0,'private-stage-only').next?.id,'welcome');
});
test('song arrangements preserve unique chorus occurrences while reusing section lyrics',()=>{
 const built=compileWorshipService(service);
 const chorus=built.publicDeck.slides.filter(s=>s.song==='Light of the Morning'&&s.section==='chorus');
 assert.equal(chorus.length,2);
 assert.deepEqual(chorus.map(s=>s.occurrence),[1,2]);
 assert.notEqual(chorus[0].id,chorus[1].id);
 assert.equal(chorus[0].text,chorus[1].text);
});
test('unlicensed lyrics fail closed to title-only rather than silently projecting them',()=>{
 const copy=structuredClone(service);
 copy.items.find(x=>x.type==='song').rights={source:'unknown',displayAuthorized:false};
 const built=compileWorshipService(copy);
 const songSlides=built.publicDeck.slides.filter(s=>s.song==='Light of the Morning');
 assert.ok(songSlides.length>0);
 assert.ok(songSlides.every(s=>!s.text));
 assert.ok(built.issues.some(x=>x.type==='lyrics_rights'));
});
test('NKJV Scripture reference-only fallback never invents Bible text',()=>{
 const built=compileWorshipService(service);
 const scripture=built.publicDeck.slides.find(s=>s.id==='first-reading');
 assert.equal(scripture.reference,'Psalm 100:1-2');
 assert.equal(scripture.text,'');
 assert.equal(scripture.title,'Scripture Reading');
 assert.ok(built.issues.some(x=>x.type==='scripture_reference_only'));
});
test('owner-supplied NKJV text without explicit display rights remains hidden',()=>{
 const copy=structuredClone(service);
 const ref=copy.items.find(x=>x.type==='scripture');
 ref.text='PRIVATE LICENSED TEST CONTENT';
 const built=compileWorshipService(copy);
 const publicCopy=JSON.stringify(built);
 assert.ok(!publicCopy.includes('PRIVATE LICENSED TEST CONTENT'));
});
test('stage-only notes, chords, and private data never enter public or livestream objects',()=>{
 const copy=structuredClone(service);
 const item=copy.items.find(x=>x.type==='song');
 item.sections[0].notes='SECRETPASTORALNOTE';
 item.sections[0].chords=['C','F','PRIVATECHORD'];
 const result=compileWorshipService(copy,{stageGrant:'grant'});
 const publicData=JSON.stringify({publicDeck:result.publicDeck,broadcastDeck:result.broadcastDeck,issues:result.issues,rundown:result.rundown});
 assert.equal(publicData.includes('SECRETPASTORALNOTE'),false);
 assert.equal(publicData.includes('PRIVATECHORD'),false);
 const stage=result.getStageCue(2,'grant');
 assert.ok(stage);
 assert.equal(stage.next?.id, result.publicDeck.slides[3].id);
 assert.equal(JSON.stringify(result).includes('SECRETPASTORALNOTE'),false);
});
test('compiled original song slides remain usable by existing PresentationDirector without replacing it',async()=>{
 const built=compileWorshipService(service);
 const director=new PresentationDirector({adapter:new MemoryAdapter(),cooldownMs:0});
 director.load(built.publicDeck);
 await director.start('automatic');
 const output=await director.ingest({source:'bandmates',type:'song.section',
   song:'Light of the Morning',section:'verse 1',occurrence:1,eventId:'start-verse'});
 assert.equal(output.changed,true);
 assert.equal(director.snapshot().current.section,'verse 1');
});
