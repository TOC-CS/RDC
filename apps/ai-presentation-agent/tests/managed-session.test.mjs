import test from 'node:test';
import assert from 'node:assert/strict';
import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {mkdtemp,readFile,writeFile,stat,access,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
const exec=promisify(execFile);
const server=fileURLToPath(new URL('../scripts/managed-server.mjs',import.meta.url));
const client=fileURLToPath(new URL('../scripts/presentationctl.mjs',import.meta.url));
async function waitForState(file,child){
 const begun=Date.now();
 while(Date.now()-begun<3500){
   if(child.exitCode!==null)throw new Error('Server exited before private state was ready: '+child.exitCode);
   try{const state=JSON.parse(await readFile(file,'utf8'));if(state.port&&state.instanceId)return state;}
   catch{}
   await new Promise(r=>setTimeout(r,30));
 }
 throw new Error('Managed session did not create private state file.');
}
test('durable local session is shared across independent CLI processes without exposing its private token',async()=>{
 const root=await mkdtemp(join(tmpdir(),'presentation-managed-'));
 const state=join(root,'control.json'), deck=join(root,'deck.json'),cue=join(root,'cue.json');
 await writeFile(deck,JSON.stringify({title:'Worship',slides:[
   {id:'first',title:'Welcome'},
   {id:'chorus',title:'Chorus',song:'Original',section:'chorus',text:'We will sing together'}
 ]}));
 await writeFile(cue,JSON.stringify({source:'bandmates',type:'song.section',song:'Original',section:'chorus',eventId:'first-chorus'}));
 const env={...process.env,PRESENTATION_AGENT_STATE_DIR:root};
 const child=spawn(process.execPath,[server],{env,stdio:['ignore','pipe','pipe']});
 let serverLog='';
 child.stderr.on('data',buf=>{if(serverLog.length<2000)serverLog+=buf.toString();});
 try{
   const privateState=await waitForState(state,child);
   assert.equal((await stat(state)).mode&0o077,0,'Credential file must be owner-only.');
   const invoke=async(...args)=>{
     const {stdout}=await exec(process.execPath,[client,...args],{env,timeout:2000});
     assert.equal(stdout.includes(privateState.token),false,'CLI must not print private token.');
     return JSON.parse(stdout);
   };
   assert.equal((await invoke('load','--file',deck)).current.id,'first');
   assert.equal((await invoke('start','automatic')).started,true);
   const change=await invoke('cue','--file',cue);
   assert.equal(change.changed,true);
   assert.equal((await invoke('status')).current.id,'chorus');
   assert.equal((await invoke('hold')).reason,'held');
   assert.equal((await invoke('status')).held,true);
   assert.equal((await invoke('resume')).reason,'resumed');
   assert.equal((await invoke('status')).held,false);
   const cap=await invoke('capabilities');
   assert.equal(cap.operatorGrantPresent,false);
   // A repeated owner/AI command with the same stable request identity must
   // return the original receipt, without advancing a second time.
   await writeFile(deck,JSON.stringify({slides:[
     {id:'one'},{id:'two'},{id:'three'}
   ]}));
   await invoke('load','--file',deck);
   await invoke('start','manual');
   const firstAdvance=await invoke('next','--request-id','rdc-job-stable-1');
   const repeatedAdvance=await invoke('next','--request-id','rdc-job-stable-1');
   assert.deepEqual(firstAdvance,repeatedAdvance);
   assert.equal((await invoke('status')).current.id,'two');
   const secondAdvance=await invoke('next','--request-id','rdc-job-stable-2');
   assert.equal(secondAdvance.slide.id,'three');
   await assert.rejects(()=>invoke('previous','--request-id','rdc-job-stable-2'),/conflict/i);
   const other=spawn(process.execPath,[server],{env,stdio:['ignore','pipe','pipe']});
   let secondExit;
   try{secondExit=await Promise.race([new Promise(r=>other.once('close',r)),new Promise((_,reject)=>setTimeout(()=>reject(Error('second server failed to reject duplicate state')),1200))]);}
   finally{other.kill('SIGTERM');}
   assert.notEqual(secondExit,0,'Second server must not silently overwrite an existing session.');
   assert.equal(JSON.parse(await readFile(state,'utf8')).instanceId,privateState.instanceId);
 }finally{
   child.kill('SIGTERM');
   await Promise.race([new Promise(r=>child.once('close',r)),new Promise(r=>setTimeout(r,1200))]);
   await assert.rejects(access(state),{code:'ENOENT'},'State file must disappear after a clean shutdown.');
   await rm(root,{recursive:true,force:true});
 }
});
test('managed controller help and refusal require no persistent process or credentials',async()=>{
 const {stdout}=await exec(process.execPath,[client,'--help'],{timeout:1500});
 assert.match(stdout,/status/);
 const root=await mkdtemp(join(tmpdir(),'presentation-nostate-'));
 try{
   await assert.rejects(()=>exec(process.execPath,[client,'status'],{
     env:{...process.env,PRESENTATION_AGENT_STATE_DIR:root},timeout:1500
   }),/No active presentation|state/i);
 }finally{await rm(root,{recursive:true,force:true});}
});
