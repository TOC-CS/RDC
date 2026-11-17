import test from 'node:test';
import assert from 'node:assert/strict';
import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {mkdtemp,stat,readFile,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';

const serverPath=fileURLToPath(new URL('../scripts/managed-server.mjs',import.meta.url));
const cliPath=fileURLToPath(new URL('../scripts/presentationctl.mjs',import.meta.url));
const exec=promisify(execFile);
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
test('managed session issues separate private viewer key and exports a safe local viewer file',async()=>{
 const folder=await mkdtemp(join(tmpdir(),'managed-present-view-'));
 const env={...process.env,PRESENTATION_AGENT_STATE_DIR:folder};
 const server=spawn(process.execPath,[serverPath],{env,stdio:['ignore','pipe','pipe']});
 const stateFile=join(folder,'control.json'),deckFile=join(folder,'deck.json'),
  viewerFile=join(folder,'private-viewer.html');
 const run=async(...args)=>{
   const {stdout}=await exec(process.execPath,[cliPath,...args],{env,timeout:2500});
   return stdout;
 };
 try{
   let state=null;
   for(let i=0;i<110;i++){
     try{state=JSON.parse(await readFile(stateFile,'utf8'));break;}catch{await sleep(20);}
   }
   assert.ok(state,'Server must issue private state.');
   assert.match(state.viewerToken,/^[a-f0-9]{64}$/);
   assert.notEqual(state.viewerToken,state.token);
   await writeFile(deckFile,JSON.stringify({slides:[{id:'title',title:'Live View'}]}));
   await run('load','--file',deckFile);
   const check=await run('viewer-check');
   assert.equal(check.includes(state.viewerToken),false);
   assert.deepEqual(JSON.parse(check),{available:true,live:true});
   const result=JSON.parse(await run('viewer-export','--file',viewerFile));
   assert.equal(result.created,true);
   assert.equal(result.file,viewerFile);
   assert.equal(JSON.stringify(result).includes(state.viewerToken),false);
   const privateFile=await stat(viewerFile);
   assert.equal(privateFile.mode&0o077,0);
   const html=await readFile(viewerFile,'utf8');
   assert.ok(html.includes('/v1/viewer?key='));
   assert.ok(html.includes(state.viewerToken));
   await assert.rejects(()=>run('viewer-export','--file',viewerFile),/exists|EEXIST/i);
 }finally{
   server.kill('SIGTERM');
   await Promise.race([new Promise(r=>server.once('close',r)),sleep(1200)]);
   await rm(folder,{recursive:true,force:true});
 }
});
