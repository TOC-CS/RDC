import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,stat,readFile,symlink,rm} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {WorshipLibraryStore,buildServiceFromWorshipLibrary} from '../src/worship-library.mjs';

const fixture={
 schema:'toc.worship.song-library/v1',
 songs:[{id:'song-example',title:'Original demonstration',rights:{
  source:'original',displayAuthorized:true,streamAuthorized:false
 },sections:[
  {label:'verse 1',lines:['Original verse'],notes:'PRIVATE_ONE',chords:['C']},
  {label:'chorus',lines:['Original chorus'],notes:'PRIVATE_CHORUS'}
 ],defaultOrder:['verse 1','chorus','chorus']}]
};
const plan={title:'Offline example',items:[
 {id:'opening',type:'song',songId:'song-example'},
 {id:'reading',type:'scripture',title:'Reading',reference:'John 3:16',translation:'NKJV'}
]};
test('earlier song library schema maps into the same source-locked engine without a parallel director',()=>{
 const compiled=buildServiceFromWorshipLibrary(fixture,plan,{stageGrant:'private'});
 const choruses=compiled.publicDeck.slides.filter(x=>x.section==='chorus');
 assert.deepEqual(choruses.map(x=>x.occurrence),[1,2]);
 assert.equal(compiled.broadcastDeck.slides.filter(x=>x.kind==='song').every(x=>x.text===''),true);
 assert.equal(compiled.publicDeck.slides.find(x=>x.id==='reading').text,'');
 assert.match(compiled.getStageCue(0,'private').notes,/PRIVATE_ONE/);
 assert.equal(JSON.stringify(compiled).includes('PRIVATE_CHORUS'),false);
});
test('legacy unknown song IDs are rejected rather than invented',()=>{
 const changed=structuredClone(plan);changed.items[0].songId='absent-song';
 assert.throws(()=>buildServiceFromWorshipLibrary(fixture,changed),/unknown song/i);
});
test('legacy local song library store is owner-only and refuses symlink directory',async()=>{
 const root=await mkdtemp(join(tmpdir(),'toc-private-legacy-library-'));
 const dir=join(root,'owner');
 try{
  const store=new WorshipLibraryStore({root:dir});
  await store.save(fixture);
  assert.equal((await stat(dir)).mode&0o077,0);
  assert.equal((await stat(join(dir,'songs.json'))).mode&0o077,0);
  const loaded=await store.load();
  assert.equal(loaded.songs[0].title,fixture.songs[0].title);
  assert.match(await readFile(join(dir,'songs.json'),'utf8'),/PRIVATE_ONE/);
  await symlink(dir,join(root,'shortcut'),'dir');
  await assert.rejects(()=>new WorshipLibraryStore({root:join(root,'shortcut')}).load(),/symlink|directory/i);
 }finally{await rm(root,{recursive:true,force:true});}
});
