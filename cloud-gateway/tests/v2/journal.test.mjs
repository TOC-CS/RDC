import test from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { createHash } from 'node:crypto';
import { RDC2Journal } from '../../lib/v2/rdc2-journal.mjs';

const digest = value=>createHash('sha256').update(value).digest('hex');
const uuid='00000000-0000-4000-8000-000000000001';
function source(){
  const db=new DatabaseSync(':memory:');
  const storage={
    sql:{exec(query,...bind){
      let rows=[];
      if(/^\s*(SELECT|WITH|PRAGMA)\b|\bRETURNING\b/i.test(query)){
        rows=db.prepare(query).all(...bind);
      } else if(/^\s*CREATE\b/i.test(query)){db.exec(query)}
      else {db.prepare(query).run(...bind)}
      return {toArray:()=>rows};
    }},
    transactionSync(fn){
      db.exec('BEGIN');
      try{const result=fn();db.exec('COMMIT');return result}
      catch(error){db.exec('ROLLBACK');throw error}
    }
  };
  return {db,storage};
}
function rig(options={}){
  const {db,storage}=source();
  let clock=1700000000000;
  const journal=new RDC2Journal(storage,{now:()=>clock,queueTtlMs:30000,
    unknownMs:120000,resultTtlMs:60000,maxQueue:4,maxRecords:50,...options});
  const heartbeat=()=>journal.heartbeat();
  const bootstrap=()=>journal.bindOwner('TOC-owner',{bootstrap:true});
  const req=(key,tool='rdc_job_run',mutating=true)=>{
    const json=JSON.stringify({name:tool,arguments:{value:key}});
    return {principal:'TOC-owner',requestKey:key,requestDigest:digest(json),
      requestJson:json,tool,mutating};
  };
  return {db,storage,journal,heartbeat,bootstrap,req,advance:ms=>{clock+=ms},now:()=>clock};
}
function expectCode(fn,code){assert.throws(fn,e=>e?.code===code)}

