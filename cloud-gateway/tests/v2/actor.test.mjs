import test from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { createHash } from 'node:crypto';
import { RDC2DeviceActor } from '../../lib/v2/rdc2-actor.mjs';

const KEY='a-local-fixture-key-that-is-never-used-outside-unit-tests-2026';
const digest=data=>createHash('sha256').update(data).digest('hex');
function fixture(){
  const db=new DatabaseSync(':memory:');
  const storage={
    sql:{exec(query,...args){
      const rows=/^\s*(SELECT|PRAGMA|WITH)\b|\bRETURNING\b/i.test(query)?
        db.prepare(query).all(...args):
        /^\s*CREATE/i.test(query)?(db.exec(query),[]):(db.prepare(query).run(...args),[]);
      return {toArray:()=>rows};
    }},
    transactionSync(fn){
      db.exec('BEGIN');
      try{const out=fn();db.exec('COMMIT');return out}
      catch(e){db.exec('ROLLBACK');throw e}
    }
  };
  let now=1700000000000;
  const sockets=[];
  const ctx={storage,getWebSockets(){return sockets}};
  const files=new Map();
  const bucket={
    puts:0,deletes:0,gets:0,
    async put(key,value){this.puts++;files.set(key,String(value));return {key}},
    async get(key){this.gets++;const text=files.get(key);return text===undefined?
      null:{text:async()=>text}},
    async delete(key){this.deletes++;files.delete(key)}
  };
  const env={RDC2_INTERNAL_KEY:KEY,RDC2_OWNER_BOOTSTRAP:'private-site',
    BUCKET:bucket};
  const actor=new RDC2DeviceActor(ctx,env,{now:()=>now});
  const call=async(path,body={},key=KEY,extraHeaders={})=>{
    const req=new Request('https://private.internal'+path,{
      method:'POST',headers:{'Content-Type':'application/json',
        'X-RDC2-Internal-Key':key,...extraHeaders},body:JSON.stringify(body)});
    const response=await actor.fetch(req);
    return {status:response.status,body:await response.json()};
  };
  const req=(key)=>{
    const requestJson=JSON.stringify({name:'rdc_job_run',arguments:{value:key}});
    return {principal:'TOC-owner',requestKey:key,requestJson,
      requestDigest:digest(requestJson),tool:'rdc_job_run',mutating:true};
  };
  return {db,storage,sockets,ctx,env,actor,call,req,bucket,files,
    advance:ms=>{now+=ms},now:()=>now};
}
test('V2 internal actor rejects unauthenticated requests before disclosing owner or queue',async()=>{
  const s=fixture();
  const bad=await s.call('/v2/status',{principal:'TOC-owner'},'bad-key');
  assert.equal(bad.status,401);
  assert.equal(JSON.stringify(bad.body).includes('TOC-owner'),false);
  assert.equal((await s.call('/v2/status',{principal:'TOC-owner'},'')).status,401);
  assert.equal(s.db.prepare('SELECT count(*) AS count FROM rdc2_meta').get().count,0);
});
test('V2 actor enforces actual stored owner on device status, admission and recovery',async()=>{
  const s=fixture();
  assert.equal((await s.call('/v2/bind',{principal:'TOC-owner',bootstrap:true})).status,200);
  assert.equal((await s.call('/v2/heartbeat')).status,200);
  assert.equal((await s.call('/v2/status',{principal:'intruder'})).status,403);
  assert.equal((await s.call('/v2/admit',{...s.req('first'),principal:'intruder'})).status,403);
  const good=await s.call('/v2/admit',s.req('first'));
  assert.equal(good.status,200);
  assert.equal(good.body.state,'queued');
  assert.equal((await s.call('/v2/recover',{principal:'intruder',id:good.body.id})).status,403);
  assert.equal((await s.call('/v2/status',{principal:'TOC-owner'})).body.pending,1);
});
test('V2 actor refuses bootstrap unless private Site explicitly permits enrollment',async()=>{
  const s=fixture();delete s.env.RDC2_OWNER_BOOTSTRAP;
  assert.equal((await s.call('/v2/bind',{principal:'TOC-owner',bootstrap:true})).status,403);
  assert.equal((await s.call('/v2/status',{principal:'TOC-owner'})).status,503);
});
test('V2 actor rejects spoofed payload digest and wrong completion digest',async()=>{
  const s=fixture();
  await s.call('/v2/bind',{principal:'TOC-owner',bootstrap:true});
  await s.call('/v2/heartbeat');
  assert.equal((await s.call('/v2/admit',{...s.req('first'),requestDigest:digest('different')})).status,409);
  const ok=await s.call('/v2/admit',s.req('first'));
  const claimed=await s.call('/v2/claim');
  assert.equal(claimed.body.operation.id,ok.body.id);
  const resultJson='{"content":[{"type":"text","text":"ok"}]}';
  assert.equal((await s.call('/v2/complete',{id:ok.body.id,claimId:claimed.body.operation.claimId,
    requestDigest:claimed.body.operation.requestDigest,resultJson,
    resultDigest:digest('wrong-result')})).status,409);
  const saved=await s.call('/v2/complete',{id:ok.body.id,claimId:claimed.body.operation.claimId,
    requestDigest:claimed.body.operation.requestDigest,resultJson,resultDigest:digest(resultJson)});
  assert.equal(saved.status,200);
  assert.equal(saved.body.state,'completed');
  assert.equal((await s.call('/v2/recover',{principal:'TOC-owner',id:ok.body.id})).body.resultJson,resultJson);
});
test('V2 actor signals work availability over attached sockets without leaking request content',async()=>{
  const s=fixture();
  const observed=[];
  s.sockets.push({send:msg=>observed.push(JSON.parse(msg))});
  await s.call('/v2/bind',{principal:'TOC-owner',bootstrap:true});
  await s.call('/v2/heartbeat');
  const response=await s.call('/v2/admit',s.req('private-data-sentinel'));
  assert.equal(response.status,200);
  assert.deepEqual(observed,[{version:2,type:'work_available'}]);
  assert.equal(JSON.stringify(observed).includes('private-data-sentinel'),false);
  await s.call('/v2/admit',s.req('private-data-sentinel'));
  assert.equal(observed.length,1,'exact duplicate cannot send second wake');
});
test('V2 actor websocket claim and original result ACK survive reconnect and never repeat execution',async()=>{
  const s=fixture();
  await s.call('/v2/bind',{principal:'TOC-owner',bootstrap:true});
  await s.call('/v2/heartbeat');
  await s.call('/v2/admit',s.req('original'));
  const sent=[];
  const ws={send:msg=>sent.push(JSON.parse(msg))};
  s.sockets.push(ws);
  await s.actor.webSocketMessage(ws,JSON.stringify({version:2,type:'claim'}));
  assert.equal(sent[0].type,'claimed');
  const op=sent[0].operation;
  assert.equal(op.requestJson,s.req('original').requestJson);
  assert.equal(typeof op.serverTimeMs,'number','V2 device must provide original server time for safe deadline validation');
  const resultJson='{"content":[{"type":"text","text":"one"}]}';
  const done={version:2,type:'complete',id:op.id,claimId:op.claimId,
    requestDigest:op.requestDigest,resultJson,resultDigest:digest(resultJson)};
  await s.actor.webSocketMessage(ws,JSON.stringify(done));
  assert.equal(sent.at(-1).type,'result_ack');
  assert.equal(sent.at(-1).duplicate,false);
  await s.actor.webSocketMessage(ws,JSON.stringify(done));
  assert.equal(sent.at(-1).duplicate,true);
  const restarted=new RDC2DeviceActor(s.ctx,s.env,{now:s.now});
  assert.equal(restarted.journal.claim(),null);
  assert.equal(restarted.journal.recover('TOC-owner',op.id).state,'completed');
});
test('V2 actor malformed frame cannot run or alter operation and is bounded',async()=>{
  const s=fixture();
  await s.call('/v2/bind',{principal:'TOC-owner',bootstrap:true});
  await s.call('/v2/heartbeat');
  await s.call('/v2/admit',s.req('protected'));
  const sent=[];const ws={send:msg=>sent.push(JSON.parse(msg))};
  await s.actor.webSocketMessage(ws,'{not json');
  assert.equal(sent.at(-1).type,'protocol_error');
  await s.actor.webSocketMessage(ws,JSON.stringify({version:1,type:'claim'}));
  assert.equal(sent.at(-1).type,'protocol_error');
  assert.equal((await s.call('/v2/status',{principal:'TOC-owner'})).body.pending,1);
});
test('V2 admit-and-wait returns committed result using WebSocket wake without D1 polling',async()=>{
  const s=fixture();
  await s.call('/v2/bind',{principal:'TOC-owner',bootstrap:true});
  await s.call('/v2/heartbeat');
  let woke;
  const notified=new Promise(resolve=>{woke=resolve});
  s.sockets.push({send:raw=>{
    if(JSON.parse(raw).type==='work_available')woke();
  }});
  const pending=s.call('/v2/admit_wait',{...s.req('wait-for-original'),waitMs:750});
  await Promise.race([notified,new Promise((_,reject)=>setTimeout(()=>reject(new Error('expected V2 work wake')),100))]);
  const claimed=await s.call('/v2/claim',{});
  assert.equal(claimed.status,200);
  const op=claimed.body.operation;
  assert.equal(op.requestJson,s.req('wait-for-original').requestJson);
  const resultJson='{"content":[{"type":"text","text":"event-driven"}]}';
  const finished=await s.call('/v2/complete',{id:op.id,claimId:op.claimId,
    requestDigest:op.requestDigest,resultJson,resultDigest:digest(resultJson)});
  assert.equal(finished.status,200);
  const response=await pending;
  assert.equal(response.status,200);
  assert.equal(response.body.state,'completed');
  assert.equal(response.body.resultJson,resultJson);
  assert.equal(response.body.id,op.id);
});
test('V2 bounded wait returns pending original ID without redispatch',async()=>{
  const s=fixture();
  await s.call('/v2/bind',{principal:'TOC-owner',bootstrap:true});
  await s.call('/v2/heartbeat');
  const input=s.req('slow-worker');
  const result=await s.call('/v2/admit_wait',{...input,waitMs:15});
  assert.equal(result.status,200);
  assert.equal(result.body.state,'queued');
  const same=await s.call('/v2/admit',input);
  assert.equal(same.body.id,result.body.id);
  assert.equal(same.body.reused,true);
  assert.equal((await s.call('/v2/status',{principal:'TOC-owner'})).body.pending,1);
  assert.equal((await s.call('/v2/admit_wait',{...s.req('invalid-wait'),waitMs:999999})).status,400);
});
test('V2 first private owner operation binds within its own actor request',async()=>{
  const s=fixture();
  await s.call('/v2/heartbeat',{});
  const sent=await s.call('/v2/admit',s.req('first-ever-call'));
  assert.equal(sent.status,200);
  assert.equal(sent.body.state,'queued');
  assert.equal(s.db.prepare("SELECT value FROM rdc2_meta WHERE key='owner'").get().value,'TOC-owner');
  assert.equal((await s.call('/v2/status',{principal:'other-owner'})).status,403);
});
test('V2 large result uses private R2, exact original identity and durable recovery',async()=>{
  const s=fixture();
  await s.call('/v2/heartbeat');
  const admitted=await s.call('/v2/admit',s.req('bulk-output'));
  const claim=(await s.call('/v2/claim')).body.operation;
  assert.equal(claim.id,admitted.body.id);
  const resultJson=JSON.stringify({content:[{type:'text',text:'V'.repeat(420000)}],
    structuredContent:{ok:true,kind:'large-original'}});
  const args={id:claim.id,claimId:claim.claimId,requestDigest:claim.requestDigest,
    resultJson,resultDigest:digest(resultJson)};
  const completed=await s.call('/v2/complete_bulk',args);
  assert.equal(completed.status,200);
  assert.equal(completed.body.state,'completed');
  assert.equal(completed.body.duplicate,false);
  assert.equal(s.bucket.puts,1);
  assert.equal(s.files.size,1);
  assert.equal(s.db.prepare('SELECT result_json FROM rdc2_ops WHERE id=?').get(claim.id).result_json,null,
    'large result bytes must not occupy a Durable Object SQL row');
  const recovered=await s.call('/v2/recover',{principal:'TOC-owner',id:claim.id});
  assert.equal(recovered.status,200);
  assert.equal(recovered.body.resultJson,resultJson);
  const retry=await s.call('/v2/complete_bulk',args);
  assert.equal(retry.status,200);
  assert.equal(retry.body.duplicate,true);
  assert.equal(s.bucket.puts,1,'same original completion must not trigger second R2 write');
});

