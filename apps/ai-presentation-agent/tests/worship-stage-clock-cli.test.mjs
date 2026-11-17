import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,readFile,symlink,rm} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath} from 'node:url';
import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';
const exec=promisify(execFile);
const server=fileURLToPath(new URL('../scripts/managed-server.mjs',import.meta.url));
const cli=fileURLToPath(new URL('../scripts/presentationctl.mjs',import.meta.url));
const SECRET='PRIVATE_TIMER_CAPTION_NEVER_PUBLIC';
const plan={title:'Service',items:[
 {id:'one',type:'announcement',title:'Opening',text:'Welcome'}
]};
async function fixture(enabled,fn){
 const dir=await mkdtemp(join(tmpdir(),'toc-stage-clock-cli-'));
 const env={...process.env,PRESENTATION_AGENT_STATE_DIR:dir,
   PRESENTATION_ALLOW_STAGE_CLOCK:enabled?'1':'0'};
 const planPath=join(dir,'plan.json'),clockPath=join(dir,'clock.json');
 await writeFile(planPath,JSON.stringify(plan),{mode:0o600});
 await writeFile(clockPath,JSON.stringify({
   action:'configure',label:SECRET,durationMs:90000
 }),{mode:0o600});
 const child=spawn(process.execPath,[server],{env,stdio:['ignore','ignore','pipe']});
 try{
   let available=false;
   for(let i=0;i<100;i++){
     try{await readFile(join(dir,'control.json'));available=true;break;}
     catch{await new Promise(r=>setTimeout(r,22));}
   }
   assert.equal(available,true);
   const run=async(...args)=>{
     const {stdout}=await exec(process.execPath,[cli,...args],{env,timeout:2500});
     assert.equal(stdout.includes(SECRET),false,'Never print private timer caption.');
     return JSON.parse(stdout);
   };
   await run('worship-load','--file',planPath);
   await fn({run,env,dir,clockPath});
 }finally{
   child.kill('SIGTERM');
   await Promise.race([new Promise(resolve=>child.once('close',resolve)),
     new Promise(resolve=>setTimeout(resolve,1400))]);
   await rm(dir,{recursive:true,force:true});
 }
}
test('RDC separate CLI commands control a private stage timer but redact its label in all replies',
 {timeout:10000},()=>fixture(true,async({run,clockPath})=>{
 const configured=await run('stage-clock','--file',clockPath);
 assert.equal(configured.privateStage,true);
 assert.equal(configured.updated,true);
 assert.equal(configured.durationMs,90000);
 assert.equal(configured.automaticAdvance,false);
 await run('stage-clock-start');
 const status=await run('stage-clock-status');
 assert.equal(status.running,true);
 assert.ok(status.remainingMs<=90000);
 assert.equal(JSON.stringify(status).includes(SECRET),false);
 const publicRundown=await run('rundown');
 assert.equal(JSON.stringify(publicRundown).includes(SECRET),false);
 await run('stage-clock-pause');
 assert.equal((await run('stage-clock-status')).paused,true);
 await run('stage-clock-resume');
 assert.equal((await run('stage-clock-status')).running,true);
 await run('stage-clock-reset');
 assert.equal((await run('stage-clock-status')).running,false);
 assert.equal((await run('status')).started,false);
}));
test('stage clock commands cannot bypass the server launch grant', {timeout:10000},
 ()=>fixture(false,async({run,clockPath})=>{
   await assert.rejects(()=>run('stage-clock','--file',clockPath),/operator|grant/i);
   await assert.rejects(()=>run('stage-clock-start'),/operator|grant/i);
   assert.equal((await run('stage-clock-status')).running,false);
 }));
test('CLI refuses stage clock caption symlink and unsafe group-readable file before a remote request',
 {timeout:10000},()=>fixture(true,async({run,dir})=>{
   const readable=join(dir,'insecure.json');
   await writeFile(readable,JSON.stringify({action:'configure',label:SECRET,durationMs:30000}),{mode:0o644});
   const shortcut=join(dir,'shortcut.json');
   await symlink(readable,shortcut);
   await assert.rejects(()=>run('stage-clock','--file',readable),/private|owner|permission/i);
   await assert.rejects(()=>run('stage-clock','--file',shortcut),/symlink|private|permission/i);
   assert.equal((await run('stage-clock-status')).running,false);
 }));
