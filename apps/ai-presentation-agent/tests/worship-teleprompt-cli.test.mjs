import test from 'node:test';
import assert from 'node:assert/strict';
import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {mkdtemp,writeFile,readFile,symlink,rm} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath} from 'node:url';
const exec=promisify(execFile);
const server=fileURLToPath(new URL('../scripts/managed-server.mjs',import.meta.url));
const cli=fileURLToPath(new URL('../scripts/presentationctl.mjs',import.meta.url));
const PRIVATE='PRIVATE_SERMON_PROMPT_FIRST\nPRIVATE_SERMON_PROMPT_SECOND';
const plan={title:'Private teleprompt test service',items:[
 {id:'sermon',type:'sermon',title:'Original sermon',text:'This is visible to the room',
  notes:PRIVATE}
]};
async function fixture(grant,fn){
 const dir=await mkdtemp(join(tmpdir(),'toc-stage-teleprompt-cli-'));
 const env={...process.env,PRESENTATION_AGENT_STATE_DIR:dir,
  PRESENTATION_ALLOW_TELEPROMPT:grant?'1':'0'};
 const planPath=join(dir,'service.json');
 const configPath=join(dir,'prompt-config.json');
 await writeFile(planPath,JSON.stringify(plan),{mode:0o600});
 await writeFile(configPath,JSON.stringify({
  action:'configure',role:'speaker',fontScale:1.5,scrollSpeed:1.2,mirrored:true
 }),{mode:0o600});
 const child=spawn(process.execPath,[server],{env,stdio:['ignore','ignore','pipe']});
 const run=async(...argv)=>{
  const result=await exec(process.execPath,[cli,...argv],{env,timeout:2600});
  assert.equal(result.stdout.includes(PRIVATE),false,'Private prompt must not print to terminal');
  assert.equal(result.stdout.includes('PRIVATE_SERMON_PROMPT_FIRST'),false);
  return JSON.parse(result.stdout);
 };
 try{
  let ready=false;
  for(let i=0;i<120;i++){
   try{await readFile(join(dir,'control.json'));ready=true;break;}
   catch{await new Promise(r=>setTimeout(r,25));}
  }
  assert.equal(ready,true);
  await run('worship-load','--file',planPath);
  await fn({run,dir,planPath,configPath});
 }finally{
  child.kill('SIGTERM');
  await Promise.race([new Promise(resolve=>child.once('close',resolve)),
    new Promise(resolve=>setTimeout(resolve,1500))]);
  await rm(dir,{recursive:true,force:true});
 }
}
test('RDC CLI reads and adjusts private teleprompt without revealing notes or changing presentation slides',
 {timeout:15000},()=>fixture(true,async({run,configPath})=>{
 const original=await run('status');
 const initial=await run('teleprompt-status');
 assert.equal(initial.privateStage,true);
 assert.equal(initial.role,'speaker');
 assert.equal(initial.position,0);
 const configured=await run('teleprompt','--file',configPath);
 assert.equal(configured.role,'speaker');
 assert.equal(configured.mirrored,true);
 assert.equal(configured.fontScale,1.5);
 assert.equal(configured.privateStage,true);
 assert.equal((await run('teleprompt-next')).position,1);
 assert.equal((await run('teleprompt-hold')).held,true);
 assert.equal((await run('teleprompt-resume')).held,false);
 assert.equal((await run('teleprompt-previous')).position,0);
 assert.deepEqual(await run('status'),original);
}));
test('separate teleprompt startup authorization and owner-only input files cannot be bypassed',
 {timeout:15000},()=>fixture(false,async({run,dir,configPath})=>{
 await assert.rejects(()=>run('teleprompt','--file',configPath),/grant|operator/i);
 await assert.rejects(()=>run('teleprompt-next'),/grant|operator/i);
 const unsafe=join(dir,'public-prompt.json');
 await writeFile(unsafe,JSON.stringify({action:'follow',text:'PRIVATE_UNSAFE',
  final:true,confidence:1,eventId:'input-1',timestamp:Date.now()}),{mode:0o644});
 await assert.rejects(()=>run('teleprompt','--file',unsafe),/owner|private|permission/i);
 const shortcut=join(dir,'shortcut.json');
 await symlink(configPath,shortcut);
 await assert.rejects(()=>run('teleprompt','--file',shortcut),/symlink|private|owner/i);
}));
