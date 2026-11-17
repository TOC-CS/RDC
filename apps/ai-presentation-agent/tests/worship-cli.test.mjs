import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,stat,lstat,symlink,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {createWorshipLibrary} from '../src/worship-library.mjs';

const run=promisify(execFile);
const script=fileURLToPath(new URL('../scripts/compile-worship-service.mjs',import.meta.url));
const catalog={
 schema:'toc.worship-library/v1',
 songs:[{id:'original-song',revision:'r1',title:'Original Music',
  rights:{source:'original',displayAuthorized:true,streamAuthorized:false},
  sections:[{id:'chorus',label:'chorus',lines:['Original worship lyric'],
   notes:'PRIVATE CHORD CHART',chords:['Am']}],
  arrangements:[{id:'service',sectionIds:['chorus','chorus']}]}],
 scriptures:[{id:'psalm',revision:'r1',reference:'Psalm 100:1-2',
  translation:'NKJV',text:'UNLICENSED NKJV BODY FROM TEST',
  scriptureRights:{source:'unknown',displayAuthorized:false,streamAuthorized:false}}],
 segments:[{id:'welcome',revision:'r1',type:'announcement',title:'Welcome',
  text:'Welcome to worship',notes:'PRIVATE PASTOR NOTE',
  publicAuthorized:true,streamAuthorized:false}]
};
async function fixture(){
 const home=await mkdtemp(join(tmpdir(),'toc-worship-compiler-'));
 const lib=createWorshipLibrary(catalog);
 const lookup=id=>lib.listEntries().find(e=>e.id===id);
 const plan={title:'Sunday worship',items:[
  {id:'welcome',sourceType:'segment',sourceId:'welcome',
   revision:lookup('welcome').revision,sha256:lookup('welcome').sha256},
  {id:'song',sourceType:'song',sourceId:'original-song',
   arrangementId:'service',revision:lookup('original-song').revision,sha256:lookup('original-song').sha256},
  {id:'reading',sourceType:'scripture',sourceId:'psalm',
   revision:lookup('psalm').revision,sha256:lookup('psalm').sha256}
 ]};
 const files={home,library:join(home,'library.json'),plan:join(home,'plan.json'),
  out:join(home,'owner-only-build')};
 await writeFile(files.library,JSON.stringify(catalog),{mode:0o600});
 await writeFile(files.plan,JSON.stringify(plan),{mode:0o600});
 return files;
}
test('offline CLI writes separate audience/broadcast JSON without stage notes or unlicensed text',async()=>{
 const f=await fixture();
 try{
  const {stdout}=await run(process.execPath,[script,'--library',f.library,'--plan',f.plan,
    '--output-dir',f.out],{timeout:4500});
  const receipt=JSON.parse(stdout);
  assert.equal(receipt.schema,'toc.worship-cli-receipt/v1');
  assert.equal(receipt.project,'TOC');
  assert.equal(receipt.compiled,true);
  assert.equal(receipt.hardwareActivated,false);
  const a=JSON.parse(await readFile(join(f.out,'audience.json'),'utf8'));
  const b=JSON.parse(await readFile(join(f.out,'broadcast.json'),'utf8'));
  const issues=JSON.parse(await readFile(join(f.out,'issues.json'),'utf8'));
  assert.equal(a.slides.length,b.slides.length);
  assert.ok(a.slides.some(x=>x.text==='Original worship lyric'));
  assert.ok(b.slides.filter(x=>x.song==='Original Music').every(x=>x.text===''));
  assert.equal(a.slides.find(x=>x.id==='reading').text,'');
  assert.ok(issues.some(x=>x.type==='scripture_reference_only'));
  for(const n of ['audience.json','broadcast.json','issues.json']){
   assert.equal((await stat(join(f.out,n))).mode&0o077,0,n+' should be owner-only.');
  }
  assert.equal((await stat(f.out)).mode&0o077,0);
  const disk=await Promise.all(['audience.json','broadcast.json','issues.json'].map(x=>readFile(join(f.out,x),'utf8')));
  for(const content of disk){
   assert.ok(!content.includes('PRIVATE CHORD CHART'));
   assert.ok(!content.includes('PRIVATE PASTOR NOTE'));
   assert.ok(!content.includes('UNLICENSED NKJV BODY FROM TEST'));
   assert.ok(!content.includes('Am'));
  }
 }finally{await rm(f.home,{recursive:true,force:true});}
});
test('offline CLI refuses overwrites and never changes a previously successful service export',async()=>{
 const f=await fixture();
 try{
  const args=[script,'--library',f.library,'--plan',f.plan,'--output-dir',f.out];
  await run(process.execPath,args,{timeout:4500});
  const before=await readFile(join(f.out,'audience.json'),'utf8');
  await assert.rejects(run(process.execPath,args,{timeout:4500}),/already exists|overwrit|EEXIST/i);
  assert.equal(await readFile(join(f.out,'audience.json'),'utf8'),before);
 }finally{await rm(f.home,{recursive:true,force:true});}
});
test('offline CLI rejects symlink output directory and accidental source-relative writes',async()=>{
 const f=await fixture();
 try{
  const other=join(f.home,'elsewhere');
  await mkdir(other,{mode:0o700});
  await symlink(other,f.out,'dir');
  await assert.rejects(run(process.execPath,[script,'--library',f.library,
   '--plan',f.plan,'--output-dir',f.out],{timeout:4500}),/symlink|directory|symbolic/i);
  await assert.rejects(run(process.execPath,[script,'--library',f.library,
   '--plan',f.plan,'--output-dir','relative-output'],{timeout:4500}),/absolute|output/i);
 }finally{await rm(f.home,{recursive:true,force:true});}
});
