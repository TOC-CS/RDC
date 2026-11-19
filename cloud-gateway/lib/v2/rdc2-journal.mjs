/**
 * RDC 2.0 private per-device Durable Object journal.
 * One colocated SQLite database. Original operation identity is authoritative.
 * No D1 polling, retries of uncertain mutations, or v1 schema access.
 */
const DEFAULTS=Object.freeze({
  queueTtlMs:30_000,unknownMs:120_000,resultTtlMs:3_600_000,
  onlineMs:35_000,maxQueue:64,maxRecords:10_000,
  maxRequestBytes:1_048_576,maxResultBytes:262_144
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
      'claim_id TEXT, claimed_ms INTEGER, result_json TEXT, result_digest TEXT,'+
      'result_size INTEGER NOT NULL DEFAULT 0, completed_ms INTEGER, result_expires_ms INTEGER,'+
      'UNIQUE(principal,request_key))');
    this.sql.exec('CREATE INDEX IF NOT EXISTS rdc2_queue_idx ON rdc2_ops(state,seq)');
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
    return this.atomic(()=>{
      const owner=this.owner();
      if(owner!==null){
        if(owner!==principal)fail('owner_forbidden',403);
        return owner;
      }
      if(bootstrap!==true)fail('owner_not_bound',503);
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
    return last!==null&&time-last<=this.limits.onlineMs;
  }
  status(principal){
    this.assertOwner(principal);
    const now=this.now();
    const count=this.first("SELECT COUNT(*) AS count FROM rdc2_ops WHERE "+
      "(state='queued' AND expires_ms>?) OR (state='claimed' AND claimed_ms>?)",
      now,now-this.limits.unknownMs);
    return {online:this.online(now),lastSeenMs:this.lastSeen(),pending:Number(count?.count??0)};
  }
  enqueue({principal,requestKey,requestDigest,requestJson,tool,mutating=false}={}){
    return this.atomic(()=>{
      this.assertOwner(principal);
      if(!validText(requestKey,200)||!digestPattern.test(requestDigest??'')||
        typeof requestJson!=='string'||!validText(tool,128)||typeof mutating!=='boolean')
        fail('invalid_request');
      const size=bytes.encode(requestJson).length;
      if(size>this.limits.maxRequestBytes)fail('payload_too_large',413);
      const existing=this.first('SELECT * FROM rdc2_ops WHERE principal=? AND request_key=?',principal,requestKey);
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
      const op=this.first('SELECT * FROM rdc2_ops WHERE id=?',id);
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
    if(!op)fail('operation_not_found',404);
    const now=this.now();
    const state=op.state==='queued'&&op.expires_ms<=now?'expired':
      op.state==='claimed'&&op.claimed_ms<=now-this.limits.unknownMs?'unknown':op.state;
    if(state==='completed'){
      if(op.result_expires_ms<=now||op.result_json===null)return {id,state:'result_expired'};
      return {id,state,resultJson:op.result_json};
    }
    return {id,state};
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