test('V2 forged bulk claim is rejected before any R2 storage write',async()=>{
  const s=fixture();
  await s.call('/v2/heartbeat');
  await s.call('/v2/admit',s.req('not-forged'));
  const claim=(await s.call('/v2/claim')).body.operation;
  const resultJson=JSON.stringify({content:[{type:'text',text:'A'.repeat(400000)}]});
  const base={id:claim.id,claimId:claim.claimId,
    requestDigest:claim.requestDigest,resultJson,resultDigest:digest(resultJson)};
  const denied=await s.call('/v2/complete_bulk',{...base,claimId:'forged-claim'});
  assert.equal(denied.status,409);
  assert.equal(s.bucket.puts,0);
  assert.equal((await s.call('/v2/recover',{principal:'TOC-owner',id:claim.id})).body.state,'claimed');
  const mismatched=await s.call('/v2/complete_bulk',{...base,resultDigest:digest('different')});
  assert.equal(mismatched.status,409);
  assert.equal(s.bucket.puts,0);
  const forbidden=await s.call('/v2/complete_bulk',base,'wrong-private-internal-key');
  assert.equal(forbidden.status,401);
  assert.equal(s.bucket.puts,0);
});

test('V2 missing private R2 binding fails closed, preserving original claimed result',async()=>{
  const s=fixture();delete s.env.BUCKET;
  await s.call('/v2/heartbeat');
  await s.call('/v2/admit',s.req('missing-r2'));
  const claim=(await s.call('/v2/claim')).body.operation;
  const resultJson=JSON.stringify({content:[{type:'text',text:'B'.repeat(350000)}]});
  const result=await s.call('/v2/complete_bulk',{
    id:claim.id,claimId:claim.claimId,
    requestDigest:claim.requestDigest,resultJson,resultDigest:digest(resultJson)});
  assert.equal(result.status,503);
  assert.equal((await s.call('/v2/recover',{principal:'TOC-owner',id:claim.id})).body.state,'claimed');
});

