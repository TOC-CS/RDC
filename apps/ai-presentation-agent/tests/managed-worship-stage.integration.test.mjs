import test from 'node:test';
import assert from 'node:assert/strict';
import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {mkdtemp,readFile,writeFile,rm,stat} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath} from 'node:url';

const exec=promisify(execFile);
const root=fileURLToPath(new URL('..',import.meta.url));
const server=fileURLToPath(new URL('../scripts/managed-server.mjs',import.meta.url));
const cli=fileURLToPath(new URL('../scripts/presentationctl.mjs',import.meta.url));
const example=fileURLToPath(new URL('../skills/ai-presentation-agent/worship/examples/sunday-service.json',import.meta.url));

test('independent managed service protects private confidence while allowing worship cue control', {timeout:13000},async()=>{
 const dir=await mkdtemp(join(tmpdir(),'toc-private-worship-'));
 const env={...process.env,PRESENTATION_AGENT_STATE_DIR:dir};
 const fixture=join(dir,'worship.json');
 const content=JSON.parse(await readFile(example,'utf8'));
 const privateNote='SECRET_STAGE_ONLY_NOTE_MUST_NEVER_APPEAR_PUBLIC';
 content.items[0].notes=privateNote;
 await writeFile(fixture,JSON.stringify(content),{mode:0o600});
 const child=spawn(globalThis.process.execPath,[server],{env,stdio:['ignore','pipe','pipe']});
 const stateFile=join(dir,'control.json');
 let stagePath=null;
 try{
   let state;
   for(let i=0;i<120;i++){
     try{state=JSON.parse(await readFile(stateFile,'utf8'));break;}catch{}
     if(child.exitCode!==null)throw Error('Isolated managed service exited');
     await new Promise(resolve=>setTimeout(resolve,30));
   }
   assert.ok(state?.port,'Isolated managed service did not initialize.');
   assert.match(state.stageToken,/^[a-f0-9]{64}$/);
   assert.notEqual(state.stageToken,state.token);
   assert.notEqual(state.stageToken,state.viewerToken);
   assert.equal((await stat(stateFile)).mode&0o077,0);
   const invoke=async(...args)=>{
     const {stdout}=await exec(globalThis.process.execPath,[cli,...args],{env,timeout:3200});
     assert.equal(stdout.includes(state.token),false);
     assert.equal(stdout.includes(state.stageToken),false);
     return JSON.parse(stdout);
   };
   const result=await invoke('worship-load','--file',fixture);
   assert.ok(result.slides.length>8);
   assert.ok(!JSON.stringify(result).includes(privateNote));
   assert.equal((await invoke('stage-check')).privateStage,true);
   assert.deepEqual(await invoke('viewer-check'),{available:true,live:true});
   assert.equal((await invoke('stream-check')).publicStream,true);
   const stageHtml=join(dir,'stage-confidence.html');
   const out=await invoke('stage-export','--file',stageHtml);
   assert.equal(out.created,true);
   assert.equal(out.privateStage,true);
   assert.equal((await stat(stageHtml)).mode&0o077,0);
   stagePath=stageHtml;
   const streamHtml=join(dir,'stream-overlay.html');
   const streamFile=await invoke('stream-export','--file',streamHtml);
   assert.equal(streamFile.created,true);
   assert.equal(streamFile.publicStream,true);
   assert.equal((await stat(streamHtml)).mode&0o077,0);
   const base='http://127.0.0.1:'+state.port;
   const publicResponse=await fetch(base+'/v1/viewer?key='+state.viewerToken);
   assert.equal(publicResponse.status,200);
   const publicHtml=await publicResponse.text();
   assert.equal(publicHtml.includes(privateNote),false);
   assert.equal(publicHtml.includes(state.stageToken),false);
   const broadcast=await fetch(base+'/v1/stream-overlay?key='+state.streamToken);
   assert.equal(broadcast.status,200);
   assert.equal((await broadcast.text()).includes(privateNote),false);
   const stageDenied=await fetch(base+'/v1/stage?key='+state.viewerToken);
   assert.equal(stageDenied.status,401);
   const stageAllowed=await fetch(base+'/v1/stage?key='+state.stageToken);
   assert.equal(stageAllowed.status,200);
   assert.equal((await stageAllowed.text()).includes(privateNote),false);
   const status=await invoke('status');
   assert.equal(JSON.stringify(status).includes(privateNote),false);
   await invoke('start','manual');
   await invoke('stop');
   await invoke('unload');
   assert.equal((await invoke('status')).slides.length,0);
 }finally{
   child.kill('SIGTERM');
   await Promise.race([
     new Promise(resolve=>child.once('close',resolve)),
     new Promise(resolve=>setTimeout(resolve,2000))
   ]);
   if(child.exitCode===null)child.kill('SIGKILL');
   await rm(dir,{recursive:true,force:true});
 }
});
