import test from 'node:test';
import assert from 'node:assert/strict';
import {createWorshipLibrary,compileWorshipFromLibrary} from '../src/worship-library.mjs';

const catalog={
 schema:'toc.worship-library/v1',
 songs:[{
  id:'original-song',revision:'v1',title:'Original Service Song',
  rights:{source:'original',displayAuthorized:true,streamAuthorized:false},
  notes:'PRIVATE_REHEARSAL_TEXT',
  sections:[
   {id:'v1',label:'verse 1',lines:['We gather together','We praise with gratitude'],
    notes:'PRIVATE_VERSE_NOTE',chords:['C','G']},
   {id:'ch',label:'chorus',lines:['Our voices rise together'],
    notes:'PRIVATE_CHORUS_NOTE',chords:['F','Am']}
  ],
  arrangements:[{id:'sunday',sectionIds:['v1','ch','ch']}]
 }],
 scriptures:[{
  id:'reading',revision:'v1',title:'Scripture Reading',reference:'John 3:16',
  translation:'NKJV',text:'COPYRIGHT_TEST_TEXT_WITHOUT_PERMISSION',
  scriptureRights:{source:'unknown',displayAuthorized:false,streamAuthorized:false},
  notes:'PRIVATE_PASTOR_NOTE'
 }],
 segments:[{
  id:'welcome',revision:'v1',type:'announcement',title:'Welcome',
  text:'Welcome to worship',notes:'PRIVATE_OPERATOR_CUE',
  publicAuthorized:true,streamAuthorized:true
 }]
};
function make(){
 const library=createWorshipLibrary(catalog);
 const byId=id=>library.listEntries().find(x=>x.id===id);
 const refs=[
  {id:'welcome',sourceType:'segment',sourceId:'welcome'},
  {id:'song',sourceType:'song',sourceId:'original-song',arrangementId:'sunday'},
  {id:'reading',sourceType:'scripture',sourceId:'reading'}
 ].map(item=>({...item,revision:byId(item.sourceId).revision,sha256:byId(item.sourceId).sha256}));
 return {library,plan:{title:'Worship Service',theme:'dark',items:refs}};
}
const priv=['PRIVATE_REHEARSAL_TEXT','PRIVATE_VERSE_NOTE','PRIVATE_CHORUS_NOTE','PRIVATE_PASTOR_NOTE','PRIVATE_OPERATOR_CUE','COPYRIGHT_TEST_TEXT_WITHOUT_PERMISSION'];
test('existing immutable offline worship catalog exposes only bounded metadata and stable hashes',()=>{
 const {library}=make();
 assert.equal(library.schema,'toc.worship-library/v1');
 assert.match(library.sha256,/^[a-f0-9]{64}$/);
 assert.equal(library.listEntries().length,3);
 const visible=JSON.stringify(library);
 for(const value of priv)assert.equal(visible.includes(value),false);
 const copy=createWorshipLibrary(structuredClone(catalog));
 assert.equal(library.sha256,copy.sha256);
});
test('existing library compiles repeatable arrangements using one original chorus source',()=>{
 const {library,plan}=make();
 const built=compileWorshipFromLibrary(plan,library,{stageGrant:'owner-stage-grant'});
 const choruses=built.publicDeck.slides.filter(s=>s.section==='chorus');
 assert.deepEqual(choruses.map(s=>s.occurrence),[1,2]);
 assert.notEqual(choruses[0].id,choruses[1].id);
 assert.equal(choruses[0].text,choruses[1].text);
 assert.equal(built.publicDeck.slides.find(s=>s.id==='reading').text,'');
 assert.equal(built.broadcastDeck.slides.filter(s=>s.song==='Original Service Song').every(s=>s.text===''),true);
 assert.equal(built.getCueSource(1,'wrong'),null);
 assert.equal(built.getCueSource(1,'owner-stage-grant').assetId,'original-song');
 assert.equal(built.getCueSource(1,'owner-stage-grant').sectionId,'v1');
 assert.match(built.getStageCue(1,'owner-stage-grant').notes,/PRIVATE_VERSE_NOTE/);
 for(const value of priv)assert.equal(JSON.stringify(built).includes(value),false);
});
test('revision or integrity digest mismatch rejects catalog substitution',()=>{
 const {library,plan}=make();
 const wrong=structuredClone(plan);
 wrong.items[1].sha256='f'.repeat(64);
 assert.throws(()=>compileWorshipFromLibrary(wrong,library),/integrity|sha/i);
 wrong.items[1].sha256=plan.items[1].sha256;
 wrong.items[1].revision='v2';
 assert.throws(()=>compileWorshipFromLibrary(wrong,library),/revision|stale/i);
});
test('song arrangement cannot be silently changed to an unknown group',()=>{
 const {library,plan}=make();
 const wrong=structuredClone(plan);
 wrong.items[1].arrangementId='unapproved-group';
 assert.throws(()=>compileWorshipFromLibrary(wrong,library),/arrangement/i);
});
test('unknown catalog source cannot become public content',()=>{
 const {library,plan}=make();
 const wrong=structuredClone(plan);
 wrong.items[0].sourceId='nonexistent';
 assert.throws(()=>compileWorshipFromLibrary(wrong,library),/unknown catalog/i);
});
test('source mutations cannot change an already validated library',()=>{
 const edited=structuredClone(catalog);
 const library=createWorshipLibrary(edited);
 const before=library.sha256;
 edited.songs[0].sections[0].lines[0]='REPLACEMENT NOT AUTHORIZED';
 assert.equal(library.sha256,before);
 assert.equal(library.listEntries()[0].sha256,createWorshipLibrary(catalog).listEntries()[0].sha256);
});
test('catalog rejects unknown rights that claim public display authorization',()=>{
 const x=structuredClone(catalog);
 x.songs[0].rights={source:'unknown',displayAuthorized:true,streamAuthorized:false};
 assert.throws(()=>createWorshipLibrary(x),/rights/i);
});
test('duplicate content identifiers and invalid scripture translations fail validation',()=>{
 const duplicate=structuredClone(catalog);
 duplicate.segments[0].id='reading';
 assert.throws(()=>createWorshipLibrary(duplicate),/duplicate/i);
 const wrong=structuredClone(catalog);
 wrong.scriptures[0].translation='ASV';
 assert.throws(()=>createWorshipLibrary(wrong),/NKJV/i);
});
test('unauthorized service references may not inject display text or private notes',()=>{
 const {library,plan}=make();
 const injected=structuredClone(plan);
 injected.items[0].notes='SEND PRIVATE NOTES PUBLIC';
 assert.throws(()=>compileWorshipFromLibrary(injected,library),/override|unexpected/i);
});
