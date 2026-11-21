/**
 * RDC 2.0 private per-device Durable Object journal.
 * One colocated SQLite database. Original operation identity is authoritative.
 * No D1 polling, retries of uncertain mutations, or v1 schema access.
 */
const DEFAULTS=Object.freeze({
  queueTtlMs:30_000,unknownMs:120_000,resultTtlMs:3_600_000,
  onlineMs:35_000,maxQueue:64,maxRecords:10_000,
  maxRequestBytes:1_048_576,maxResultBytes:262_144,
  maxBulkResultBytes:12*1024*1024
});
const bytes=new TextEncoder();
const digestPattern=/^[a-f0-9]{64}$/;
const validText=(value,max)=>typeof value==='string'&&value.length>0&&value.length<=max;
export class RDC2Error extends Error {
  constructor(code,status=400){super(code);this.code=code;this.status=status}
}
function fail(code,status=400){throw new RDC2Error(code,status)}

export class RDC2Journal {
  constructor(storage,{now=Date.now,...limits}={}){
    if(typeof storage?.sql?.exec!=='function'||typeof storage?.transactionSync!=='function')
      fail('sqlite_storage_required',503);
    this.storage=storage;this.sql=storage.sql;this.now=now;
    this.limits={...DEFAULTS,...limits};
    this.sql.exec('CREATE TABLE IF NOT EXISTS rdc2_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)');
    this.sql.exec('CREATE TABLE IF NOT EXISTS rdc2_ops ('+
      'seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,'+
      'principal TEXT NOT NULL, request_key TEXT NOT NULL, request_digest TEXT NOT NULL,'+
      'request_json TEXT, request_size INTEGER NOT NULL, tool TEXT NOT NULL,'+
      'mutating INTEGER NOT NULL, state TEXT NOT NULL,'+
      'created_ms INTEGER NOT NULL, expires_ms INTEGER NOT NULL,'+
      'claim_id TEXT, claimed_ms INTEGER, result_json TEXT, result_key TEXT, result_digest TEXT,'+
      'result_size INTEGER NOT NULL DEFAULT 0, completed_ms INTEGER, result_expires_ms INTEGER,'+
      'UNIQUE(principal,request_key))');
    this.sql.exec('CREATE INDEX IF NOT EXISTS rdc2_queue_idx ON rdc2_ops(state,seq)');
    // Never make a previously accepted mutation executable again merely to
    // reclaim hot-journal capacity. Immutable, lightweight tombstones retain
    // its exact original identity, digest, claim and outcome indefinitely.
    this.sql.exec('CREATE TABLE IF NOT EXISTS rdc2_tombstones ('+
      'id TEXT PRIMARY KEY,principal TEXT NOT NULL,request_key TEXT NOT NULL,'+
      'request_digest TEXT NOT NULL,tool TEXT NOT NULL,mutating INTEGER NOT NULL,'+
      'state TEXT NOT NULL,claim_id TEXT,result_digest TEXT,'+
      'UNIQUE(principal,request_key))');
    // The unreleased early V2 journal predates the optional private R2
    // pointer. Preserve its persisted operations when that candidate is
    // upgraded in place. SQLite DDL is atomic, and this check is local.
    const columns=this.sql.exec('PRAGMA table_info(rdc2_ops)').toArray();
    if(!columns.some(column=>column.name==='result_key'))
      this.sql.exec('ALTER TABLE rdc2_ops ADD COLUMN result_key TEXT');
  }
  rows(sql,...values){return this.sql.exec(sql,...values).toArray()}
  first(sql,...values){return this.rows(sql,...values)[0]??null}
  atomic(fn){return this.storage.transactionSync(fn)}
  owner(){return this.first("SELECT value FROM rdc2_meta WHERE key='owner'")?.value??null}
  assertOwner(principal){
    if(!validText(principal,256))fail('principal_required',401);
    const owner=this.owner();
    if(owner===null)fail('owner_not_bound',503);
    if(owner!==principal)fail('owner_forbidden',403);
  }
  bindOwner(principal,{bootstrap=false}={}){
    if(!validText(principal,256))fail('principal_required',401);
    // Most owner requests are already enrolled. Read the immutable owner
    // before acquiring a SQLite write transaction on every hot-path call.
    const bound=this.owner();
    if(bound!==null){
      if(bound!==principal)fail('owner_forbidden',403);
      return bound;
    }
    if(bootstrap!==true)fail('owner_not_bound',503);
    // First enrollment remains atomic and rechecks the owner inside the
    // transaction so an optimistic read can never overwrite another owner.
    return this.atomic(()=>{
      const owner=this.owner();
      if(owner!==null){
        if(owner!==principal)fail('owner_forbidden',403);
        return owner;
      }
      this.sql.exec("INSERT INTO rdc2_meta(key,value) VALUES ('owner',?)",principal);
      return principal;
    });
  }
  heartbeat(){
    const now=this.now();
    this.sql.exec("INSERT INTO rdc2_meta(key,value) VALUES ('last_seen_ms',?) "+
      'ON CONFLICT(key) DO UPDATE SET value=excluded.value',String(now));
    return {lastSeenMs:now};
  }
  lastSeen(){
    const value=this.first("SELECT value FROM rdc2_meta WHERE key='last_seen_ms'")?.value;
    return value===undefined?null:Number(value);
  }
  online(time=this.now()){
    const last=this.lastSeen();
    // Date.now can move backwards after an OS clock adjustment. A heartbeat
    // originating in the future cannot prove that a device is still online.
    return last!==null&&time>=last&&time-last<=this.limits.onlineMs;
  }
  status(principal){
    this.assertOwner(principal);
    const now=this.now();
    const count=this.first("SELECT COUNT(*) AS count FROM rdc2_ops WHERE "+
      "(state='queued' AND expires_ms>?) OR (state='claimed' AND claimed_ms>?)",
      now,now-this.limits.unknownMs);
    return {online:this.online(now),lastSeenMs:this.lastSeen(),pending:Number(count?.count??0)};
  }
  phaseMetrics(principal,limit=30){
    this.assertOwner(principal);
    if(!Number.isInteger(limit)||limit<1||limit>100)
      fail('invalid_limit');
    // Read only existing durable timestamps. No new writes or cold-path
    // bookkeeping are introduced into admission, claim or completion.
    // Output contains opaque operation IDs and phase milliseconds only.
    const rows=this.rows('SELECT id,created_ms,claimed_ms,completed_ms '+
      "FROM rdc2_ops WHERE state='completed' AND claimed_ms IS NOT NULL "+
      'AND completed_ms IS NOT NULL ORDER BY seq DESC LIMIT ?',limit);
    // Wall-clock jumps can reverse durable timestamps. A negative phase
    // previously became an apparent 0 ms success, contaminating the owner
    // speed gate. Preserve the original ID but explicitly disqualify it.
    const samples=rows.map(entry=>{
      const valid=Number.isSafeInteger(entry.created_ms)&&
        Number.isSafeInteger(entry.claimed_ms)&&
        Number.isSafeInteger(entry.completed_ms)&&
        entry.claimed_ms>=entry.created_ms&&
        entry.completed_ms>=entry.claimed_ms;
      return {
        operationId:entry.id,
        queuePickupMs:valid?entry.claimed_ms-entry.created_ms:null,
        claimToResultMs:valid?entry.completed_ms-entry.claimed_ms:null,
        timingStatus:valid?'valid':'invalid_clock_order',
      };
    });
    const validSampleCount=samples.filter(entry=>entry.timingStatus==='valid').length;
    return {
      source:'rdc2-durable-journal',sampleCount:samples.length,
      validSampleCount,invalidSampleCount:samples.length-validSampleCount,
      resolutionMs:1,samples,
    };
  }
  enqueue({principal,requestKey,requestDigest,requestJson,tool,mutating=false}={}){
    return this.atomic(()=>{
      this.assertOwner(principal);
      if(!validText(requestKey,200)||!digestPattern.test(requestDigest??'')||
        typeof requestJson!=='string'||!validText(tool,128)||typeof mutating!=='boolean')
        fail('invalid_request');
      const size=bytes.encode(requestJson).length;
      if(size>this.limits.maxRequestBytes)fail('payload_too_large',413);
      const existing=this.first('SELECT * FROM rdc2_ops WHERE principal=? AND request_key=?',principal,requestKey) ??
        this.first('SELECT * FROM rdc2_tombstones WHERE principal=? AND request_key=?',principal,requestKey);
      if(existing){
        if(existing.request_digest!==requestDigest||existing.tool!==tool||
          existing.mutating!==(mutating?1:0))fail('request_id_conflict',409);
        return {id:existing.id,state:existing.state,reused:true};
      }
      let request;
      try{request=JSON.parse(requestJson)}
      catch{fail('invalid_request')}
      if(request===null||typeof request!=='object'||Array.isArray(request)||
        request.name!==tool||!request.arguments||
        typeof request.arguments!=='object'||Array.isArray(request.arguments))
        fail('invalid_request');
      const now=this.now();
      if(!this.online(now))fail('device_offline',503);
      const busy=this.first("SELECT COUNT(*) AS count FROM rdc2_ops WHERE "+
        "(state='queued' AND expires_ms>?) OR (state='claimed' AND claimed_ms>?)",
        now,now-this.limits.unknownMs);
      if(Number(busy.count)>=this.limits.maxQueue)fail('queue_full',429);
      const retained=this.first('SELECT COUNT(*) AS count FROM rdc2_ops');
      if(Number(retained.count)>=this.limits.maxRecords)fail('journal_full',429);
      const id=crypto.randomUUID();
      this.sql.exec('INSERT INTO rdc2_ops (id,principal,request_key,request_digest,request_json,'+
        'request_size,tool,mutating,state,created_ms,expires_ms)'+
        " VALUES (?,?,?,?,?,?,?,?,'queued',?,?)",
        id,principal,requestKey,requestDigest,requestJson,size,tool,mutating?1:0,
        now,now+this.limits.queueTtlMs);
      return {id,state:'queued',reused:false};
    });
  }
  claim(){
    return this.atomic(()=>{
      const now=this.now();
      const op=this.first("SELECT * FROM rdc2_ops WHERE state='queued' AND expires_ms>? "+
        'ORDER BY seq LIMIT 1',now);
      if(!op)return null;
      const claimId=crypto.randomUUID();
      this.sql.exec("UPDATE rdc2_ops SET state='claimed',claim_id=?,claimed_ms=? "+
        "WHERE id=? AND state='queued'",claimId,now,op.id);
      return {id:op.id,claimId,requestJson:op.request_json,requestDigest:op.request_digest,
        tool:op.tool,mutating:op.mutating===1,expiresAtMs:op.expires_ms};
    });
  }
  complete({id,claimId,requestDigest,resultJson,resultDigest}={}){
    return this.atomic(()=>{
      if(!validText(id,100)||!validText(claimId,100)||
        !digestPattern.test(requestDigest??'')||!digestPattern.test(resultDigest??'')||
        typeof resultJson!=='string')fail('invalid_result');
      const size=bytes.encode(resultJson).length;
      if(size>this.limits.maxResultBytes)fail('payload_too_large',413);
      const op=this.first('SELECT * FROM rdc2_ops WHERE id=?',id) ??
        this.first('SELECT * FROM rdc2_tombstones WHERE id=?',id);
      if(!op)fail('operation_not_found',404);
      if(op.claim_id!==claimId||op.request_digest!==requestDigest)fail('claim_mismatch',409);
      if(op.state==='completed'){
        if(op.result_digest!==resultDigest)fail('result_conflict',409);
        return {id,state:'completed',duplicate:true};
      }
      if(!['claimed','unknown'].includes(op.state))fail('operation_not_claimed',409);
      let result;
      try{result=JSON.parse(resultJson)}
      catch{fail('invalid_result')}
      if(result===null||typeof result!=='object'||Array.isArray(result)||
        !Array.isArray(result.content)||result.content.length>1000||
        (result.isError!==undefined&&typeof result.isError!=='boolean'))
        fail('invalid_result');
      const now=this.now();
      this.sql.exec("UPDATE rdc2_ops SET state='completed',completed_ms=?,"+
        'result_json=?,result_digest=?,result_size=?,result_expires_ms=?,'+
        "request_json=NULL,request_size=0 WHERE id=? AND claim_id=? AND state IN ('claimed','unknown')",
        now,resultJson,resultDigest,size,now+this.limits.resultTtlMs,id,claimId);
      return {id,state:'completed',duplicate:false};
    });
  }
  recover(principal,id){
    this.assertOwner(principal);
    if(!validText(id,100))fail('invalid_request');
    const op=this.first('SELECT * FROM rdc2_ops WHERE id=? AND principal=?',id,principal);
    if(!op){
      const original=this.first('SELECT state FROM rdc2_tombstones WHERE id=? AND principal=?',id,principal);
      if(!original)fail('operation_not_found',404);
      return {id,state:original.state==='completed'?'result_expired':original.state};
    }
    const now=this.now();
    const state=op.state==='queued'&&op.expires_ms<=now?'expired':
      op.state==='claimed'&&op.claimed_ms<=now-this.limits.unknownMs?'unknown':op.state;
    if(state==='completed'){
      if(op.result_expires_ms<=now||(op.result_json===null&&op.result_key===null))
        return {id,state:'result_expired'};
      if(op.result_key!==null)
        return {id,state,resultKey:op.result_key,resultDigest:op.result_digest,
          resultSize:op.result_size};
      return {id,state,resultJson:op.result_json};
    }
    return {id,state};
  }
  preflightExternalCompletion({id,claimId,requestDigest,resultDigest}={}){
    if(!validText(id,100)||!validText(claimId,100)||
      !digestPattern.test(requestDigest??'')||!digestPattern.test(resultDigest??''))
      fail('invalid_result');
    const op=this.first('SELECT claim_id,request_digest,result_digest,state FROM rdc2_ops WHERE id=?',id) ??
      this.first('SELECT claim_id,request_digest,result_digest,state FROM rdc2_tombstones WHERE id=?',id);
    if(!op)fail('operation_not_found',404);
    if(op.claim_id!==claimId||op.request_digest!==requestDigest)
      fail('claim_mismatch',409);
    if(op.state==='completed'){
      if(op.result_digest!==resultDigest)fail('result_conflict',409);
      return {id,state:'completed',duplicate:true};
    }
    if(!['claimed','unknown'].includes(op.state))fail('operation_not_claimed',409);
    return {id,state:op.state,duplicate:false};
  }
  completeExternal({id,claimId,requestDigest,resultDigest,resultSize,resultKey}={}){
    return this.atomic(()=>{
      const status=this.preflightExternalCompletion({id,claimId,requestDigest,resultDigest});
      if(status.duplicate)return status;
      if(!Number.isInteger(resultSize)||resultSize<=this.limits.maxResultBytes||
        resultSize>this.limits.maxBulkResultBytes)
        fail('payload_too_large',413);
      const expected='rdc2-results/'+id+'/'+resultDigest+'.json';
      if(resultKey!==expected)fail('invalid_result_key',409);
      const now=this.now();
      this.sql.exec("UPDATE rdc2_ops SET state='completed',completed_ms=?,"+
        'result_json=NULL,result_key=?,result_digest=?,result_size=?,result_expires_ms=?,'+
        "request_json=NULL,request_size=0 WHERE id=? AND claim_id=? AND state IN ('claimed','unknown')",
        now,resultKey,resultDigest,resultSize,now+this.limits.resultTtlMs,id,claimId);
      return {id,state:'completed',duplicate:false};
    });
  }
  expiredExternal(limit=16){
    if(!Number.isInteger(limit)||limit<1||limit>64)fail('invalid_limit');
    return this.rows("SELECT id,result_key FROM rdc2_ops WHERE state='completed' "+
      "AND result_key IS NOT NULL AND result_expires_ms<=? ORDER BY completed_ms LIMIT ?",
      this.now(),limit).map(row=>({id:row.id,resultKey:row.result_key}));
  }
  clearExpiredExternal(id,key){
    this.sql.exec("UPDATE rdc2_ops SET result_key=NULL,result_size=0 "+
      "WHERE id=? AND result_key=? AND state='completed' AND result_expires_ms<=?",
      id,key,this.now());
  }
  archiveRetired(limit=256){
    if(!Number.isInteger(limit)||limit<1||limit>512)fail('invalid_limit');
    // Both insertion and hot-row retirement must commit atomically. Never
    // compact unknown/claimed operations or unexpired data, and never remove
    // an R2 pointer before its original object is durably retired.
    return this.atomic(()=>{
      const rows=this.rows("SELECT * FROM rdc2_ops WHERE "+
        "(state='expired' AND request_json IS NULL) OR "+
        "(state='completed' AND result_expires_ms<=? AND result_json IS NULL AND result_key IS NULL) "+
        'ORDER BY seq LIMIT ?',this.now(),limit);
      for(const op of rows){
        this.sql.exec('INSERT INTO rdc2_tombstones '+
          '(id,principal,request_key,request_digest,tool,mutating,state,claim_id,result_digest) '+
          'VALUES (?,?,?,?,?,?,?,?,?)',
          op.id,op.principal,op.request_key,op.request_digest,op.tool,op.mutating,
          op.state,op.claim_id,op.result_digest);
        this.sql.exec('DELETE FROM rdc2_ops WHERE id=?',op.id);
      }
      return rows.length;
    });
  }
  sweep(){
    return this.atomic(()=>{
      const now=this.now();
      this.sql.exec("UPDATE rdc2_ops SET state='expired',request_json=NULL,request_size=0 "+
        "WHERE state='queued' AND expires_ms<=?",now);
      this.sql.exec("UPDATE rdc2_ops SET state='unknown',request_json=NULL,request_size=0 "+
        "WHERE state='claimed' AND claimed_ms<=?",now-this.limits.unknownMs);
      this.sql.exec("UPDATE rdc2_ops SET result_json=NULL,result_size=0 "+
        "WHERE state='completed' AND result_expires_ms<=? AND result_json IS NOT NULL",now);
    });
  }
}
