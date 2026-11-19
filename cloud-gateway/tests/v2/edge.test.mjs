import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {createHash} from 'node:crypto';
import {RDC2DeviceActor} from '../../lib/v2/rdc2-actor.mjs';
import {createRDC2Edge} from '../../lib/v2/rdc2-edge.mjs';
const KEY='synthetic-only-private-edge-internal-key-2026';
const DEVICE_KEY='synthetic-only-device-key-not-a-real-credential-2026';
const sha=value=>createHash('sha256').update(value).digest('hex');
const catalog=[{
  name:'rdc_job_run',description:'Safe authorized terminal fixture',
  inputSchema:{type:'object',properties:{argv:{type:'array',items:{type:'string'}},
    cwd:{type:'string'}},required:['argv','cwd'],additionalProperties:false},
  annotations:{readOnlyHint:false},'x-rdc-mutating':true
}];
function fixture(){
  const db=new DatabaseSync(':memory:');
  const storage={
    sql:{exec(sql,...values){
      const records=/^\s*(SELECT|WITH|PRAGMA)\b|\bRETURNING\b/i.test(sql)?
        db.prepare(sql).all(...values):
        /^\s*CREATE/i.test(sql)?(db.exec(sql),[]):(db.prepare(sql).run(...values),[]);
      return {toArray:()=>records};
    }},
    transactionSync(fn){
      db.exec('BEGIN');
      try{const value=fn();db.exec('COMMIT');return value}
      catch(e){db.exec('ROLLBACK');throw e}
    }
  };
  const ctx={storage,getWebSockets(){return []}};
  const env={RDC2_RUNTIME_ENABLED:'1',RDC2_INTERNAL_KEY:KEY,
    RDC2_OWNER_BOOTSTRAP:'private-site',RDC_DEVICE_ID:'v2-test-device',
    RDC_DEVICE_SECRET:DEVICE_KEY};
  const actor=new RDC2DeviceActor(ctx,env);
  env.RDC2_DEVICE={idFromName:id=>id,get:()=>actor};
  const edge=createRDC2Edge({catalog});
  let seq=0;
  async function invoke(name,args={},owner='TOC-owner'){
    const response=await edge.mcp(new Request('https://owner-site.invalid/v2/mcp',{
      method:'POST',headers:{'Content-Type':'application/json',
        ...(owner===null?{}:{'oai-authenticated-user-id':owner})},
      body:JSON.stringify({jsonrpc:'2.0',id:++seq,method:'tools/call',
        params:{name,arguments:args}})}),env);
    return {status:response.status,body:await response.json()};
  }
  async function direct(path,value={}){
    const response=await actor.fetch(new Request('https://actor.internal'+path,{
      method:'POST',headers:{'Content-Type':'application/json','X-RDC2-Internal-Key':KEY},
      body:JSON.stringify(value)}));
    return {status:response.status,data:await response.json()};
  }
  return {db,ctx,env,actor,edge,invoke,direct};
}
test('V2 private Site gateway returns 404 when runtime not explicitly enabled',async()=>{
  const s=fixture();delete s.env.RDC2_RUNTIME_ENABLED;
  assert.equal((await s.invoke('rdc_connection_status')).status,404);
  assert.equal(s.db.prepare('SELECT COUNT(*) n FROM rdc2_meta').get().n,0);
});
test('V2 authenticates actual private Site owner before remote device state',async()=>{
  const s=fixture();
  assert.equal((await s.invoke('rdc_connection_status',{},null)).status,401);
  const allowed=await s.invoke('rdc_connection_status');
  assert.equal(allowed.status,200);
  assert.equal(allowed.body.result.structuredContent.online,false);
  const denied=await s.invoke('rdc_connection_status',{},'other-owner');
  assert.equal(denied.status,403);
  assert.equal(JSON.stringify(denied.body).includes('lastSeenMs'),false);
});
test('V2 worker dispatch and original result recovery use durable actor with no D1',async()=>{
  const s=fixture();
  await s.invoke('rdc_connection_status');
  await s.direct('/v2/heartbeat');
  const args={argv:['/bin/echo','original'],cwd:'/tmp',
    _rdc_request_id:'v2-owner-original'};
  const pending=await s.invoke('rdc_job_run',args);
  assert.equal(pending.status,200);
  const original=pending.body.result.structuredContent;
  assert.equal(original.pending,true);
  assert.ok(original.operation_id);
  const claimed=await s.direct('/v2/claim');
  assert.equal(claimed.status,200);
  assert.equal(claimed.data.operation.id,original.operation_id);
  const resultJson=JSON.stringify({content:[{type:'text',text:'original'}],
    structuredContent:{ok:true,output:'original'}});
  assert.equal((await s.direct('/v2/complete',{id:claimed.data.operation.id,
    claimId:claimed.data.operation.claimId,
    requestDigest:claimed.data.operation.requestDigest,
    resultJson,resultDigest:sha(resultJson)})).status,200);
  const recovered=await s.invoke('rdc_operation_status',{operation_id:original.operation_id});
  assert.equal(recovered.status,200);
  assert.equal(recovered.body.result.structuredContent.output,'original');
  const duplicate=await s.invoke('rdc_job_run',args);
  assert.equal(duplicate.body.result.structuredContent.output,'original');
  assert.equal(s.db.prepare('SELECT COUNT(*) n FROM rdc2_ops').get().n,1);
});
test('V2 rejects unknown tool, absent mutation identity, and cross-owner duplicate',async()=>{
  const s=fixture();
  await s.invoke('rdc_connection_status');
  await s.direct('/v2/heartbeat');
  assert.equal((await s.invoke('rdc_unknown_tool')).status,400);
  assert.equal((await s.invoke('rdc_job_run',{argv:['echo','test'],cwd:'/tmp'})).status,400);
  const args={argv:['echo','test'],cwd:'/tmp',_rdc_request_id:'once'};
  assert.equal((await s.invoke('rdc_job_run',args)).status,200);
  assert.equal((await s.invoke('rdc_job_run',args,'other-owner')).status,403);
  assert.equal(s.db.prepare('SELECT COUNT(*) n FROM rdc2_ops').get().n,1);
});
test('V2 worker socket request enforces original device credential before connecting',async()=>{
  const s=fixture();
  const request=new Request('https://owner-site.invalid/v2/device/socket',{
    method:'GET',headers:{Upgrade:'websocket','X-RDC-Device-Key':'wrong'}});
  const denied=await s.edge.deviceSocket(request,s.env);
  assert.equal(denied.status,401);
  const missing=new Request('https://owner-site.invalid/v2/device/socket',{
    method:'GET',headers:{Upgrade:'websocket'}});
  assert.equal((await s.edge.deviceSocket(missing,s.env)).status,401);
});
test('V2 warm status requires only one private Durable Object fetch hop',async()=>{
  const s=fixture();let actorFetches=0;
  s.env.RDC2_DEVICE.get=()=>({fetch:async req=>{actorFetches++;return s.actor.fetch(req)}});
  const first=await s.invoke('rdc_connection_status');
  assert.equal(first.status,200);
  assert.equal(actorFetches,1,'owner enrollment and liveness must use one actor hop');
  actorFetches=0;
  const next=await s.invoke('rdc_connection_status');
  assert.equal(next.status,200);
  assert.equal(actorFetches,1,'warm status must avoid a separate bind hop');
});
test('V2 private Site bulk upload authenticates original device and recovers same result',async()=>{
  const s=fixture();
  const objects=new Map();
  s.env.BUCKET={
    async put(key,value){objects.set(key,String(value))},
    async get(key){const raw=objects.get(key);return raw===undefined?null:{text:async()=>raw}},
    async delete(key){objects.delete(key)}
  };
  await s.invoke('rdc_connection_status');
  await s.direct('/v2/heartbeat');
  const requestJson=JSON.stringify({name:'rdc_job_run',arguments:{argv:['echo','large'],cwd:'/tmp'}});
  const original=await s.direct('/v2/admit',{principal:'TOC-owner',
    requestKey:'bulk-test',requestJson,requestDigest:sha(requestJson),
    tool:'rdc_job_run',mutating:true});
  const claim=(await s.direct('/v2/claim')).data.operation;
  assert.equal(claim.id,original.data.id);
  const resultJson=JSON.stringify({content:[{type:'text',text:'U'.repeat(360000)}],
    structuredContent:{ok:true,category:'bulk'}});
  const args={id:claim.id,claimId:claim.claimId,requestDigest:claim.requestDigest,
    resultJson,resultDigest:sha(resultJson)};
  const upload=key=>new Request('https://owner-site.invalid/v2/device/result',{
    method:'POST',headers:{'Content-Type':'application/json','X-RDC-Device-Key':key},
    body:JSON.stringify(args)});
  const unauthorized=await s.edge.deviceResult(upload('wrong-device-key'),s.env);
  assert.equal(unauthorized.status,401);
  assert.equal(objects.size,0);
  const first=await s.edge.deviceResult(upload(DEVICE_KEY),s.env);
  assert.equal(first.status,200);
  assert.equal((await first.json()).operation_id,claim.id);
  assert.equal(objects.size,1);
  const recovered=await s.invoke('rdc_operation_status',{operation_id:claim.id});
  assert.equal(recovered.status,200);
  assert.equal(recovered.body.result.structuredContent.category,'bulk');
  const again=await s.edge.deviceResult(upload(DEVICE_KEY),s.env);
  assert.equal(again.status,200);
  assert.equal((await again.json()).duplicate,true);
  assert.equal(objects.size,1);
});
test('V2 private Site bulk endpoint remains completely disabled by default',async()=>{
  const s=fixture();delete s.env.RDC2_RUNTIME_ENABLED;
  const req=new Request('https://owner-site.invalid/v2/device/result',{
    method:'POST',headers:{'Content-Type':'application/json','X-RDC-Device-Key':DEVICE_KEY},
    body:'{}'});
  const resp=await s.edge.deviceResult(req,s.env);
  assert.equal(resp.status,404);
  assert.equal(s.db.prepare('SELECT COUNT(*) n FROM rdc2_meta').get().n,0);
});
