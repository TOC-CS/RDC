import test from 'node:test';
import assert from 'node:assert/strict';
import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {readFile,writeFile,mkdtemp,rm} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath} from 'node:url';

const exec=promisify(execFile);
const server=fileURLToPath(new URL('../scripts/managed-server.mjs',import.meta.url));
const cli=fileURLToPath(new URL('../scripts/presentationctl.mjs',import.meta.url));
const plan={title:'RDC Operator Looks',items:[
 {id:'welcome',type:'announcement',title:'Welcome',text:'Welcome to worship',notes:'PRIVATE_STAGED_NOTES'}
]};
async function isolated(authorized,task){
 const dir=await mkdtemp(join(tmpdir(),'toc-rdc-look-cli-'));
 const env={...process.env,PRESENTATION_AGENT_STATE_DIR:dir,
   PRESENTATION_ALLOW_WORSHIP_LOOK_EDIT:authorized?'1':'0'};
 const planFile=join(dir,'service.json');
 const look=join(dir,'look.json');
 const curtain=join(dir,'visibility.json');
 const invalid=join(dir,'invalid.json');
 await writeFile(planFile,JSON.stringify(plan),{mode:0o600});
 await writeFile(look,JSON.stringify({
   destination:'broadcast',look:{layout:'minimal',background:'transparent',layers:['text']}
 }),{mode:0o600});
 await writeFile(curtain,JSON.stringify({
   destination:'audience',mode:'blank'
 }),{mode:0o600});
 await writeFile(invalid,JSON.stringify({
   destination:'stage',mode:'clear',password:'PRIVATE_DONT_LOG'
 }),{mode:0o600});
 const child=spawn(process.execPath,[server],{env,stdio:['ignore','ignore','pipe']});
 try{
   let ready=false;
   for(let i=0;i<90;i++){
     try{await readFile(join(dir,'control.json'));ready=true;break;}
     catch{await new Promise(resolve=>setTimeout(resolve,25));}
   }
   assert.equal(ready,true);
   const run=async(...args)=>{
     const {stdout}=await exec(process.execPath,[cli,...args],{env,timeout:2500});
     assert.equal(stdout.includes('PRIVATE_DONT_LOG'),false);
     return JSON.parse(stdout);
   };
   await run('worship-load','--file',planFile);
   await task({run,look,curtain,invalid,env});
 }finally{
   child.kill('SIGTERM');
   await Promise.race([new Promise(resolve=>child.once('close',resolve)),
     new Promise(resolve=>setTimeout(resolve,1200))]);
   await rm(dir,{recursive:true,force:true});
 }
}
test('RDC CLI owner grant can change a broadcast Look and blank only local audience HTML without moving the service cue',
 {timeout:12000},()=>isolated(true,async({run,look,curtain,invalid})=>{
 const before=await run('status');
 const changed=await run('look-set','--file',look);
 assert.equal(changed.destinations.find(x=>x.destination==='broadcast').layout,'minimal');
 const blackout=await run('visibility-set','--file',curtain);
 assert.equal(blackout.outputs.find(x=>x.destination==='audience').mode,'blank');
 assert.equal(blackout.streamOrRecordChanged,false);
 const rundown=await run('rundown');
 assert.equal(rundown.looks.find(x=>x.destination==='broadcast').layout,'minimal');
 assert.equal(rundown.visibility.find(x=>x.destination==='audience').mode,'blank');
 assert.equal(JSON.stringify(rundown).includes('PRIVATE_STAGED_NOTES'),false);
 assert.deepEqual(await run('status'),before);
 await assert.rejects(()=>run('visibility-set','--file',invalid),/Unknown|unsupported|field|Only/i);
}));
test('RDC CLI cannot bypass locally disabled operator controls, even with a valid private managed-session credential',
 {timeout:12000},()=>isolated(false,async({run,look,curtain})=>{
 await assert.rejects(()=>run('look-set','--file',look),/operator|grant/i);
 await assert.rejects(()=>run('visibility-set','--file',curtain),/operator|grant/i);
 const rundown=await run('rundown');
 assert.equal(rundown.looks.find(x=>x.destination==='broadcast').layout,'lower-third');
 assert.equal(rundown.visibility.find(x=>x.destination==='audience').mode,'visible');
}));
