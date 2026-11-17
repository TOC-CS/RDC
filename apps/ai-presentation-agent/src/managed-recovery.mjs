// Private, token-free local crash checkpoint and conservative stale-session
// recovery. No projector, microphone, camera, or external output is opened.
import {open,rename,unlink,readFile,lstat} from 'node:fs/promises';
import {join} from 'node:path';
import {randomUUID} from 'node:crypto';

const SCHEMA='toc.presentation.private-recovery/v1';
const MAX_BYTES=2_097_152;
export const CHECKPOINT_FILE='last-known.json';
const LOCK_FILE='.control-recovery.lock';

function ownerFile(stat,path){
 if(!stat.isFile()||stat.isSymbolicLink()||(stat.mode&0o077)!==0||
   (typeof process.getuid==='function'&&stat.uid!==process.getuid()))
   throw new Error('Private recovery state must be an owner-only regular file: '+path);
}
function checkpointPath(paths){return join(paths.dir,CHECKPOINT_FILE);}
function checkAge(time){
 return Number.isFinite(time)&&time>0&&time<=Date.now()+60_000&&Date.now()-time<7*24*3600*1000;
}
export async function readRecoveryCheckpoint(paths){
 const file=checkpointPath(paths);
 let st;
 try{st=await lstat(file);}
 catch(e){if(e.code==='ENOENT')return null;throw e;}
 ownerFile(st,CHECKPOINT_FILE);
 if(st.size>MAX_BYTES||st.size<12)
   throw new Error('Private recovery checkpoint size is invalid.');
 let content;
 try{content=JSON.parse(await readFile(file,'utf8'));}
 catch{throw new Error('Private recovery checkpoint contains invalid JSON.');}
 if(!content||content.schema!==SCHEMA||
   !content.deck||typeof content.deck!=='object'||
   !Array.isArray(content.deck.slides)||content.deck.slides.length<1||
   !Number.isInteger(content.index)||content.index<0||
   content.index>=content.deck.slides.length||!checkAge(content.savedAt))
   throw new Error('Private recovery checkpoint schema, position or age is invalid.');
 // No native adapter configuration, output authorization, or credentials are
 // ever restored. All deck data is validated again by PresentationDirector.
 return {deck:content.deck,index:content.index};
}
export function createCheckpointWriter(paths){
 let current=Promise.resolve(),lastSignature=null;
 const save=snapshot=>{
   if(!Array.isArray(snapshot?.slides)||snapshot.slides.length===0)return current;
   const content={index:snapshot.index??0,
     deck:{title:snapshot.title,theme:snapshot.theme,
       slides:snapshot.slides}};
   const signature=JSON.stringify(content);
   if(signature===lastSignature)return current;
   const data=JSON.stringify({schema:SCHEMA,savedAt:Date.now(),...content});
   if(Buffer.byteLength(data)>MAX_BYTES)
     throw new Error('Deck exceeds the 2 MiB private crash checkpoint limit.');
   lastSignature=signature;
   const write=current.catch(()=>{}).then(async()=>{
     const temp=join(paths.dir,'.last-known-'+process.pid+'-'+randomUUID()+'.tmp');
     try{
       await (async()=>{
         const handle=await open(temp,'wx',0o600);
         try{await handle.writeFile(data,'utf8');await handle.sync();}
         finally{await handle.close();}
       })();
       await rename(temp,checkpointPath(paths));
     }finally{await unlink(temp).catch(()=>{});}
   }).catch(error=>{
     lastSignature=null;
     throw error;
   });
   current=write;
   return write;
 };
 const clear=()=>{
   lastSignature=null;
   const run=current.catch(()=>{}).then(async()=>{
     await unlink(checkpointPath(paths)).catch(error=>{
       if(error.code!=='ENOENT')throw error;
     });
   });
   current=run;
   return run;
 };
 return {save,clear,flush:()=>current};
}
function liveProcess(pid){
 if(!Number.isSafeInteger(pid)||pid<1)throw new Error('Private managed session PID is invalid.');
 try{process.kill(pid,0);return true;}
 catch(error){
   if(error.code==='ESRCH')return false;
   // EPERM or an unknown OS error must never be interpreted as a dead session.
   throw new Error('Unable to establish that the previous private session stopped.');
 }
}
export async function clearVerifiedDeadControl(paths,{readCurrent}={}){
 // Current state reader performs 0600 owner/type checks and full schema check.
 if(typeof readCurrent!=='function')throw new TypeError('Verified private state reader is required.');
 let previous=await readCurrent();
 if(liveProcess(previous.pid))
   throw new Error('Another presentation session already owns this state directory.');
 const lockFile=join(paths.dir,LOCK_FILE);
 let lock=null;
 try{lock=await open(lockFile,'wx',0o600);}
 catch(error){
   if(error.code==='EEXIST')
     throw new Error('Private session recovery is already in progress or requires owner cleanup.');
   throw error;
 }
 try{
   // Re-read after acquiring the lock so a newer live instance is never
   // removed because an earlier PID was stale.
   const fresh=await readCurrent();
   if(fresh.instanceId!==previous.instanceId||liveProcess(fresh.pid))
     throw new Error('Private presentation owner changed; no stale session was removed.');
   await unlink(paths.file);
   return {recoveredStaleControl:true};
 }finally{
   await lock.close();
   await unlink(lockFile).catch(()=>{});
 }
}
