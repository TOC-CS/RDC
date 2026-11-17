#!/usr/bin/env node
// Isolated 30-transition benchmark with durable private checkpoint writes.
// Does not access owner desktop, audio, video, other processes or public APIs.
import {spawn} from 'node:child_process';
import {mkdtemp,readFile,rm} from 'node:fs/promises';
import {performance} from 'node:perf_hooks';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath} from 'node:url';

const server=fileURLToPath(new URL('./managed-server.mjs',import.meta.url));
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const percentile=(values,q)=>{const a=[...values].sort((a,b)=>a-b);
 return Math.round(a[Math.ceil(a.length*q)-1]*100)/100;};
export async function benchmarkManagedCheckpoint({transitions=30}={}){
 if(!Number.isInteger(transitions)||transitions<1||transitions>100)
   throw new Error('Choose one to 100 transitions.');
 const dir=await mkdtemp(join(tmpdir(),'toc-managed-latency-'));
 const child=spawn(process.execPath,[server],{
   env:{...process.env,PRESENTATION_AGENT_STATE_DIR:dir},
   stdio:['ignore','ignore','pipe']
 });
 let stderr='';
 child.stderr.on('data',data=>{if(stderr.length<300)stderr+=String(data).slice(0,300);});
 let state=null;
 try{
   for(let i=0;i<150;i++){
     if(child.exitCode!==null)throw new Error('Isolated managed server exited.');
     try{state=JSON.parse(await readFile(join(dir,'control.json'),'utf8'));break;}
     catch{await delay(20);}
   }
   if(!state)throw new Error('Isolated managed server failed to become ready.');
   const url='http://127.0.0.1:'+state.port;
   const post=async(path,args)=>{
     const resp=await fetch(url+path,{
       method:'POST',
       headers:{Authorization:'Bearer '+state.token,'Content-Type':'application/json'},
       body:JSON.stringify(args),signal:AbortSignal.timeout(3000)
     });
     if(resp.status!==200)throw new Error('Isolated managed command failed: HTTP '+resp.status);
     return resp.json();
   };
   await post('/v1/load',{deck:{slides:[{id:'first'},{id:'second'}]}});
   await post('/v1/start',{mode:'manual'});
   const timings=[];
   for(let i=0;i<transitions;i++){
     const action=i%2===0?'next':'previous',index=i%2===0?1:0;
     const t=performance.now();
     const receipt=await post('/v1/command',{action,idempotencyKey:'benchmark-'+i});
     const elapsed=performance.now()-t;
     if(!receipt.changed)throw new Error('Managed presentation command did not advance.');
     const recovered=JSON.parse(await readFile(join(dir,'last-known.json'),'utf8'));
     if(recovered.index!==index)throw new Error('Durable checkpoint missed a completed slide command.');
     timings.push(elapsed);
   }
   return {
     schema:'toc.presentation.managed-durable-latency/v1',
     samples:timings.length,
     durableCheckpointConfirmed:true,
     p50Ms:percentile(timings,.5),p95Ms:percentile(timings,.95),
     maxMs:percentile(timings,1),
     physicalProjectionMeasured:false,
     note:'End-to-end isolated managed HTTP reply includes private checkpoint write and disk sync. No native apps or physical output.'
   };
 }finally{
   child.kill('SIGTERM');
   await Promise.race([
     new Promise(resolve=>child.once('close',resolve)),
     delay(1400)
   ]);
   if(child.exitCode===null)child.kill('SIGKILL');
   await rm(dir,{recursive:true,force:true,maxRetries:6,retryDelay:100});
 }
}
if(process.argv[1]&&import.meta.url===new URL('file://'+process.argv[1]).href){
 try{process.stdout.write(JSON.stringify(await benchmarkManagedCheckpoint(),null,2)+'\n');}
 catch(error){process.stderr.write('Managed benchmark failed: '+String(error.message)+'\n');process.exitCode=1;}
}
