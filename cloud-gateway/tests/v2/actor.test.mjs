import test from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { createHash } from 'node:crypto';
import { RDC2DeviceActor } from '../../lib/v2/rdc2-actor.mjs';

const KEY='a-local-fixture-key-that-is-never-used-outside-unit-tests-2026';
const digest=data=>createHash('sha256').update(data).digest('hex');
function fixture(options={}){
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
  const actor=new RDC2DeviceActor(ctx,env,{now:()=>now,...options});
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
  const spectatorFrames=[];
  s.sockets.push({send:raw=>spectatorFrames.push(JSON.parse(raw))});
  const done={version:2,type:'complete',id:op.id,claimId:op.claimId,
    requestDigest:op.requestDigest,resultJson,resultDigest:digest(resultJson)};
  await s.actor.webSocketMessage(ws,JSON.stringify(done));
  assert.deepEqual(spectatorFrames,[],
    'an unrelated device socket must not receive completion for someone else');
  assert.deepEqual(sent.map(x=>x.type),['claimed','result_ack'],
    'original claimant receives its precise ACK without an extra result hint');
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
  const originalTransaction=s.storage.transactionSync.bind(s.storage);
  let transactions=0;
  s.storage.transactionSync=(fn)=>{transactions++;return originalTransaction(fn)};
  assert.equal((await s.call('/v2/status',{principal:'TOC-owner'})).status,200);
  assert.equal((await s.call('/v2/metrics',{principal:'TOC-owner',limit:1})).status,200);
  assert.equal(transactions,0,
    'enrolled owner status and metrics must not acquire redundant SQLite write transactions');
  const next=await s.call('/v2/admit',s.req('second-owner-operation'));
  assert.equal(next.status,200);
  assert.equal(transactions,1,
    'enrolled owner admission must use only its necessary durable enqueue transaction');
});
test('V2 large result uses private R2, exact original identity and durable recovery',async()=>{
  const s=fixture();
  await s.call('/v2/heartbeat');
  const admitted=await s.call('/v2/admit',s.req('bulk-output'));
  const ownerFrames=[];const spectatorFrames=[];
  const claimant={send:raw=>ownerFrames.push(JSON.parse(raw))};
  s.sockets.push(claimant,{send:raw=>spectatorFrames.push(JSON.parse(raw))});
  await s.actor.webSocketMessage(claimant,JSON.stringify({version:2,type:'claim'}));
  const claim=ownerFrames[0].operation;
  assert.equal(claim.id,admitted.body.id);
  const resultJson=JSON.stringify({content:[{type:'text',text:'V'.repeat(420000)}],
    structuredContent:{ok:true,kind:'large-original'}});
  const args={id:claim.id,claimId:claim.claimId,requestDigest:claim.requestDigest,
    resultJson,resultDigest:digest(resultJson)};
  const completed=await s.call('/v2/complete_bulk',args);
  assert.equal(completed.status,200);
  assert.equal(completed.body.state,'completed');
  assert.equal(completed.body.duplicate,false);
  assert.deepEqual(ownerFrames.map(x=>x.type),['claimed','result_available'],
    'HTTP bulk completion sends one hint only to its exact original claimant');
  assert.deepEqual(spectatorFrames,[],
    'unrelated worker receives no private bulk result notification');
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

test('V2 duplicate admission has bounded exact-result waiters under 48-request burst',async()=>{
  const s=fixture();
  await s.call('/v2/bind',{principal:'TOC-owner',bootstrap:true});
  await s.call('/v2/heartbeat');
  const initial=await s.call('/v2/admit',s.req('hot-result'));
  assert.equal(initial.status,200);
  const pending=Array.from({length:48},()=>s.call('/v2/admit_wait',{
    ...s.req('hot-result'),waitMs:250
  }));
  await new Promise(resolve=>setTimeout(resolve,30));
  const size=s.actor.resultWaiters.get(initial.body.id)?.size??0;
  assert.ok(size>=1,'one original operation should retain active response waiters');
  assert.ok(size<=16,'flood must not retain more than sixteen timers for same operation');
  const claim=await s.call('/v2/claim');
  assert.equal(claim.body.operation.id,initial.body.id);
  const resultJson=JSON.stringify({content:[{type:'text',text:'result'}]});
  assert.equal((await s.call('/v2/complete',{
    id:claim.body.operation.id,claimId:claim.body.operation.claimId,
    requestDigest:claim.body.operation.requestDigest,
    resultJson,resultDigest:digest(resultJson)
  })).status,200);
  const replies=await Promise.all(pending);
  assert.ok(replies.every(x=>x.status===200&&x.body.id===initial.body.id));
  assert.equal(s.actor.resultWaiters.size,0,'all bounded listeners cleaned after original completion');
  assert.equal((await s.call('/v2/claim')).body.operation,null,'original work executed at most once');
});

test('V2 mixed-key burst caps aggregate waiter timers at 128 without dropping original identities',async()=>{
  const s=fixture();
  await s.call('/v2/bind',{principal:'TOC-owner',bootstrap:true});
  await s.call('/v2/heartbeat');
  const original=[];
  for(let n=0;n<10;n++){
    const admitted=await s.call('/v2/admit',s.req('original-'+n));
    assert.equal(admitted.status,200);
    original.push(admitted.body.id);
  }
  const pending=[];
  for(let n=0;n<10;n++){
    for(let r=0;r<16;r++)
      pending.push(s.call('/v2/admit_wait',{...s.req('original-'+n),waitMs:200}));
  }
  await new Promise(resolve=>setTimeout(resolve,40));
  const active=[...s.actor.resultWaiters.values()].reduce((sum,group)=>sum+group.size,0);
  assert.ok(active>=1);
  assert.ok(active<=128,'durable actor may not retain unbounded concurrent response waiters');
  const all=await Promise.all(pending);
  assert.equal(all.length,160);
  assert.ok(all.every(x=>x.status===200&&original.includes(x.body.id)));
  assert.equal(s.actor.resultWaiters.size,0);
});

test('V2 aborted client release removes exact wait subscription without replaying work',async()=>{
  const s=fixture();
  await s.call('/v2/bind',{principal:'TOC-owner',bootstrap:true});
  await s.call('/v2/heartbeat');
  const admitted=await s.call('/v2/admit',s.req('abort-original'));
  const ctrl=new AbortController();
  const pending=s.actor.waitForResult('TOC-owner',admitted.body.id,180,ctrl.signal);
  assert.equal(s.actor.resultWaiterCount,1);
  ctrl.abort();
  await new Promise(resolve=>setTimeout(resolve,5));
  assert.equal(s.actor.resultWaiterCount,0,
    'cancelled client must not occupy a slot until its timeout');
  assert.equal((await pending).id,admitted.body.id);
  assert.equal(s.actor.resultWaiters.size,0);
  const claim=await s.call('/v2/claim');
  assert.equal(claim.body.operation.id,admitted.body.id,
    'aborted read must leave original durable operation intact');
});

test('V2 opt-in claim wait pushes one durable original operation with no second claim request',async()=>{
  const s=fixture();
  await s.call('/v2/bind',{principal:'TOC-owner',bootstrap:true});
  await s.call('/v2/heartbeat');
  const frames=[];
  const ws={send:payload=>frames.push(JSON.parse(payload))};
  s.sockets.push(ws);
  await s.actor.webSocketMessage(ws,JSON.stringify({version:2,type:'claim_wait'}));
  assert.equal(frames.length,0,'no empty-claim response while waiting for newly admitted work');
  const response=await s.call('/v2/admit',s.req('single-push'));
  assert.equal(response.status,200);
  assert.deepEqual(frames.map(x=>x.type),['claimed'],
    'claimed must arrive in the original outstanding worker wait, without extra claim hop');
  assert.equal(frames[0].operation.id,response.body.id);
  assert.equal(frames[0].operation.requestJson,s.req('single-push').requestJson);
  assert.equal(s.actor.pendingClaimSockets.size,0);
  assert.equal((await s.call('/v2/claim')).body.operation,null,'durable original cannot be claimed twice');
});

test('V2 claim wait safely drops a disconnected waiter without accidentally claiming work',async()=>{
  const s=fixture();
  await s.call('/v2/bind',{principal:'TOC-owner',bootstrap:true});
  await s.call('/v2/heartbeat');
  const ws={send:()=>{throw new Error('closed socket')},close:()=>{}};
  s.sockets.push(ws);
  await s.actor.webSocketMessage(ws,JSON.stringify({version:2,type:'claim_wait'}));
  assert.equal(s.actor.pendingClaimSockets.size,1);
  await s.actor.webSocketClose(ws,1000,'done');
  assert.equal(s.actor.pendingClaimSockets.size,0);
  s.sockets.pop();
  const op=await s.call('/v2/admit',s.req('after-disconnect'));
  const original=await s.call('/v2/claim');
  assert.equal(original.body.operation.id,op.body.id);
  assert.equal((await s.call('/v2/claim')).body.operation,null);
});

test('V2 hibernation restores one pending claim credit for direct no-roundtrip wake',async()=>{
  const s=fixture();
  await s.call('/v2/bind',{principal:'TOC-owner',bootstrap:true});
  await s.call('/v2/heartbeat');
  let attachment=null;
  const frames=[];
  const ws={
    send:payload=>frames.push(JSON.parse(payload)),
    serializeAttachment:value=>{attachment=value},
    deserializeAttachment:()=>attachment
  };
  s.sockets.push(ws);
  await s.actor.webSocketMessage(ws,JSON.stringify({version:2,type:'claim_wait'}));
  assert.deepEqual(attachment,{rdc2:{pendingClaim:true}},
    'the original waiting credit must survive actor hibernation');
  const restarted=new RDC2DeviceActor(s.ctx,s.env,{now:s.now});
  assert.equal(restarted.pendingClaimSockets.size,0,'actor memory starts empty');
  const op=await restarted.fetch(new Request('https://private.internal/v2/admit',{
    method:'POST',headers:{'Content-Type':'application/json',
      'X-RDC2-Internal-Key':KEY},body:JSON.stringify(s.req('hibernate-direct'))
  }));
  const received=await op.json();
  assert.equal(op.status,200);
  assert.deepEqual(frames.map(f=>f.type),['claimed'],
    'one durable claim should be pushed directly without waiting for another worker request');
  assert.equal(frames[0].operation.id,received.id);
  assert.deepEqual(attachment,{rdc2:{operationId:received.id}},
    'waiting credit must be replaced by one active original claim');
  assert.equal(restarted.journal.claim(),null,'original work must never be claimed twice');
  await restarted.webSocketMessage(ws,JSON.stringify({version:2,type:'claim_wait'}));
  assert.equal(frames.length,1,'timeout refresh must not authorize a duplicate operation');
});

test('V2 claim wait rejects payload-bearing frames without consuming durable queue',async()=>{
  const s=fixture();
  await s.call('/v2/bind',{principal:'TOC-owner',bootstrap:true});
  await s.call('/v2/heartbeat');
  const observed=[];
  const socket={send:raw=>observed.push(JSON.parse(raw))};
  s.sockets.push(socket);
  await s.actor.webSocketMessage(socket,JSON.stringify({
    version:2,type:'claim_wait',requestJson:'private-execution-payload'
  }));
  assert.deepEqual(observed.map(x=>x.type),['protocol_error']);
  assert.equal(s.actor.pendingClaimSockets.size,0);
  const queued=await s.call('/v2/admit',s.req('still-queued'));
  assert.equal(queued.status,200);
  const claimed=await s.call('/v2/claim');
  assert.equal(claimed.body.operation.id,queued.body.id);
});

test('V2 duplicate pending or active socket claims cannot authorize two operations',async()=>{
  const s=fixture();
  await s.call('/v2/bind',{principal:'TOC-owner',bootstrap:true});
  await s.call('/v2/heartbeat');
  const frames=[];
  let attachment=null;
  const socket={
    send:x=>frames.push(JSON.parse(x)),
    serializeAttachment:x=>{attachment=x},
    deserializeAttachment:()=>attachment
  };
  s.sockets.push(socket);
  const request=JSON.stringify({version:2,type:'claim_wait'});
  await s.actor.webSocketMessage(socket,request);
  await s.actor.webSocketMessage(socket,request);
  assert.equal(s.actor.pendingClaimSockets.size,1);
  const first=await s.call('/v2/admit',s.req('first-credit'));
  const second=await s.call('/v2/admit',s.req('second-credit'));
  assert.equal(first.status,200);
  assert.equal(second.status,200);
  const remainingIds=[];
  for(let n=0;n<5;n++){
    const queued=await s.call('/v2/admit',s.req('queued-while-busy-'+n));
    assert.equal(queued.status,200);
    remainingIds.push(queued.body.id);
  }
  assert.equal(frames.filter(x=>x.type==='work_available').length,0,
    'an active original claim must suppress redundant wake hints during a slow command');
  assert.equal(frames.filter(x=>x.type==='claimed').length,1);
  const original=frames.find(x=>x.type==='claimed').operation;
  assert.equal(original.id,first.body.id);
  await s.actor.webSocketMessage(socket,request);
  assert.equal(frames.filter(x=>x.type==='claimed').length,1,
    'timeout refresh cannot claim a second job before original completion');
  const restarted=new RDC2DeviceActor(s.ctx,s.env,{now:s.now});
  await restarted.webSocketMessage(socket,request);
  assert.equal(frames.filter(x=>x.type==='claimed').length,1,
    'WebSocket hibernation attachment must retain active original claim');
  const resultJson=JSON.stringify({content:[{type:'text',text:'correct'}]});
  await restarted.webSocketMessage(socket,JSON.stringify({
    version:2,type:'complete',id:original.id,claimId:original.claimId,
    requestDigest:original.requestDigest,resultJson,resultDigest:digest(resultJson)}));
  assert.equal(frames.at(-1).type,'result_ack');
  assert.equal(attachment,null,'completed original clears persisted claim credit');
  await restarted.webSocketMessage(socket,request);
  assert.equal(frames.filter(x=>x.type==='claimed').length,2);
  assert.equal(frames.filter(x=>x.type==='claimed')[1].operation.id,second.body.id);
  for(const id of remainingIds){
    const next=await s.call('/v2/claim');
    assert.equal(next.body.operation.id,id,'queued originals must remain FIFO and un-replayed');
  }
  assert.equal((await s.call('/v2/claim')).body.operation,null);
});

test('V2 pending socket credits remain capacity bounded during hostile fanout',async()=>{
  const s=fixture();
  await s.call('/v2/bind',{principal:'TOC-owner',bootstrap:true});
  await s.call('/v2/heartbeat');
  const results=[];
  for(let n=0;n<24;n++){
    const observed=[];
    const socket={send:x=>observed.push(JSON.parse(x))};
    s.sockets.push(socket);
    await s.actor.webSocketMessage(socket,JSON.stringify({version:2,type:'claim_wait'}));
    results.push(observed);
  }
  assert.equal(s.actor.pendingClaimSockets.size,8);
  assert.equal(results.filter(x=>x.at(-1)?.type==='operation_error').length,16);
  assert.equal(s.actor.journal.status('TOC-owner').pending,0);
});

test('V2 private actor exposes only owner-bound sanitized durable phase timings',async()=>{
  const s=fixture();
  await s.call('/v2/bind',{principal:'TOC-owner',bootstrap:true});
  await s.call('/v2/heartbeat');
  const accepted=await s.call('/v2/admit',s.req('phase-timing'));
  const claim=await s.call('/v2/claim');
  const raw=JSON.stringify({content:[{type:'text',text:'private-result'}]});
  await s.call('/v2/complete',{id:claim.body.operation.id,
    claimId:claim.body.operation.claimId,
    requestDigest:claim.body.operation.requestDigest,
    resultJson:raw,resultDigest:digest(raw)});
  const metrics=await s.call('/v2/metrics',{principal:'TOC-owner',limit:30});
  assert.equal(metrics.status,200);
  assert.equal(metrics.body.source,'rdc2-durable-journal');
  assert.equal(metrics.body.sampleCount,1);
  assert.equal(metrics.body.samples[0].operationId,accepted.body.id);
  assert.equal(JSON.stringify(metrics.body).includes('phase-timing'),false);
  assert.equal(JSON.stringify(metrics.body).includes('private-result'),false);
  assert.equal((await s.call('/v2/metrics',{principal:'intruder',limit:30})).status,403);
  assert.equal((await s.call('/v2/metrics',{principal:'TOC-owner',limit:999})).status,400);
});


test('V2 negotiated quiet heartbeat records 80 liveness updates without filling socket receive buffer',async()=>{
  const s=fixture();
  const observed=[];
  const socket={send:raw=>observed.push(JSON.parse(raw))};
  s.sockets.push(socket);
  const first=JSON.stringify({version:2,type:'heartbeat'});
  await s.actor.webSocketMessage(socket,first);
  assert.equal(observed.at(-1).type,'heartbeat_ack');
  assert.equal(observed.at(-1).heartbeatNoAckSupported,true);
  const firstSeen=s.actor.journal.lastSeen();
  assert.equal(typeof firstSeen,'number');
  observed.length=0;
  for(let i=0;i<80;i++){
    s.advance(15_000);
    await s.actor.webSocketMessage(socket,JSON.stringify({version:2,type:'heartbeat_no_ack'}));
  }
  assert.equal(observed.length,0,
    '60+ quiet heartbeats must not accumulate WebSocket ACK frames during long commands');
  assert.equal(s.actor.journal.lastSeen(),firstSeen+80*15_000);
  assert.equal(s.actor.journal.online(),true);
  await s.actor.webSocketMessage(socket,first);
  assert.equal(observed.length,1,'Normal negotiation heartbeat still acknowledges');
  assert.equal(observed[0].type,'heartbeat_ack');
});

test('V2 quiet heartbeat rejects extra payloads without changing online status or claim credits',async()=>{
  const s=fixture();
  const observed=[];
  const socket={send:raw=>observed.push(JSON.parse(raw))};
  s.sockets.push(socket);
  const original=s.actor.journal.lastSeen();
  await s.actor.webSocketMessage(socket,JSON.stringify({
    version:2,type:'heartbeat_no_ack',requestJson:'payload-not-allowed'}));
  assert.equal(observed.at(-1).type,'protocol_error');
  assert.equal(s.actor.journal.lastSeen(),original);
  assert.equal(s.actor.pendingClaimSockets.size,0);
  assert.equal((await s.call('/v2/claim')).body.operation,null);
});

test('V2 owner recovery traffic reaps expired private R2 in background without delaying admission',async()=>{
  const s=fixture();
  await s.call('/v2/heartbeat');
  const makeBulk=async key=>{
    await s.call('/v2/heartbeat');
    const admitted=await s.call('/v2/admit',s.req(key));
    assert.equal(admitted.status,200);
    const operation=(await s.call('/v2/claim')).body.operation;
    const resultJson=JSON.stringify({content:[{type:'text',text:key.repeat(90000)}]});
    const input={id:operation.id,claimId:operation.claimId,
      requestDigest:operation.requestDigest,resultJson,resultDigest:digest(resultJson)};
    assert.equal((await s.call('/v2/complete_bulk',input)).status,200);
    return operation.id;
  };
  const expiredId=await makeBulk('old-bulk');
  s.advance(3_500_000);
  const liveId=await makeBulk('live-bulk');
  s.advance(100_001);
  assert.equal(s.files.size,2);
  const jobs=[];
  s.ctx.waitUntil=job=>jobs.push(job);
  let unlockDelete;
  const delayedDelete=new Promise(resolve=>{unlockDelete=resolve});
  const originalDelete=s.bucket.delete.bind(s.bucket);
  s.bucket.delete=async key=>{await delayedDelete;return originalDelete(key)};
  const before=Date.now();
  const status=await Promise.race([
    s.call('/v2/status',{principal:'TOC-owner'}),
    new Promise((_,reject)=>setTimeout(()=>reject(new Error('Owner status waited for slow R2 deletion')),250))
  ]);
  assert.equal(status.status,200);
  assert.ok(Date.now()-before<250,'background retention must never block owner status');
  assert.equal(jobs.length,1,'owner traffic should schedule bounded retention');
  assert.equal(s.files.size,2,'R2 deletion remains pending, request has returned');
  const unauthorized=await s.call('/v2/status',{principal:'different-owner'});
  assert.equal(unauthorized.status,403);
  assert.equal(jobs.length,1,'foreign owner must never trigger maintenance');
  await s.call('/v2/status',{principal:'TOC-owner'});
  assert.equal(jobs.length,1,'back-to-back admissions should not spawn more sweeps');
  unlockDelete();
  await Promise.all(jobs);
  assert.equal(s.bucket.deletes,1);
  assert.equal(s.files.size,1,'only expired R2 object should be deleted');
  assert.equal((await s.call('/v2/recover',{principal:'TOC-owner',id:expiredId})).body.state,
    'result_expired','original operation identity must survive result retirement');
  assert.equal((await s.call('/v2/recover',{principal:'TOC-owner',id:liveId})).body.state,
    'completed','unexpired original result must remain recoverable');
  s.advance(60_001);
  await s.call('/v2/status',{principal:'TOC-owner'});
  assert.equal(jobs.length,2,'later owner traffic may schedule another bounded maintenance pass');
  await Promise.all(jobs);
  assert.equal(s.bucket.deletes,1,'no repeat deletion for already-retired result');
});

test('V2 background retention fails closed on R2 outage and retries without deleting original claim',async()=>{
  const s=fixture();
  await s.call('/v2/heartbeat');
  const admission=await s.call('/v2/admit',s.req('recoverable-original'));
  const claim=(await s.call('/v2/claim')).body.operation;
  const resultJson=JSON.stringify({content:[{type:'text',text:'X'.repeat(300000)}]});
  assert.equal((await s.call('/v2/complete_bulk',{
    id:claim.id,claimId:claim.claimId,requestDigest:claim.requestDigest,
    resultJson,resultDigest:digest(resultJson)
  })).status,200);
  s.advance(3_600_001);
  const jobs=[];
  s.ctx.waitUntil=job=>jobs.push(job);
  const originalDelete=s.bucket.delete.bind(s.bucket);
  let failures=0;
  s.bucket.delete=async key=>{
    if(failures++===0)throw Error('synthetic backend R2 outage');
    return originalDelete(key);
  };
  assert.equal((await s.call('/v2/status',{principal:'TOC-owner'})).status,200);
  assert.equal(jobs.length,1);
  await Promise.all(jobs);
  assert.equal(s.files.size,1,'failed R2 deletion must leave original bytes intact');
  assert.equal((await s.call('/v2/recover',{
    principal:'TOC-owner',id:admission.body.id
  })).body.state,'result_expired','original identity is never replayed after retention failure');
  s.advance(60_001);
  assert.equal((await s.call('/v2/status',{principal:'TOC-owner'})).status,200);
  await Promise.all(jobs);
  assert.equal(s.files.size,0,'next owner action retries only original expired object deletion');
  assert.equal((await s.call('/v2/recover',{
    principal:'TOC-owner',id:admission.body.id
  })).body.state,'result_expired');
  assert.equal(s.db.prepare('SELECT state FROM rdc2_ops WHERE id=?').get(admission.body.id).state,
    'completed','default rollback-compatible retention must preserve original operation');
});

test('V2 authenticated owner maintenance recycles hot slots without replaying an old mutation',async()=>{
  const s=fixture({maxRecords:3});
  // Test-only opt-in: no production rollback has been qualified for archive writes.
  s.env.RDC2_TOMBSTONE_ARCHIVE_ENABLED='1';
  const jobs=[];
  s.ctx.waitUntil=task=>jobs.push(task);
  const bound=await s.call('/v2/bind',{principal:'TOC-owner',bootstrap:true});
  assert.equal(bound.status,200);
  assert.equal((await s.call('/v2/heartbeat')).status,200);
  const originals=[];
  for(const key of ['original-a','original-b','original-c']){
    const accepted=await s.call('/v2/admit',s.req(key));
    const claimed=await s.call('/v2/claim',{});
    assert.equal(accepted.status,200);
    const resultJson=JSON.stringify({content:[{type:'text',text:key}]});
    const finished=await s.call('/v2/complete',{
      id:accepted.body.id,claimId:claimed.body.operation.claimId,
      requestDigest:claimed.body.operation.requestDigest,
      resultJson,resultDigest:digest(resultJson)
    });
    assert.equal(finished.status,200);
    originals.push(accepted.body.id);
  }
  assert.equal((await s.call('/v2/admit',s.req('next'))).body.error.code,'journal_full');
  await Promise.all(jobs);
  jobs.length=0;
  s.advance(3_600_001);
  const status=await s.call('/v2/status',{principal:'TOC-owner'});
  assert.equal(status.status,200);
  assert.equal(jobs.length,1);
  await jobs[0];
  assert.equal(s.db.prepare('SELECT count(*) n FROM rdc2_ops').get().n,0);
  assert.equal(s.db.prepare('SELECT count(*) n FROM rdc2_tombstones').get().n,3);
  assert.equal((await s.call('/v2/heartbeat')).status,200);
  const fresh=await s.call('/v2/admit',s.req('next'));
  assert.equal(fresh.status,200);
  assert.equal(fresh.body.reused,false);
  const old=await s.call('/v2/admit',s.req('original-a'));
  assert.equal(old.status,200);
  assert.equal(old.body.id,originals[0]);
  assert.equal(old.body.reused,true);
  assert.equal((await s.call('/v2/recover',{principal:'TOC-owner',id:originals[0]})).body.state,'result_expired');
  const currentClaim=await s.call('/v2/claim',{});
  assert.equal(currentClaim.body.operation.id,fresh.body.id);
});

test('V2 archival stays disabled by default until a tombstone-aware rollback is verified',async()=>{
  const s=fixture({maxRecords:1});
  const jobs=[];
  s.ctx.waitUntil=task=>jobs.push(task);
  await s.call('/v2/heartbeat');
  const accepted=await s.call('/v2/admit',s.req('original-mutation'));
  const claim=(await s.call('/v2/claim')).body.operation;
  const resultJson=JSON.stringify({content:[{type:'text',text:'original-result'}]});
  assert.equal((await s.call('/v2/complete',{
    id:claim.id,claimId:claim.claimId,
    requestDigest:claim.requestDigest,resultJson,resultDigest:digest(resultJson)
  })).status,200);
  await Promise.all(jobs);
  s.advance(3_600_001);
  assert.equal((await s.call('/v2/status',{principal:'TOC-owner'})).status,200);
  await Promise.all(jobs);
  assert.equal(s.db.prepare('SELECT count(*) n FROM rdc2_tombstones').get().n,0,
    'old rollback reader knows only original rdc2_ops');
  assert.equal(s.db.prepare('SELECT state FROM rdc2_ops WHERE id=?').get(accepted.body.id).state,'completed');
  assert.equal((await s.call('/v2/recover',{principal:'TOC-owner',id:accepted.body.id})).body.state,'result_expired');
});

test('V2 socket upgrade refuses more than eight authenticated live device sockets before allocating a pair',async()=>{
  const s=fixture();
  const existing=Array.from({length:8},()=>({send(){}}));
  s.sockets.push(...existing);
  let accepts=0;
  s.ctx.acceptWebSocket=()=>{accepts++};
  const request=()=>new Request('https://rdc2.internal/v2/socket',{
    method:'GET',headers:{Upgrade:'websocket','X-RDC2-Internal-Key':KEY}
  });
  const denied=await s.actor.fetch(request());
  assert.equal(denied.status,429,'ninth socket must be rejected before an upgrade is created');
  assert.equal((await denied.json()).error.code,'device_socket_capacity');
  assert.equal(accepts,0);
  assert.equal(s.actor.pendingClaimSockets.size,0);
  s.sockets.splice(0,1);
  const underLimit=await s.actor.fetch(request());
  assert.notEqual(underLimit.status,429,'capacity should recover when old socket leaves');
  assert.equal(s.sockets.length,7);
  assert.equal(s.actor.pendingClaimSockets.size,0);
});

test('V2 hostile socket fanout is bounded without disturbing existing work or owner',async()=>{
  const s=fixture();
  const old=Array.from({length:8},()=>({send(){}}));
  s.sockets.push(...old);
  let accepted=0;
  s.ctx.acceptWebSocket=()=>{accepted++};
  const upgrade=()=>new Request('https://rdc2.internal/v2/socket',{
    method:'GET',headers:{Upgrade:'websocket','X-RDC2-Internal-Key':KEY}
  });
  const failures=await Promise.all(Array.from({length:96},()=>s.actor.fetch(upgrade())));
  assert.ok(failures.every(response=>response.status===429));
  assert.equal(accepted,0,'no unauthorized extra actor sockets');
  assert.equal((await s.call('/v2/heartbeat')).status,200);
  const original=await s.call('/v2/admit',s.req('owner-after-flood'));
  assert.equal(original.status,200,'legitimate owner admission remains available');
  assert.equal((await s.call('/v2/claim')).body.operation.id,original.body.id);
  assert.equal(s.sockets.length,8);
});
