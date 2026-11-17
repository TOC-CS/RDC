import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,writeFile,symlink,rm,lstat} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createCheckpointWriter,readRecoveryCheckpoint,clearVerifiedDeadControl} from '../src/managed-recovery.mjs';

const secure=async fn=>{
 const dir=await mkdtemp(join(tmpdir(),'presentation-security-test-'));
 const paths={dir,file:join(dir,'control.json')};
 try{return await fn(paths);}finally{await rm(dir,{recursive:true,force:true});}
};
const state={title:'Rehearsal',theme:'dark',index:1,
 slides:[{id:'one',title:'First'},{id:'two',title:'Second'}],
 armed:true,started:true,token:'secret-never-write-me',
 viewerToken:'also-never-write-me'};

test('private checkpoint retains current deck and index but no bearer token or live authorization',()=>secure(async paths=>{
 const writer=createCheckpointWriter(paths);
 await writer.save(state);
 const file=join(paths.dir,'last-known.json');
 const st=await lstat(file);
 assert.equal(st.mode&0o077,0);
 const raw=await readFile(file,'utf8');
 assert.ok(!raw.includes(state.token));
 assert.ok(!raw.includes(state.viewerToken));
 assert.ok(!raw.includes('"armed"'));
 const recovery=await readRecoveryCheckpoint(paths);
 assert.equal(recovery.index,1);
 assert.equal(recovery.deck.slides[1].id,'two');
}));
test('private checkpoint refuses symlinked and group-readable state files',()=>secure(async paths=>{
 const root=join(paths.dir,'source.json');
 await writeFile(root,JSON.stringify({schema:'invalid'}),{mode:0o600});
 await symlink(root,join(paths.dir,'last-known.json'));
 await assert.rejects(()=>readRecoveryCheckpoint(paths),/owner-only/i);
}));
test('invalid recovery schema never authorizes restoring a presentation',()=>secure(async paths=>{
 const file=join(paths.dir,'last-known.json');
 await writeFile(file,JSON.stringify({schema:'wrong',savedAt:Date.now(),
   index:0,deck:{slides:[{id:'x'}]}}),{mode:0o600});
 await assert.rejects(()=>readRecoveryCheckpoint(paths),/schema|position|age/i);
}));
test('verified active owner PID prevents a new managed server from replacing its control file',()=>secure(async paths=>{
 const existing={pid:process.pid,instanceId:'live-session-123'};
 await writeFile(paths.file,JSON.stringify(existing),{mode:0o600});
 await assert.rejects(()=>clearVerifiedDeadControl(paths,{readCurrent:async()=>existing}),/already owns/i);
 assert.equal(JSON.parse(await readFile(paths.file,'utf8')).instanceId,existing.instanceId);
}));
test('verified dead PID cleanup only removes the exact old control file',()=>secure(async paths=>{
 const old={pid:2147483647,instanceId:'dead-session-123'};
 await writeFile(paths.file,JSON.stringify(old),{mode:0o600});
 const outcome=await clearVerifiedDeadControl(paths,{readCurrent:async()=>old});
 assert.equal(outcome.recoveredStaleControl,true);
 await assert.rejects(()=>lstat(paths.file),{code:'ENOENT'});
}));
test('no-op status changes do not rewrite a checkpoint unnecessarily',()=>secure(async paths=>{
 const writer=createCheckpointWriter(paths);
 await writer.save(state);
 const file=join(paths.dir,'last-known.json');
 const first=await lstat(file);
 await new Promise(r=>setTimeout(r,25));
 await writer.save({...state,held:true,mode:'automatic'});
 const second=await lstat(file);
 assert.equal(second.mtimeMs,first.mtimeMs);
 assert.equal(second.ino,first.ino);
}));
