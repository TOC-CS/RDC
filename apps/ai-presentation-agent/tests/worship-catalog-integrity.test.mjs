import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {createWorshipLibrary,compileWorshipFromLibrary} from '../src/worship-library.mjs';
import {compileWorshipService} from '../src/worship-service.mjs';

const origin=new URL('../examples/toc-offline-worship-library.json',import.meta.url);
const schedule=new URL('../examples/toc-offline-worship-plan.json',import.meta.url);
const librarySource=JSON.parse(await readFile(fileURLToPath(origin),'utf8'));
const servicePlan=JSON.parse(await readFile(fileURLToPath(schedule),'utf8'));

test('two similar song slot prefixes remain provenance-separated',()=>{
 const lib=createWorshipLibrary(librarySource);
 const source=lib.listEntries().find(e=>e.id==='morning-song');
 const items=['morning','morning-s1'].map(id=>({
  id,sourceType:'song',sourceId:'morning-song',arrangementId:'short-reprise',
  revision:source.revision,sha256:source.sha256
 }));
 const compiled=compileWorshipFromLibrary({title:'Collision check',items},lib,{stageGrant:'private'});
 const idx=compiled.publicDeck.slides.findIndex(s=>s.id==='morning-s1-s1-p1');
 assert.ok(idx>0);
 assert.equal(compiled.getCueSource(idx,'private').slotId,'morning-s1');
 assert.equal(compiled.getCueSource(idx,'private').sectionId,'chorus');
 assert.equal(compiled.getCueSource(idx,'bad'),null);
});
test('original display permission never implies livestream authorization',()=>{
 const built=compileWorshipService({
  title:'Rights review',items:[{id:'original',type:'song',title:'Original song',
   rights:{source:'original',displayAuthorized:true},
   sections:[{label:'chorus',lines:['Original local lyric']}],order:['chorus']
  }]
 });
 assert.equal(built.publicDeck.slides[0].text,'Original local lyric');
 assert.equal(built.broadcastDeck.slides[0].text,'');
 assert.ok(built.issues.some(x=>x.type==='livestream_lyrics_rights'));
});
test('original TOC library example remains reference-only and separate from stage privacy',()=>{
 const lib=createWorshipLibrary(librarySource);
 const result=compileWorshipFromLibrary(servicePlan,lib,{stageGrant:'private-only'});
 assert.equal(result.publicDeck.slides.length,14);
 assert.equal(result.broadcastDeck.slides.length,14);
 assert.equal(result.publicDeck.slides.find(x=>x.id==='reading').text,'');
 assert.ok(result.issues.some(x=>x.type==='scripture_reference_only'));
 const choruses=result.publicDeck.slides.filter(x=>x.song==='Morning Song of Gratitude'&&x.section==='chorus'&&x.id.startsWith('opening-worship'));
 assert.deepEqual(choruses.map(x=>x.occurrence),[1,2,3]);
 const publicJson=JSON.stringify(result);
 assert.equal(publicJson.includes('PRIVATE REHEARSAL'),false);
 assert.equal(result.getStageCue(0,'bad'),null);
 assert.ok(result.getStageCue(0,'private-only').notes.includes('PRIVATE'));
});
