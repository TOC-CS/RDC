import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {DatabaseSync} from 'node:sqlite';
import {RDC2Journal} from '../../lib/v2/rdc2-journal.mjs';

const digest=raw=>createHash('sha256').update(raw).digest('hex');
function fixture(capacity=3){
  const db=new DatabaseSync(':memory:');
  let now=1700000000000;
  const storage={
    sql:{exec(query,...args){
      const rows=/^\s*(SELECT|PRAGMA|WITH)\b|\bRETURNING\b/i.test(query)?
        db.prepare(query).all(...args): /^\s*CREATE/i.test(query)?
        (db.exec(query),[]): (db.prepare(query).run(...args),[]);
      return {toArray:()=>rows};
    }},
    transactionSync(fn){
      db.exec('BEGIN');
      try{const result=fn();db.exec('COMMIT');return result}
      catch(err){db.exec('ROLLBACK');throw err}
    }
  };
  let journal=new RDC2Journal(storage,{now:()=>now,maxRecords:capacity});
  journal.bindOwner('owner',{bootstrap:true});
  journal.heartbeat();
  const request=key=>{
    const requestJson=JSON.stringify({name:'rdc_job_run',arguments:{key}});
    return {principal:'owner',requestKey:key,requestJson,
      requestDigest:digest(requestJson),tool:'rdc_job_run',mutating:true};
  };
  const run=key=>{
    const input=request(key);
    const admitted=journal.enqueue(input);
    const claimed=journal.claim();
    assert.equal(claimed.id,admitted.id);
    const resultJson=JSON.stringify({content:[{type:'text',text:'result-'+key}]});
    const resultDigest=digest(resultJson);
    journal.complete({id:admitted.id,claimId:claimed.claimId,
      requestDigest:claimed.requestDigest,resultJson,resultDigest});
    return {admitted,claimed,resultJson,resultDigest,input};
  };
  return {db,storage,request,run,get journal(){return journal},
    reopen(){journal=new RDC2Journal(storage,{now:()=>now,maxRecords:capacity})},
    advance:ms=>{now+=ms}};
}
test('expired confirmed completions archive only their minimal immutable replay identities',()=>{
  const s=fixture(3);
  const done=['a','b','c'].map(k=>s.run(k));
  assert.throws(()=>s.journal.enqueue(s.request('d')),
    e=>e.code==='journal_full');
  s.advance(3_600_001);
  s.journal.sweep();
  assert.equal(s.journal.archiveRetired(10),3);
  assert.equal(s.db.prepare('SELECT count(*) n FROM rdc2_ops').get().n,0);
  assert.equal(s.db.prepare('SELECT count(*) n FROM rdc2_tombstones').get().n,3);
  s.journal.heartbeat();
  const fresh=s.journal.enqueue(s.request('d'));
  assert.equal(fresh.reused,false);
  const duplicate=s.journal.enqueue(s.request('a'));
  assert.deepEqual(duplicate,{id:done[0].admitted.id,state:'completed',reused:true});
  assert.deepEqual(s.journal.recover('owner',done[0].admitted.id),
    {id:done[0].admitted.id,state:'result_expired'});
  assert.deepEqual(s.journal.complete({id:done[0].admitted.id,
    claimId:done[0].claimed.claimId,
    requestDigest:done[0].claimed.requestDigest,
    resultJson:done[0].resultJson,resultDigest:done[0].resultDigest}),
    {id:done[0].admitted.id,state:'completed',duplicate:true});
  assert.throws(()=>s.journal.enqueue({...s.request('a'),
    requestDigest:digest('forged')}),e=>e.code==='request_id_conflict');
  assert.throws(()=>s.journal.complete({id:done[0].admitted.id,
    claimId:done[0].claimed.claimId,
    requestDigest:done[0].claimed.requestDigest,
    resultJson:done[0].resultJson,resultDigest:digest('forged')}),
    e=>e.code==='result_conflict');
  assert.throws(()=>s.journal.recover('other',done[0].admitted.id),
    e=>e.code==='owner_forbidden');
  s.reopen();
  assert.equal(s.journal.enqueue(s.request('a')).id,done[0].admitted.id);
  assert.equal(s.journal.recover('owner',done[0].admitted.id).state,'result_expired');
  assert.equal(s.journal.claim().id,fresh.id);
});
test('never archive unexpired private R2 result pointers or uncertain original mutations',()=>{
  const s=fixture(2);
  const input=s.request('bulky');
  const admitted=s.journal.enqueue(input), claimed=s.journal.claim();
  const resultJson=JSON.stringify({content:[{type:'text',text:'large result'}]});
  const resultDigest=digest(resultJson);
  const key='rdc2-results/'+admitted.id+'/'+resultDigest+'.json';
  s.journal.completeExternal({id:admitted.id,claimId:claimed.claimId,
    requestDigest:claimed.requestDigest,resultDigest,resultSize:262145,resultKey:key});
  const uncertain=s.journal.enqueue(s.request('uncertain'));
  s.journal.claim();
  s.advance(3_600_001);
  s.journal.sweep();
  assert.equal(s.journal.archiveRetired(64),0);
  assert.equal(s.db.prepare('SELECT count(*) n FROM rdc2_ops').get().n,2);
  assert.equal(s.journal.recover('owner',uncertain.id).state,'unknown');
  s.journal.heartbeat();
  assert.throws(()=>s.journal.enqueue(s.request('fourth')),e=>e.code==='journal_full');
  s.journal.clearExpiredExternal(admitted.id,key);
  assert.equal(s.journal.archiveRetired(64),1);
  assert.equal(s.journal.recover('owner',admitted.id).state,'result_expired');
  assert.equal(s.journal.recover('owner',uncertain.id).state,'unknown');
  assert.equal(s.journal.enqueue(s.request('fourth')).reused,false);
  assert.equal(s.journal.enqueue(s.request('uncertain')).id,uncertain.id);
});
test('bounded archives preserve order and forbid resurrection of expired queue requests',()=>{
  const s=fixture(4);
  const entries=['a','b','c','d'].map(key=>s.journal.enqueue(s.request(key)));
  s.advance(30_001);
  s.journal.sweep();
  assert.equal(s.journal.archiveRetired(2),2);
  assert.equal(s.db.prepare('SELECT count(*) n FROM rdc2_ops').get().n,2);
  assert.equal(s.journal.recover('owner',entries[0].id).state,'expired');
  assert.equal(s.journal.enqueue(s.request('a')).id,entries[0].id);
  assert.equal(s.journal.archiveRetired(2),2);
  assert.equal(s.journal.enqueue(s.request('e')).reused,false);
  assert.equal(s.db.prepare('SELECT count(*) n FROM rdc2_tombstones').get().n,4);
});

test('100 confirmed mutations across synthetic retention cycles cannot exhaust eight hot slots',()=>{
  const s=fixture(8);
  const originals=[];
  for(let i=0;i<100;i++){
    if(i>0&&i%8===0){
      s.advance(3_600_001);
      s.journal.sweep();
      assert.equal(s.journal.archiveRetired(8),8);
      s.journal.heartbeat();
    }
    originals.push(s.run('cycle-'+i).admitted.id);
  }
  s.advance(3_600_001);
  s.journal.sweep();
  assert.equal(s.journal.archiveRetired(8),4);
  assert.equal(s.db.prepare('SELECT count(*) n FROM rdc2_tombstones').get().n,100);
  assert.equal(s.db.prepare('SELECT count(*) n FROM rdc2_ops').get().n,0);
  for(const i of [0,7,8,31,63,95,99]){
    assert.equal(s.journal.enqueue(s.request('cycle-'+i)).id,originals[i]);
    assert.equal(s.journal.recover('owner',originals[i]).state,'result_expired');
  }
  assert.equal(new Set(originals).size,100);
  assert.throws(()=>s.journal.enqueue({...s.request('cycle-0'),requestDigest:digest('altered')}),
    error=>error.code==='request_id_conflict');
});
