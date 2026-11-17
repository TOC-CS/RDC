import test from 'node:test';
import assert from 'node:assert/strict';
import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {mkdtemp,writeFile,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';

const exec=promisify(execFile);
const root=new URL('..',import.meta.url);
const server=fileURLToPath(new URL('../scripts/managed-server.mjs',import.meta.url));
const cli=fileURLToPath(new URL('../scripts/presentationctl.mjs',import.meta.url));
test('RDC CLI macro-preview reads an isolated managed session and never executes an OBS/stream action',
 {timeout:9000},async()=>{
 const home=await mkdtemp(join(tmpdir(),'toc-macro-preview-test-'));
 const state=join(home,'control.json'),deck=join(home,'deck.json'),macro=join(home,'macro.json');
 const env={...process.env,PRESENTATION_AGENT_STATE_DIR:home};
 await writeFile(deck,JSON.stringify({slides:[{id:'intro'},{id:'sermon'}]}));
 await writeFile(macro,JSON.stringify({name:'Worship to Sermon',steps:[
  {action:'show-slide',slideId:'sermon'},
  {action:'set-obs-preview',scene:'Sermon Camera'},
  {action:'stage-message',text:'PRIVATE_PASTOR_PROMPT'},
  {action:'start-stream'}
 ]}));
 const child=spawn(process.execPath,[server],{env,stdio:['ignore','ignore','pipe']});
 try{
  let ready=false;
  for(let tries=0;tries<80;tries++){
   try{await readFile(state);ready=true;break;}catch{await new Promise(r=>setTimeout(r,35));}
  }
  assert.equal(ready,true,'Managed presentation session must be ready.');
  const invoke=async(...args)=>{
   const {stdout}=await exec(process.execPath,[cli,...args],{env,timeout:2000});
   return JSON.parse(stdout);
  };
  await invoke('load','--file',deck);
  const before=await invoke('status');
  const preview=await invoke('macro-preview','--file',macro);
  const after=await invoke('status');
  assert.equal(preview.executionAllowed,false);
  assert.equal(preview.applied,false);
  assert.ok(preview.requiredGrants.includes('obs.start-stream'));
  assert.equal(JSON.stringify(preview).includes('PRIVATE_PASTOR_PROMPT'),false);
  assert.deepEqual(after,before);
 }finally{
  child.kill('SIGTERM');
  await Promise.race([new Promise(r=>child.once('close',r)),
    new Promise(r=>setTimeout(r,1200))]);
  await rm(home,{recursive:true,force:true});
 }
});