test('V2 private owner binding requires explicit bootstrap and survives process restart',()=>{
  const s=rig();
  expectCode(()=>s.journal.bindOwner('TOC-owner'), 'owner_not_bound');
  s.bootstrap();
  assert.equal(s.journal.bindOwner('TOC-owner'), 'TOC-owner');
  expectCode(()=>s.journal.bindOwner('intruder',{bootstrap:true}),'owner_forbidden');
  const restarted=new RDC2Journal(s.storage,{now:s.now});
  assert.equal(restarted.bindOwner('TOC-owner'),'TOC-owner');
  expectCode(()=>restarted.bindOwner('intruder'),'owner_forbidden');
});
test('V2 status knows offline, online, and stale heartbeat without device state leaks',()=>{
  const s=rig({onlineMs:35000});
  s.bootstrap();
  assert.deepEqual(s.journal.status('TOC-owner').online,false);
  s.heartbeat();
  assert.equal(s.journal.status('TOC-owner').online,true);
  s.advance(35001);
  assert.equal(s.journal.status('TOC-owner').online,false);
  expectCode(()=>s.journal.status('other-owner'),'owner_forbidden');
});
test('V2 admits first original mutation once and recovers duplicate idempotently',()=>{
  const s=rig();s.bootstrap();s.heartbeat();
  const original=s.journal.enqueue(s.req('original-1'));
  assert.equal(original.reused,false);
  assert.equal(original.state,'queued');
  const again=s.journal.enqueue(s.req('original-1'));
  assert.equal(again.id,original.id);
  assert.equal(again.reused,true);
  assert.equal(s.journal.status('TOC-owner').pending,1);
});
test('V2 same key with different content fails without new operation',()=>{
  const s=rig();s.bootstrap();s.heartbeat();
  s.journal.enqueue(s.req('key-a'));
  const altered={...s.req('key-a'),requestJson:'{"name":"rdc_file_write","arguments":{"value":"altered"}}'};
  altered.requestDigest=digest(altered.requestJson);
  expectCode(()=>s.journal.enqueue(altered),'request_id_conflict');
  assert.equal(s.journal.status('TOC-owner').pending,1);
});
test('V2 rejects missing owner, malformed digest, empty key and unauthorized principal',()=>{
  const s=rig();s.bootstrap();s.heartbeat();
  expectCode(()=>s.journal.enqueue({...s.req('a'),principal:'other'}),'owner_forbidden');
  expectCode(()=>s.journal.enqueue({...s.req('a'),requestDigest:'wrong'}),'invalid_request');
  expectCode(()=>s.journal.enqueue({...s.req('a'),requestKey:''}),'invalid_request');
  assert.equal(s.journal.status('TOC-owner').pending,0);
});
test('V2 requires online device for new dispatch but preserves duplicate recovery when offline',()=>{
  const s=rig();s.bootstrap();
  expectCode(()=>s.journal.enqueue(s.req('offline')),'device_offline');
  s.heartbeat();const initial=s.journal.enqueue(s.req('offline'));
  s.advance(36000);
  assert.equal(s.journal.enqueue(s.req('offline')).id,initial.id);
  expectCode(()=>s.journal.enqueue(s.req('fresh')),'device_offline');
});
test('V2 durable ordered claim grants each operation exactly one distinct claim identity',()=>{
  const s=rig();s.bootstrap();s.heartbeat();
  const a=s.journal.enqueue(s.req('a'));
  const b=s.journal.enqueue(s.req('b'));
  const first=s.journal.claim();const second=s.journal.claim();
  assert.equal(first.id,a.id);assert.equal(second.id,b.id);
  assert.notEqual(first.claimId,second.claimId);
  assert.equal(s.journal.claim(),null);
  assert.equal(s.journal.status('TOC-owner').pending,2);
});
test('V2 forged claim or wrong request hash cannot complete original mutation',()=>{
  const s=rig();s.bootstrap();s.heartbeat();
  const input=s.journal.enqueue(s.req('protected'));const op=s.journal.claim();
  const resultJson='{"content":[{"type":"text","text":"done"}]}';
  const data={id:input.id,claimId:op.claimId,requestDigest:op.requestDigest,
    resultJson,resultDigest:digest(resultJson)};
  expectCode(()=>s.journal.complete({...data,claimId:uuid}),'claim_mismatch');
  expectCode(()=>s.journal.complete({...data,requestDigest:digest('wrong')}),'claim_mismatch');
  assert.equal(s.journal.recover('TOC-owner',input.id).state,'claimed');
  assert.equal(s.journal.complete(data).state,'completed');
  assert.equal(s.journal.recover('TOC-owner',input.id).resultJson,resultJson);
});
test('V2 lost completion ACK recovers original result; identical duplicate is accepted once',()=>{
  const s=rig();s.bootstrap();s.heartbeat();
  s.journal.enqueue(s.req('lost-ack'));const op=s.journal.claim();
  const resultJson='{"content":[{"type":"text","text":"exact"}]}';
  const data={id:op.id,claimId:op.claimId,requestDigest:op.requestDigest,
    resultJson,resultDigest:digest(resultJson)};
  assert.equal(s.journal.complete(data).duplicate,false);
  assert.equal(s.journal.complete(data).duplicate,true);
  assert.equal(s.journal.recover('TOC-owner',op.id).resultJson,resultJson);
  expectCode(()=>s.journal.complete({...data,resultJson:'{"different":true}',
    resultDigest:digest('{"different":true}')}),'result_conflict');
});
test('V2 process restart never reclaims an in-flight mutation',()=>{
  const s=rig();s.bootstrap();s.heartbeat();
  s.journal.enqueue(s.req('once'));const op=s.journal.claim();
  const restored=new RDC2Journal(s.storage,{now:s.now});
  assert.equal(restored.claim(),null);
  assert.equal(restored.recover('TOC-owner',op.id).state,'claimed');
  s.advance(120001);restored.sweep();
  assert.equal(restored.claim(),null);
  assert.equal(restored.recover('TOC-owner',op.id).state,'unknown');
});
test('V2 original late result may finish unknown state without replay',()=>{
  const s=rig();s.bootstrap();s.heartbeat();
  s.journal.enqueue(s.req('late'));const op=s.journal.claim();
  s.advance(120001);s.journal.sweep();
  const json='{"content":[],"isError":false}';
  assert.equal(s.journal.complete({id:op.id,claimId:op.claimId,
    requestDigest:op.requestDigest,resultJson:json,resultDigest:digest(json)}).state,'completed');
  assert.equal(s.journal.claim(),null);
});
test('V2 expires queued operations and never executes late work',()=>{
  const s=rig();s.bootstrap();s.heartbeat();const initial=s.journal.enqueue(s.req('expired'));
  s.advance(30001);
  assert.equal(s.journal.claim(),null);
  s.journal.sweep();
  assert.equal(s.journal.recover('TOC-owner',initial.id).state,'expired');
});
test('V2 queue saturation rejects surplus work but never silently removes protected mutation',()=>{
  const s=rig({maxQueue:2});s.bootstrap();s.heartbeat();
  const first=s.journal.enqueue(s.req('first'));
  s.journal.enqueue(s.req('second'));
  expectCode(()=>s.journal.enqueue(s.req('third')),'queue_full');
  assert.equal(s.journal.enqueue(s.req('first')).id,first.id);
});
test('V2 recorded result expiry stops exposure but preserves mutation tombstone',()=>{
  const s=rig();s.bootstrap();s.heartbeat();s.journal.enqueue(s.req('result'));
  const op=s.journal.claim(), json='{"content":[],"isError":false}';
  s.journal.complete({id:op.id,claimId:op.claimId,
    requestDigest:op.requestDigest,resultJson:json,resultDigest:digest(json)});
  s.advance(60001);
  assert.equal(s.journal.recover('TOC-owner',op.id).state,'result_expired');
  assert.equal(s.journal.enqueue(s.req('result')).id,op.id);
});
test('V2 bounds request and response payloads without persisting overflow',()=>{
  const s=rig({maxRequestBytes:64,maxResultBytes:64});s.bootstrap();s.heartbeat();
  const big=JSON.stringify({name:'a',arguments:{value:'x'.repeat(300)}});
  expectCode(()=>s.journal.enqueue({...s.req('big'),requestJson:big,requestDigest:digest(big)}),'payload_too_large');
  s.journal.enqueue(s.req('small','t',false));const op=s.journal.claim();
  const resultJson='{"content":[{"text":"'+ 'x'.repeat(200)+'"}]}';
  expectCode(()=>s.journal.complete({id:op.id,claimId:op.claimId,requestDigest:op.requestDigest,
    resultJson,resultDigest:digest(resultJson)}),'payload_too_large');
  assert.equal(s.journal.recover('TOC-owner',op.id).state,'claimed');
});
test('V2 journal rejects altered tool identity or nonobject request with no admission',()=>{
  const s=rig();s.bootstrap();s.heartbeat();
  const array='[]';
  expectCode(()=>s.journal.enqueue({...s.req('invalid'),requestJson:array,
    requestDigest:digest(array)}),'invalid_request');
  const impostor=JSON.stringify({name:'rdc_file_read',arguments:{}});
  expectCode(()=>s.journal.enqueue({...s.req('mismatch'),requestJson:impostor,
    requestDigest:digest(impostor)}),'invalid_request');
  assert.equal(s.journal.status('TOC-owner').pending,0);
});
test('V2 journal rejects invalid MCP result envelope before committing and permits original valid upload',()=>{
  const s=rig();s.bootstrap();s.heartbeat();s.journal.enqueue(s.req('mcp-envelope'));
  const claimed=s.journal.claim();
  for(const invalid of ['[]','{}','{"content":"invalid"}','{"content":[],"isError":"yes"}']){
    expectCode(()=>s.journal.complete({id:claimed.id,claimId:claimed.claimId,
      requestDigest:claimed.requestDigest,resultJson:invalid,resultDigest:digest(invalid)}),
      'invalid_result');
    assert.equal(s.journal.recover('TOC-owner',claimed.id).state,'claimed');
  }
  const valid='{"content":[{"type":"text","text":"complete"}],"isError":false}';
  assert.equal(s.journal.complete({id:claimed.id,claimId:claimed.claimId,
    requestDigest:claimed.requestDigest,resultJson:valid,resultDigest:digest(valid)}).state,
    'completed');
});
test('V2 schema migration adds private bulk pointer to older v2 SQLite without losing original result',()=>{
  const s=source();
  s.db.exec("CREATE TABLE rdc2_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);"+
    "CREATE TABLE rdc2_ops("+
      "seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT NOT NULL UNIQUE,"+
      "principal TEXT NOT NULL,request_key TEXT NOT NULL,request_digest TEXT NOT NULL,"+
      "request_json TEXT,request_size INTEGER NOT NULL,tool TEXT NOT NULL,"+
      "mutating INTEGER NOT NULL,state TEXT NOT NULL,"+
      "created_ms INTEGER NOT NULL,expires_ms INTEGER NOT NULL,"+
      "claim_id TEXT,claimed_ms INTEGER,result_json TEXT,result_digest TEXT,"+
      "result_size INTEGER NOT NULL DEFAULT 0,completed_ms INTEGER,result_expires_ms INTEGER,"+
      "UNIQUE(principal,request_key));"+
    "CREATE INDEX rdc2_queue_idx ON rdc2_ops(state,seq);");
  const sourcePayload=JSON.stringify({name:'rdc_job_run',arguments:{value:'migrate'}});
  const resultPayload=JSON.stringify({content:[{type:'text',text:'ORIGINAL_RESULT'}]});
  const now=1700000000000;
  s.db.prepare("INSERT INTO rdc2_meta(key,value) VALUES ('owner',?)").run('TOC-owner');
  s.db.prepare("INSERT INTO rdc2_ops (id,principal,request_key,request_digest,"+
    "request_json,request_size,tool,mutating,state,created_ms,expires_ms,"+
    "claim_id,claimed_ms,result_json,result_digest,result_size,completed_ms,result_expires_ms)"+
    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)").run(
    'older-original','TOC-owner','preserved',digest(sourcePayload),null,0,
    'rdc_job_run',1,'completed',now-500,now+30000,'older-claim',now-490,
    resultPayload,digest(resultPayload),Buffer.byteLength(resultPayload),now-480,now+60000);
  const journal=new RDC2Journal(s.storage,{now:()=>now});
  assert.equal(s.db.prepare("SELECT COUNT(*) AS n FROM pragma_table_info('rdc2_ops') WHERE name='result_key'").get().n,1);
  const old=journal.recover('TOC-owner','older-original');
  assert.equal(old.state,'completed');
  assert.equal(old.resultJson,resultPayload);
  assert.equal(s.db.prepare('SELECT result_key FROM rdc2_ops WHERE id=?').get('older-original').result_key,null);
  const reboot=new RDC2Journal(s.storage,{now:()=>now});
  assert.equal(reboot.recover('TOC-owner','older-original').resultJson,resultPayload);
});

