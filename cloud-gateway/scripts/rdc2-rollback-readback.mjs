/**
 * OFFLINE, SOURCE-ONLY rollback compatibility qualification for RDC 2.0.
 *
 * Loads the exact SHA-256 pinned candidate reader bytes into an isolated,
 * in-memory SQLite fixture containing already-archived original operations.
 * No owner Site or worker access, no protected version verification, no
 * credentials, file mutations, cloud traffic, or activation of archive writes.
 */
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {DatabaseSync} from 'node:sqlite';
import {basename,resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {RDC2Journal} from '../lib/v2/rdc2-journal.mjs';

const sha=raw=>createHash('sha256').update(raw).digest('hex');
const literalDigest=/^[a-f0-9]{64}$/;
const owner='rollback-synthetic-owner';
const checkNames=[
  'confirmedArchivedDuplicate','expiredQueuedDuplicate','originalIdPreserved',
  'expiredResultWithheld','forgedDigestRejected','foreignOwnerRejected',
  'freshUnrelatedAdmission','duplicateCompletionNoReplay'
];
function sqliteFixture(){
  const db=new DatabaseSync(':memory:');
  const storage={
    sql:{exec(sql,...args){
      const rows=/^\s*(SELECT|PRAGMA|WITH)\b|\bRETURNING\b/i.test(sql)?
        db.prepare(sql).all(...args):/^\s*CREATE/i.test(sql)?
        (db.exec(sql),[]):(db.prepare(sql).run(...args),[]);
      return {toArray:()=>rows};
    }},
    transactionSync(work){
      db.exec('BEGIN');
      try{const result=work();db.exec('COMMIT');return result}
      catch(error){db.exec('ROLLBACK');throw error}
    },
  };
  return {db,storage};
}
function request(key){
  const requestJson=JSON.stringify({name:'rdc_job_run',
    arguments:{fixture:key,scope:'rollback-preflight-only'}});
  return {principal:owner,requestKey:key,requestJson,
    requestDigest:sha(requestJson),tool:'rdc_job_run',mutating:true};
}
const thrownCode=(task,code)=>{try{task();return false}catch(error){return error?.code===code}};
const blocked=(message)=>({sourceCompatible:false,releaseApproved:false,
  hostedProtectedVersionVerified:false,blockers:[message]});

export async function runRollbackReadback({candidatePath,expectedSha256}={}){
  if(typeof expectedSha256!=='string'||!literalDigest.test(expectedSha256))
    throw new Error('expected SHA-256 required as 64 lowercase hex digits');
  if(typeof candidatePath!=='string'||!candidatePath)
    throw new Error('candidate path required');
  const path=resolve(candidatePath);
  if(basename(path)!=='rdc2-journal.mjs')
    throw new Error('candidate must be an exact rdc2-journal.mjs source file');
  const source=readFileSync(path);
  const actual=sha(source);
  if(actual!==expectedSha256)throw new Error('candidate source SHA-256 mismatch');
  const outcome={
    candidateSha256:actual,
    sourceCompatible:false,
    releaseApproved:false,
    hostedProtectedVersionVerified:false,
    archiveEnablementApproved:false,
    scope:'synthetic-in-memory-SQLite-source-readback-only',
    checks:Object.fromEntries(checkNames.map(name=>[name,false])),
    blockers:[]
  };
  let Candidate;
  try{
    // Import the exact checked bytes, eliminating path read/import races.
    // This script must only be run against authorized local source.
    const loadedCandidate=await import('data:text/javascript;base64,'+source.toString('base64'));
    Candidate=loadedCandidate.RDC2Journal;
    if(typeof Candidate!=='function')throw new Error('candidate_missing_reader');
  }catch{outcome.blockers.push('candidate_load_failed');return outcome}
  const {db,storage}=sqliteFixture();
  let now=1700000000000;
  try{
    const seed=new RDC2Journal(storage,{now:()=>now,maxRecords:8});
    seed.bindOwner(owner,{bootstrap:true});
    seed.heartbeat();
    const done=seed.enqueue(request('previously-committed-mutation'));
    const claimed=seed.claim();
    const resultJson=JSON.stringify({content:[{type:'text',text:'synthetic-only'}]});
    const resultDigest=sha(resultJson);
    seed.complete({id:done.id,claimId:claimed.claimId,
      requestDigest:claimed.requestDigest,resultJson,resultDigest});
    const queued=seed.enqueue(request('expired-unclaimed-mutation'));
    now+=3_600_001;
    seed.sweep();
    if(seed.archiveRetired(8)!==2)throw new Error('fixture_archive_failed');
    if(db.prepare('SELECT count(*) AS count FROM rdc2_ops').get().count!==0)
      throw new Error('fixture_hot_rows_not_retired');
    const candidate=new Candidate(storage,{now:()=>now,maxRecords:8});
    candidate.heartbeat();
    const reusedDone=candidate.enqueue(request('previously-committed-mutation'));
    const reusedQueued=candidate.enqueue(request('expired-unclaimed-mutation'));
    outcome.checks.confirmedArchivedDuplicate=reusedDone.reused===true&&reusedDone.id===done.id;
    outcome.checks.expiredQueuedDuplicate=reusedQueued.reused===true&&reusedQueued.id===queued.id;
    outcome.checks.originalIdPreserved=reusedDone.id===done.id&&reusedQueued.id===queued.id;
    const recovery=candidate.recover(owner,done.id);
    outcome.checks.expiredResultWithheld=recovery.state==='result_expired'&&
      !Object.hasOwn(recovery,'resultJson')&&!Object.hasOwn(recovery,'resultKey');
    outcome.checks.forgedDigestRejected=thrownCode(()=>candidate.enqueue({
      ...request('previously-committed-mutation'),
      requestDigest:sha('forged-rollback-input')}),'request_id_conflict');
    outcome.checks.foreignOwnerRejected=thrownCode(
      ()=>candidate.recover('foreign-synthetic-owner',done.id),'owner_forbidden');
    const fresh=candidate.enqueue(request('unrelated-new-work'));
    outcome.checks.freshUnrelatedAdmission=fresh.reused===false&&
      fresh.id!==done.id&&fresh.id!==queued.id;
    const duplicate=candidate.complete({id:done.id,claimId:claimed.claimId,
      requestDigest:claimed.requestDigest,resultJson,resultDigest});
    outcome.checks.duplicateCompletionNoReplay=duplicate.duplicate===true&&
      duplicate.id===done.id;
  }catch{
    outcome.blockers.push('candidate_reader_failed_or_unsafe');
  }finally{db.close()}
  if(!outcome.checks.confirmedArchivedDuplicate)
    outcome.blockers.push('unsafe_replay_archived_confirmed_mutation');
  if(!outcome.checks.expiredQueuedDuplicate)
    outcome.blockers.push('unsafe_replay_archived_expired_queue');
  for(const [name,passed] of Object.entries(outcome.checks))
    if(!passed&&!['confirmedArchivedDuplicate','expiredQueuedDuplicate'].includes(name))
      outcome.blockers.push('failed_'+name);
  outcome.sourceCompatible=outcome.blockers.length===0;
  // A source test can NEVER attest that a protected inactive owner-private
  // Site version exists or is restorable. The production gate stays closed.
  return outcome;
}

if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href){
  const args=process.argv.slice(2);
  const flag=name=>args[args.indexOf(name)+1];
  try{
    const result=await runRollbackReadback({
      candidatePath:flag('--candidate'),expectedSha256:flag('--sha256')
    });
    console.log(JSON.stringify(result,null,2));
    process.exitCode=result.sourceCompatible?0:2;
  }catch(error){
    let reason='candidate_unavailable';
    if(String(error.message).includes('SHA-256 mismatch'))reason='sha256_mismatch';
    else if(String(error.message).includes('expected SHA-256'))reason='unverified_candidate_sha256';
    else if(String(error.message).includes('candidate'))reason='invalid_candidate';
    console.log(JSON.stringify(blocked(reason),null,2));
    process.exitCode=2;
  }
}
