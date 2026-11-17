import test from 'node:test';
import assert from 'node:assert/strict';
import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {mkdtemp,readFile,writeFile,rm,stat,access} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath} from 'node:url';

const exec=promisify(execFile);
const serverScript=fileURLToPath(new URL('../scripts/managed-server.mjs',import.meta.url));
const client=fileURLToPath(new URL('../scripts/presentationctl.mjs',import.meta.url));

async function waitState(file,child,previousInstance=null){
 for(let i=0;i<160;i++){
   if(child.exitCode!==null)throw Error('Server stopped before recovery session was available.');
   try{
     const status=JSON.parse(await readFile(file,'utf8'));
     if(status.port&&status.instanceId&&status.instanceId!==previousInstance)return status;
   }catch{}
   await new Promise(r=>setTimeout(r,25));
 }
 throw Error('Recovery session private control file was not created.');
}
test('managed session preserves last slide after isolated process crash but never auto-arms output',
 {timeout:18000},async()=>{
 const dir=await mkdtemp(join(tmpdir(),'ai-presentation-crash-recovery-'));
 const stateFile=join(dir,'control.json');
 const deckFile=join(dir,'deck.json');
 await writeFile(deckFile,JSON.stringify({title:'Unattended rehearsal',
   slides:[{id:'welcome',title:'Welcome'},{id:'sermon',title:'Sermon'},{id:'closing',title:'Closing'}]}));
 const env={...process.env,PRESENTATION_AGENT_STATE_DIR:dir};
 const launch=()=>spawn(process.execPath,[serverScript],{env,stdio:['ignore','pipe','pipe']});
 const cmd=async(...args)=>{
   const {stdout}=await exec(process.execPath,[client,...args],{env,timeout:3500});
   return JSON.parse(stdout);
 };
 let first=null,second=null;
 try{
   first=launch();
   const firstControl=await waitState(stateFile,first);
   await cmd('load','--file',deckFile);
   await cmd('start','manual');
   await cmd('next','--request-id','before-process-crash');
   assert.equal((await cmd('status')).current.id,'sermon');
   assert.equal((await stat(join(dir,'last-known.json'))).mode&0o077,0,
      'Private recovery deck must be readable by owner only.');
   first.kill('SIGKILL');
   await new Promise(resolve=>first.once('close',resolve));
   second=launch();
   const secondControl=await waitState(stateFile,second,firstControl.instanceId);
   assert.notEqual(secondControl.instanceId,firstControl.instanceId);
   assert.notEqual(secondControl.token,firstControl.token,'Old bearer must never be reused.');
   const recovered=await cmd('status');
   assert.equal(recovered.current.id,'sermon');
   assert.equal(recovered.started,false);
   assert.equal(recovered.armed,false);
   assert.equal(recovered.held,true);
   assert.equal(recovered.recoveryPreview,true);
   const start=await cmd('start','manual');
   assert.equal(start.started,true);
   assert.equal(start.current.id,'welcome','New show start must be deliberate and deterministic.');
 }finally{
   for(const child of [first,second])if(child&&child.exitCode===null){
     child.kill('SIGTERM');
     await Promise.race([
       new Promise(r=>child.once('close',r)),
       new Promise(r=>setTimeout(r,1100))
     ]);
     if(child.exitCode===null)child.kill('SIGKILL');
   }
   await rm(dir,{recursive:true,force:true,maxRetries:4,retryDelay:80});
 }
});
test('stop then unload clears durable deck so a crash restart cannot resurrect a finished presentation',
 {timeout:18000},async()=>{
 const dir=await mkdtemp(join(tmpdir(),'presentation-unload-crash-'));
 const control=join(dir,'control.json'),deckPath=join(dir,'deck.json');
 const checkpoint=join(dir,'last-known.json');
 await writeFile(deckPath,JSON.stringify({
   title:'Completed local presentation',slides:[{id:'opening'},{id:'closing'}]
 }));
 const env={...process.env,PRESENTATION_AGENT_STATE_DIR:dir};
 const launch=()=>spawn(process.execPath,[serverScript],{env,stdio:['ignore','pipe','pipe']});
 const execCli=async(...args)=>{
   const {stdout}=await exec(process.execPath,[client,...args],{env,timeout:3000});
   return JSON.parse(stdout);
 };
 let first=null,second=null;
 try{
   first=launch();
   const old=await waitState(control,first);
   await execCli('load','--file',deckPath);
   await execCli('start','manual');
   await execCli('next','--request-id','completed-final-slide');
   await execCli('stop');
   assert.equal((await readFile(checkpoint,'utf8')).includes('closing'),true);
   const clear=await execCli('unload');
   assert.equal(clear.slides.length,0);
   await assert.rejects(access(checkpoint),{code:'ENOENT'});
   first.kill('SIGKILL');
   await new Promise(resolve=>first.once('close',resolve));
   second=launch();
   const newer=await waitState(control,second,old.instanceId);
   assert.notEqual(newer.token,old.token);
   const recovered=await execCli('status');
   assert.equal(recovered.slides.length,0);
   assert.equal(recovered.current,null);
   assert.equal(recovered.started,false);
   assert.equal(recovered.armed,false);
   assert.equal(recovered.recoveryPreview,false);
 }finally{
   for(const child of [first,second])if(child&&child.exitCode===null){
     child.kill('SIGTERM');
     await Promise.race([
       new Promise(r=>child.once('close',r)),
       new Promise(r=>setTimeout(r,1100))
     ]);
     if(child.exitCode===null)child.kill('SIGKILL');
   }
   await rm(dir,{recursive:true,force:true,maxRetries:4,retryDelay:80});
 }
});