test('V2 owner metrics derive queue and execution phases from durable original rows',()=>{
  const s=rig();s.bootstrap();s.heartbeat();
  const original=s.journal.enqueue(s.req('timed-original'));
  s.advance(37);
  const claim=s.journal.claim();
  s.advance(92);
  const resultJson='{"content":[{"type":"text","text":"correct"}]}';
  s.journal.complete({id:claim.id,claimId:claim.claimId,
    requestDigest:claim.requestDigest,resultJson,resultDigest:digest(resultJson)});
  const report=s.journal.phaseMetrics('TOC-owner',30);
  assert.equal(report.source,'rdc2-durable-journal');
  assert.equal(report.sampleCount,1);
  assert.deepEqual(report.samples.map(row=>[row.operationId,row.queuePickupMs,row.claimToResultMs]),[
    [original.id,37,92]]);
  assert.equal(JSON.stringify(report).includes('timed-original'),false);
  assert.equal(JSON.stringify(report).includes('requestJson'),false);
  assert.equal(JSON.stringify(report).includes('correct'),false);
  s.advance(40);
  assert.equal(s.journal.complete({id:claim.id,claimId:claim.claimId,
    requestDigest:claim.requestDigest,resultJson,resultDigest:digest(resultJson)}).duplicate,true);
  assert.equal(s.journal.phaseMetrics('TOC-owner',30).sampleCount,1);
  // A backwards OS clock adjustment must never create a zero-latency
  // success sample or falsely mark a stale future heartbeat as online.
  s.advance(1);s.heartbeat();
  const reversed=s.journal.enqueue(s.req('backwards-clock'));
  s.advance(5);
  const reversedClaim=s.journal.claim();
  assert.equal(reversedClaim.id,reversed.id);
  s.advance(-25);
  assert.equal(s.journal.online(),false,'future heartbeat must not imply online');
  s.journal.complete({id:reversedClaim.id,claimId:reversedClaim.claimId,
    requestDigest:reversedClaim.requestDigest,resultJson,
    resultDigest:digest(resultJson)});
  const afterClockChange=s.journal.phaseMetrics('TOC-owner',30);
  assert.equal(afterClockChange.sampleCount,2);
  assert.equal(afterClockChange.validSampleCount,1);
  assert.equal(afterClockChange.invalidSampleCount,1);
  const invalid=afterClockChange.samples.find(row=>row.operationId===reversed.id);
  assert.equal(invalid.timingStatus,'invalid_clock_order');
  assert.equal(invalid.queuePickupMs,null);
  assert.equal(invalid.claimToResultMs,null);
  assert.equal(afterClockChange.samples.find(row=>row.operationId===original.id)
    .timingStatus,'valid');
});
test('V2 owner-only phase telemetry refuses invalid limits and other principals',()=>{
  const s=rig();s.bootstrap();
  assert.throws(()=>s.journal.phaseMetrics('intruder',30),e=>e.code==='owner_forbidden');
  for(const limit of [0,101,-1,3.5,null,'30',true]){
    assert.throws(()=>s.journal.phaseMetrics('TOC-owner',limit),e=>e.code==='invalid_limit');
  }
});
