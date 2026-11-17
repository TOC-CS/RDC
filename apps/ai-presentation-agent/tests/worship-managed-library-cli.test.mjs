import test from 'node:test';
import assert from 'node:assert/strict';
import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {mkdtemp,writeFile,readFile,symlink,rm} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath} from 'node:url';
import {createWorshipLibrary} from '../src/worship-library.mjs';

const exec=promisify(execFile);
const server=fileURLToPath(new URL('../scripts/managed-server.mjs',import.meta.url));
const cli=fileURLToPath(new URL('../scripts/presentationctl.mjs',import.meta.url));
const PRIVATE='PRIVATE_VOCALIST_NOTES_MUST_STAY_IN_STAGE';
const ROOM_ONLY='Original lyric, authorized for room but denied on stream';
function bundle(){
 const catalog={schema:'toc.worship-library/v1',songs:[{
  id:'chorus-song',revision:'r1',title:'Original Song',
  rights:{source:'original',displayAuthorized:true,streamAuthorized:false},
  sections:[{id:'chorus',label:'Chorus',lines:[ROOM_ONLY],
   notes:PRIVATE,chords:['G','D']}],
  arrangements:[{id:'sunday',sectionIds:['chorus','chorus']}]
 }],segments:[{
  id:'welcome',revision:'r1',type:'announcement',title:'Welcome',
  text:'Welcome to worship',publicAuthorized:true,streamAuthorized:true,
  notes:PRIVATE
 }]};
 const map=new Map(createWorshipLibrary(catalog).listEntries().map(x=>[x.id,x]));
 const ref=(id,sourceId,sourceType,arrangementId)=>({
  id,sourceId,sourceType,revision:map.get(sourceId).revision,
  sha256:map.get(sourceId).sha256,...(arrangementId?{arrangementId}:{})
 });
 return {catalog,plan:{title:'Original Sunday Service',items:[
  ref('welcome-slot','welcome','segment'),
  ref('song-slot','chorus-song','song','sunday')
 ]}};
}
async function fixture(run){
 const dir=await mkdtemp(join(tmpdir(),'toc-worship-library-managed-cli-'));
 const privateFile=join(dir,'catalog-bundle.json');
 const payload=bundle();
 await writeFile(privateFile,JSON.stringify(payload),{mode:0o600});
 const env={...process.env,PRESENTATION_AGENT_STATE_DIR:dir};
 const processInstance=spawn(process.execPath,[server],{env,stdio:['ignore','ignore','pipe']});
 const command=async(...args)=>{
  const {stdout}=await exec(process.execPath,[cli,...args],{env,timeout:2600});
  assert.equal(stdout.includes(PRIVATE),false,'CLI must not print private stage notes');
  return JSON.parse(stdout);
 };
 try{
  let ready=false;
  for(let i=0;i<120;i++){
   try{await readFile(join(dir,'control.json'));ready=true;break;}
   catch{await new Promise(resolve=>setTimeout(resolve,25));}
  }
  assert.equal(ready,true,'Isolated managed server did not start');
  await run({dir,privateFile,payload,command});
 }finally{
  processInstance.kill('SIGTERM');
  await Promise.race([new Promise(resolve=>processInstance.once('close',resolve)),
    new Promise(resolve=>setTimeout(resolve,1500))]);
  await rm(dir,{recursive:true,force:true});
 }
}

test('RDC loads a private offline worship catalog into one managed cue session and persists only public crash state',
 {timeout:12000},()=>fixture(async({dir,privateFile,command})=>{
 const loaded=await command('worship-library-load','--file',privateFile);
 assert.equal(loaded.title,'Original Sunday Service');
 assert.equal(loaded.armed,false);
 assert.equal(loaded.started,false);
 assert.equal(loaded.slides.length,3);
 assert.equal(loaded.worship.stageAvailable,true);
 assert.equal((await command('stage-check')).available,true);
 assert.equal((await command('stream-check')).available,true);
 const checkpoint=JSON.parse(await readFile(join(dir,'last-known.json'),'utf8'));
 assert.equal(checkpoint.deck.slides.length,3);
 assert.equal(JSON.stringify(checkpoint).includes(PRIVATE),false);
 assert.equal(JSON.stringify(checkpoint).includes('stageToken'),false);
 assert.equal(JSON.stringify(checkpoint).includes('streamToken'),false);
 const starting=await command('rundown');
 assert.equal(starting.current.id,'welcome-slot');
 await command('start','manual');
 await command('next');
 assert.equal((await command('rundown')).current.occurrence,1);
 await command('next');
 assert.equal((await command('rundown')).current.occurrence,2);
 const current=await command('status');
 assert.equal(current.started,true);
 assert.equal(current.armed,false);
 await command('stop');
 await command('unload');
 assert.equal((await command('status')).slides.length,0);
}));

test('owner-only worship catalog CLI refuses group-readable and symlink files without changing existing state',
 {timeout:12000},()=>fixture(async({dir,privateFile,payload,command})=>{
 const before=await command('status');
 const readable=join(dir,'world-readable.json');
 await writeFile(readable,JSON.stringify(payload),{mode:0o644});
 const shortcut=join(dir,'catalog-link.json');
 await symlink(privateFile,shortcut);
 await assert.rejects(()=>command('worship-library-load','--file',readable),
  /private|owner|permission/i);
 await assert.rejects(()=>command('worship-library-load','--file',shortcut),
  /private|symlink|regular/i);
 assert.deepEqual(await command('status'),before);
 const corrupt=join(dir,'corrupt-private.json');
 const changed=structuredClone(payload);
 changed.plan.items[1].sha256='a'.repeat(64);
 await writeFile(corrupt,JSON.stringify(changed),{mode:0o600});
 await assert.rejects(()=>command('worship-library-load','--file',corrupt),
  /checksum|integrity|SHA/i);
 assert.deepEqual(await command('status'),before);
}));
