import test from 'node:test';
import assert from 'node:assert/strict';
import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {mkdtemp,readFile,writeFile,rename,mkdir,rmdir,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
const exec=promisify(execFile);
const server=fileURLToPath(new URL('../scripts/managed-server.mjs',import.meta.url));
const cli=fileURLToPath(new URL('../scripts/presentationctl.mjs',import.meta.url));
test('managed unload reports a private checkpoint removal failure, then safely retries once repaired',
 {timeout:14000},async()=>{
 const root=await mkdtemp(join(tmpdir(),'presentation-clear-failure-'));
 const env={...process.env,PRESENTATION_AGENT_STATE_DIR:root};
 const deck=join(root,'deck.json'),control=join(root,'control.json'),
       saved=join(root,'last-known.json'),backup=join(root,'saved.original');
 await writeFile(deck,JSON.stringify({slides:[{id:'one'},{id:'two'}]}));
 const child=spawn(process.execPath,[server],{env,stdio:['ignore','pipe','pipe']});
 const cmd=async(...args)=>{
   const {stdout}=await exec(process.execPath,[cli,...args],{env,timeout:3500});
   return JSON.parse(stdout);
 };
 try{
   for(let i=0;i<90;i++){
     try{const state=JSON.parse(await readFile(control,'utf8'));if(state.port)break;}
     catch{}
     await new Promise(r=>setTimeout(r,30));
   }
   await cmd('load','--file',deck);
   await cmd('start','manual');
   await cmd('next');
   await cmd('stop');
   await rename(saved,backup);
   await mkdir(saved,{mode:0o700});
   await assert.rejects(()=>cmd('unload'),/checkpoint|recovery|clear|storage/i);
   assert.equal((await cmd('status')).slides.length,0,'In-memory deck is already stopped and cleared.');
   await rmdir(saved);
   await cmd('unload');
   assert.equal((await cmd('status')).slides.length,0);
 }finally{
   child.kill('SIGTERM');
   await Promise.race([
     new Promise(r=>child.once('close',r)),
     new Promise(r=>setTimeout(r,1000))
   ]);
   if(child.exitCode===null)child.kill('SIGKILL');
   await rm(root,{recursive:true,force:true,maxRetries:4,retryDelay:60});
 }
});