test('V2 bulk recovery fails closed when private R2 object is missing',async()=>{
  const s=fixture();await s.call('/v2/heartbeat');
  await s.call('/v2/admit',s.req('missing-object'));
  const claim=(await s.call('/v2/claim')).body.operation;
  const resultJson=JSON.stringify({content:[{type:'text',text:'C'.repeat(390000)}]});
  const args={id:claim.id,claimId:claim.claimId,
    requestDigest:claim.requestDigest,resultJson,resultDigest:digest(resultJson)};
  assert.equal((await s.call('/v2/complete_bulk',args)).status,200);
  s.files.clear();
  const result=await s.call('/v2/recover',{principal:'TOC-owner',id:claim.id});
  assert.equal(result.status,503);
  assert.equal(result.body.error.code,'result_unavailable');
  assert.equal(s.db.prepare('SELECT state FROM rdc2_ops WHERE id=?').get(claim.id).state,'completed',
    'missing bytes must not cause redispatch');
});

test('V2 bulk result expiry retires only expired original R2 bytes',async()=>{
  const s=fixture();await s.call('/v2/heartbeat');
  for(const key of ['earlier','later']){
    // A long synthetic time jump requires an authentic device heartbeat.
    await s.call('/v2/heartbeat');
    await s.call('/v2/admit',s.req(key));
    const claim=(await s.call('/v2/claim')).body.operation;
    const resultJson=JSON.stringify({content:[{type:'text',text:key.repeat(100000)}]});
    assert.equal((await s.call('/v2/complete_bulk',{
      id:claim.id,claimId:claim.claimId,
      requestDigest:claim.requestDigest,resultJson,resultDigest:digest(resultJson)})).status,200);
    if(key==='earlier')s.advance(3_500_000);
  }
  assert.equal(s.files.size,2);
  s.advance(100_001);
  const cleaned=await s.call('/v2/sweep',{});
  assert.equal(cleaned.status,200);
  assert.equal(s.files.size,1);
  assert.equal(s.bucket.deletes,1);
  const earlier=s.db.prepare("SELECT id FROM rdc2_ops WHERE request_key='earlier'").get().id;
  const later=s.db.prepare("SELECT id FROM rdc2_ops WHERE request_key='later'").get().id;
  assert.equal((await s.call('/v2/recover',{principal:'TOC-owner',id:earlier})).body.state,'result_expired');
  assert.equal((await s.call('/v2/recover',{principal:'TOC-owner',id:later})).body.state,'completed');
});
test('V2 16 concurrent duplicate bulk completions share one private R2 write',async()=>{
  const s=fixture();
  await s.call('/v2/heartbeat');
  await s.call('/v2/admit',s.req('burst-bulk'));
  const op=(await s.call('/v2/claim')).body.operation;
  const resultJson=JSON.stringify({content:[{type:'text',text:'X'.repeat(450000)}]});
  const input={id:op.id,claimId:op.claimId,requestDigest:op.requestDigest,
    resultDigest:digest(resultJson),resultJson};
  const responses=await Promise.all(Array.from({length:16},
    ()=>s.call('/v2/complete_bulk',input)));
  assert.ok(responses.every(r=>r.status===200));
  assert.equal(responses.filter(r=>r.body.duplicate===false).length,1);
  assert.equal(responses.filter(r=>r.body.duplicate===true).length,15);
  assert.equal(s.bucket.puts,1,'duplicate completions must not generate 16 redundant private R2 writes');
  assert.equal((await s.call('/v2/recover',{principal:'TOC-owner',id:op.id})).body.resultJson,resultJson);
});
