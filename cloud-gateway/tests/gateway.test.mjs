import assert from 'node:assert/strict';
import { test } from 'node:test';
import { DatabaseSync } from 'node:sqlite';
import { readFileSync, readdirSync } from 'node:fs';
import { createGateway } from '../lib/rdc-gateway-core.mjs';

const DEVICE = '00000000-0000-4000-8000-000000000001';
const KEY = 'test-device-key-with-at-least-thirty-two-bytes';
const plainTool = (name, mutating=false) => ({name, description:'Test tool', inputSchema:{type:'object', properties:{value:{type:'string'}}, additionalProperties:false}, annotations:{readOnlyHint:!mutating}, 'x-rdc-mutating':mutating});
const catalog = [plainTool('rdc_system_status'), plainTool('rdc_file_write',true), plainTool('rdc_preview_frame'), plainTool('rdc_preview_open'), plainTool('rdc_preview_activity')];
const result = value => ({content:[{type:'text',text:value}],structuredContent:{ok:true,value}});

class D1 {
  constructor() {
    this.sqlite = new DatabaseSync(':memory:');
    for(const name of readdirSync(new URL('../drizzle/', import.meta.url)).filter(x=>x.endsWith('.sql')).sort()) {
      this.sqlite.exec(readFileSync(new URL('../drizzle/'+name,import.meta.url),'utf8'));
    }
  }
  prepare(sql) {
    const db=this.sqlite;
    return {bind(...args) {
      const prepared=db.prepare(sql);
      return {
        async first(){return prepared.get(...args)??null},
        async all(){return {results:prepared.all(...args)}},
        async run(){const r=prepared.run(...args);return {meta:{changes:Number(r.changes)}}},
      };
    }};
  }
}
class R2 {
  constructor(){this.objects=new Map();this.puts=0}
  async put(key,body){this.puts++;this.objects.set(key,String(body));return {key}}
  async get(key){const body=this.objects.get(key);return body===undefined?null:{size:Buffer.byteLength(body),text:async()=>body}}
  async delete(keys){for(const key of Array.isArray(keys)?keys:[keys])this.objects.delete(key)}
}
function setup(limits={}) {
  let now=1700000000000;
  const env={DB:new D1(),BUCKET:new R2(),RDC_DEVICE_ID:DEVICE,RDC_DEVICE_SECRET:KEY,RDC_OWNER_BOOTSTRAP:'private-site'};
  const gateway=createGateway({catalog,resourceHtml:'<!doctype html><html>Real embedded resource fixture</html>',iconDataUri:'data:image/png;base64,eA==',clock:()=>now,sleep:async ms=>{now+=ms},limits:{callWaitMs:0,pollWaitMs:0,...limits}});
  const request=(path,body,headers={})=>new Request('https://rdc.example'+path,{method:'POST',headers:{'Content-Type':'application/json',...headers},body:JSON.stringify(body)});
  const mcp=async(name,args={},owner='owner-1')=>{
    const response=await gateway.mcp(request('/mcp',{jsonrpc:'2.0',id:'call',method:'tools/call',params:{name,arguments:args}}, owner?{'oai-authenticated-user-id':owner}:{}),env);
    return {status:response.status,body:await response.json()};
  };
  const poll=async(body={},key=KEY)=>{
    const response=await gateway.poll(request('/device/poll',{device_id:DEVICE,...body},{'X-RDC-Device-Key':key}),env);
    return {status:response.status,body:await response.json()};
  };
  const complete=async(op,value=result('done'))=>{
    const response=await gateway.result(request('/device/result',{device_id:DEVICE,operation_id:op.operation_id,claim_id:op.claim_id,request_sha256:op.request_sha256,result_json:JSON.stringify(value)},{'X-RDC-Device-Key':KEY}),env);
    return {status:response.status,body:await response.json()};
  };
  return {env,gateway,request,mcp,poll,complete,advance:ms=>now+=ms,now:()=>now};
}

test('MCP metadata exposes the actual HTML and resource link without device secrets',async()=>{
  const s=setup();
  const tools=await s.gateway.mcp(s.request('/mcp',{jsonrpc:'2.0',id:1,method:'tools/list'}),s.env);
  const payload=await tools.json();
  const write=payload.result.tools.find(t=>t.name==='rdc_file_write');
  assert.ok(write.inputSchema.required.includes('_rdc_request_id'));
  assert.equal(JSON.stringify(payload).includes(KEY),false);
  const resource=await s.gateway.mcp(s.request('/mcp',{jsonrpc:'2.0',id:2,method:'resources/read',params:{uri:'ui://rdc/preview-v1.html'}}),s.env);
  const content=(await resource.json()).result.contents[0];
  assert.match(content.text,/Real embedded/);
  assert.equal(content.mimeType,'text/html;profile=mcp-app');
  assert.deepEqual(content._meta.ui.csp.connectDomains,[]);
});

test('only the pinned Sites principal can dispatch, and device credentials never become owner credentials',async()=>{
  const s=setup();
  assert.equal((await s.mcp('rdc_connection_status',{},null)).status,401);
  assert.equal((await s.mcp('rdc_connection_status')).body.result.structuredContent.ok,true);
  assert.equal((await s.mcp('rdc_connection_status',{},'another-user')).status,403);
  assert.equal((await s.poll({},'wrong-key')).status,401);
  assert.equal((await s.poll({device_id:'another-device'})).status,403);
  assert.equal((await s.poll({claim:false})).status,200);
});

test('bootstrap requires an explicit private Site deployment grant',async()=>{
  const s=setup();delete s.env.RDC_OWNER_BOOTSTRAP;
  assert.equal((await s.mcp('rdc_connection_status')).status,503);
  assert.equal(s.env.DB.sqlite.prepare('SELECT count(*) AS n FROM gateway_owner').get().n,0);
});

test('a mutation is claimed once and an idempotency key cannot change its arguments',async()=>{
  const s=setup();await s.poll({claim:false});
  const args={value:'one',_rdc_request_id:'stable-action-1'};
  const queued=await s.mcp('rdc_file_write',args);
  const id=queued.body.result.structuredContent.operation_id;
  assert.equal(queued.body.result.structuredContent.pending,true);
  const repeated=await s.mcp('rdc_file_write',args);
  assert.equal(repeated.body.result.structuredContent.operation_id,id);
  assert.equal((await s.mcp('rdc_file_write',{...args,value:'changed'})).status,409);
  const claims=await Promise.all([s.poll(),s.poll()]);
  assert.equal(claims.filter(x=>x.body.operation).length,1);
  const op=claims.find(x=>x.body.operation).body.operation;
  assert.deepEqual(JSON.parse(op.request_json),{name:'rdc_file_write',arguments:{value:'one'}});
  assert.equal((await s.complete(op)).body.duplicate,false);
  assert.equal((await s.complete(op)).body.duplicate,true);
  assert.equal((await s.complete(op,result('different'))).status,409);
  const done=await s.mcp('rdc_operation_status',{operation_id:id});
  assert.equal(done.body.result.structuredContent.value,'done');
  assert.equal((await s.poll()).body.operation,null);
});

test('offline work is rejected and expired queued work is never executed',async()=>{
  const s=setup();
  assert.equal((await s.mcp('rdc_system_status')).body.result.structuredContent.error.code,'device_offline');
  await s.poll({claim:false});
  const queued=await s.mcp('rdc_file_write',{value:'x',_rdc_request_id:'expires'});
  s.advance(31_000);
  assert.equal((await s.poll()).body.operation,null);
  const status=await s.mcp('rdc_operation_status',{operation_id:queued.body.result.structuredContent.operation_id});
  assert.equal(status.body.result.structuredContent.error.code,'expired_before_execution');
});

test('lost claim responses become unknown without redelivery, and a late result can still resolve them',async()=>{
  const s=setup();await s.poll({claim:false});
  const queued=await s.mcp('rdc_file_write',{value:'x',_rdc_request_id:'lost-claim'});
  const op=(await s.poll()).body.operation;
  s.advance(121_000);
  assert.equal((await s.poll()).body.operation,null);
  const status=await s.mcp('rdc_operation_status',{operation_id:queued.body.result.structuredContent.operation_id});
  assert.equal(status.body.result.structuredContent.error.code,'outcome_unknown');
  assert.equal((await s.complete(op)).status,200);
  assert.equal((await s.mcp('rdc_operation_status',{operation_id:op.operation_id})).body.result.structuredContent.value,'done');
});

test('large image results use R2, survive readback, and keep D1 rows small',async()=>{
  const s=setup();await s.poll({claim:false});
  await s.mcp('rdc_preview_frame',{value:'frame'});
  const op=(await s.poll()).body.operation;
  const image='A'.repeat(8*1024*1024);
  const output={content:[{type:'image',mimeType:'image/png',data:image}],structuredContent:{ok:true}};
  assert.equal((await s.complete(op,output)).status,200);
  const stored=s.env.DB.sqlite.prepare('SELECT * FROM gateway_operations WHERE id=?').get(op.operation_id);
  assert.ok(Buffer.byteLength(JSON.stringify(stored))<4096);
  assert.equal(stored.request_json,null);
  const done=await s.mcp('rdc_operation_status',{operation_id:op.operation_id});
  assert.equal(done.body.result.content[0].data.length,image.length);
  s.advance(31_000);await s.poll({claim:false});
  const expired=await s.mcp('rdc_operation_status',{operation_id:op.operation_id});
  assert.equal(expired.body.result.isError,false);
  assert.equal(expired.body.result.structuredContent.reason,'result_expired');
  assert.equal(expired.body.result.structuredContent.preview_refresh_required,true);
  assert.equal(expired.body.result.structuredContent.refresh_tool,'rdc_preview_frame');
  assert.equal(expired.body.result.structuredContent.operation_id,op.operation_id);
  assert.equal(s.env.BUCKET.objects.size,0);
});

test('completed preview expiry reports a fresh read without throwing or redispatching the original operation',async()=>{
  for(const name of ['rdc_preview_open','rdc_preview_frame','rdc_preview_activity']){
    const s=setup({resultTtlMs:1000,frameTtlMs:1000,frameOperationTtlMs:5000});
    await s.poll({claim:false});
    const args={value:'selected observation',_rdc_request_id:'retained-preview'};
    const initial=await s.mcp(name,args);
    const op=(await s.poll()).body.operation;
    assert.equal(op.operation_id,initial.body.result.structuredContent.operation_id);
    await s.complete(op);
    s.advance(1001);
    for(const response of [await s.mcp('rdc_operation_status',{operation_id:op.operation_id}),await s.mcp(name,args)]){
      const payload=response.body.result;
      assert.equal(response.status,200);
      assert.equal(payload.isError,false);
      assert.deepEqual(payload.structuredContent,{
        ok:true,preview_refresh_required:true,refresh_tool:name,
        operation_id:op.operation_id,completed:true,reason:'result_expired',
        message:'This preview observation completed, but its response expired. Request a fresh read-only snapshot.',
      });
      assert.deepEqual(JSON.parse(payload.content[0].text),payload.structuredContent);
    }
    assert.equal(s.env.DB.sqlite.prepare('SELECT COUNT(*) AS n FROM gateway_operations').get().n,1);
    assert.equal((await s.poll()).body.operation,null);
    const next=await s.mcp(name,{value:'selected observation',_rdc_request_id:'fresh-preview'});
    assert.equal(next.body.result.structuredContent.pending,true);
    assert.notEqual(next.body.result.structuredContent.operation_id,op.operation_id);
    const fresh=(await s.poll()).body.operation;
    assert.equal(fresh.operation_id,next.body.result.structuredContent.operation_id);
    assert.equal((await s.poll()).body.operation,null);
  }
});

test('a missing stored preview response has the same explicit completed read-only recovery contract',async()=>{
  const s=setup();await s.poll({claim:false});
  await s.mcp('rdc_preview_open',{_rdc_request_id:'missing-preview-result'});
  const op=(await s.poll()).body.operation;await s.complete(op);
  const row=s.env.DB.sqlite.prepare('SELECT result_key FROM gateway_operations WHERE id=?').get(op.operation_id);
  await s.env.BUCKET.delete(row.result_key);
  const status=await s.mcp('rdc_operation_status',{operation_id:op.operation_id});
  assert.equal(status.body.result.isError,false);
  assert.deepEqual(status.body.result.structuredContent,{
    ok:true,preview_refresh_required:true,refresh_tool:'rdc_preview_open',
    operation_id:op.operation_id,completed:true,reason:'result_unavailable',
    message:'This preview observation completed, but its stored response is unavailable. Request a fresh read-only snapshot.',
  });
  assert.equal(s.env.DB.sqlite.prepare('SELECT COUNT(*) AS n FROM gateway_operations').get().n,1);
  assert.equal((await s.poll()).body.operation,null);
});

test('fresh-preview recovery is withheld for mutations, other reads, and every unfinished or uncertain outcome',async()=>{
  for(const [name,persistedMutation] of [['rdc_file_write',1],['rdc_system_status',0],['rdc_preview_open',1]]){
    const s=setup({resultTtlMs:1000});await s.poll({claim:false});
    const args={value:'retain identity',_rdc_request_id:'no-preview-replay'};
    await s.mcp(name,args);const op=(await s.poll()).body.operation;await s.complete(op);
    s.env.DB.sqlite.prepare('UPDATE gateway_operations SET mutating=? WHERE id=?').run(persistedMutation,op.operation_id);
    s.advance(1001);
    for(const response of [await s.mcp('rdc_operation_status',{operation_id:op.operation_id}),await s.mcp(name,args)]){
      assert.equal(response.body.result.isError,true);
      assert.equal(response.body.result.structuredContent.error.code,'result_expired');
      assert.equal(response.body.result.structuredContent.operation_id,op.operation_id);
      assert.equal(response.body.result.structuredContent.completed,true);
      assert.equal(response.body.result.structuredContent.preview_refresh_required,undefined);
      assert.equal(response.body.result.structuredContent.refresh_tool,undefined);
    }
    assert.equal(s.env.DB.sqlite.prepare('SELECT COUNT(*) AS n FROM gateway_operations').get().n,1);
    assert.equal((await s.poll()).body.operation,null);
  }
  for(const state of ['queued','claimed','unknown','expired']){
    const s=setup();await s.poll({claim:false});
    const pending=await s.mcp('rdc_preview_open',{_rdc_request_id:'unfinished-preview'});
    const id=pending.body.result.structuredContent.operation_id;
    s.env.DB.sqlite.prepare('UPDATE gateway_operations SET state=? WHERE id=?').run(state,id);
    const status=await s.mcp('rdc_operation_status',{operation_id:id});
    assert.equal(status.body.result.structuredContent.preview_refresh_required,undefined,state);
    assert.equal(status.body.result.structuredContent.refresh_tool,undefined,state);
    assert.equal(status.body.result.structuredContent.operation_id,id,state);
    assert.equal(s.env.DB.sqlite.prepare('SELECT COUNT(*) AS n FROM gateway_operations').get().n,1);
  }
});

test('retired preview frames release operation capacity while mutation identities remain recoverable',async()=>{
  const s=setup({maxOperations:3,frameTtlMs:1000,frameOperationTtlMs:2000});
  await s.poll({claim:false});
  const mutationArgs={value:'keep this identity',_rdc_request_id:'retained-mutation'};
  await s.mcp('rdc_file_write',mutationArgs);
  const mutation=(await s.poll()).body.operation;
  await s.complete(mutation);
  const frames=[];
  for(let i=0;i<2;i++){
    await s.mcp('rdc_preview_frame',{value:'frame-'+i});
    const frame=(await s.poll()).body.operation;
    frames.push(frame);await s.complete(frame);
  }
  assert.equal((await s.mcp('rdc_preview_frame',{value:'blocked'})).body.result.structuredContent.error.code,'gateway_busy');
  s.advance(2001);await s.poll({claim:false});
  assert.equal(s.env.DB.sqlite.prepare('SELECT COUNT(*) AS n FROM gateway_operations').get().n,1);
  assert.equal((await s.mcp('rdc_preview_frame',{value:'new observation'})).body.result.structuredContent.pending,true);
  const original=await s.mcp('rdc_file_write',mutationArgs);
  assert.equal(original.body.result.structuredContent.value,'done');
  assert.equal(original.body.result._meta['rdc/operation_id'],mutation.operation_id);
  // A pump whose upload acknowledgement was lost can learn that this
  // short-lived read was retired. It must never repeat a mutation on 404.
  assert.equal((await s.complete(frames[0])).body.error.code,'operation_not_found');
});

test('observer claims only activity while normal operations keep their original queue order',async()=>{
  const s=setup();await s.poll({claim:false});
  await s.mcp('rdc_file_write',{value:'first action',_rdc_request_id:'primary-write'});
  await s.mcp('rdc_preview_frame',{value:'frame behind work'});
  const pending=await s.mcp('rdc_preview_activity',{value:'actual work'});
  // Real admissions can share a millisecond. Deliberately reverse UUID order
  // so this contract cannot pass because random IDs happen to sort as FIFO.
  s.env.DB.sqlite.prepare('UPDATE gateway_operations SET id=?,created_ms=? WHERE tool=?')
    .run('ffffffff-ffff-4fff-8fff-ffffffffffff',s.now(),'rdc_file_write');
  s.env.DB.sqlite.prepare('UPDATE gateway_operations SET id=?,created_ms=? WHERE tool=?')
    .run('00000000-0000-4000-8000-000000000000',s.now(),'rdc_preview_frame');
  const claims=await Promise.all([s.poll({observation_only:true}),s.poll({observation_only:true})]);
  const observed=claims.filter(x=>x.body.operation);
  assert.equal(observed.length,1);
  assert.equal(observed[0].body.operation.operation_id,pending.body.result.structuredContent.operation_id);
  assert.equal(JSON.parse(observed[0].body.operation.request_json).name,'rdc_preview_activity');
  assert.equal((await s.poll({observation_only:true})).body.operation,null);
  const primary=(await s.poll()).body.operation;
  assert.equal(JSON.parse(primary.request_json).name,'rdc_file_write');
  await s.complete(observed[0].body.operation,result('live while primary runs'));
  const recovered=await s.mcp('rdc_operation_status',{operation_id:observed[0].body.operation.operation_id});
  assert.equal(recovered.body.result.structuredContent.value,'live while primary runs');
  assert.equal(s.env.DB.sqlite.prepare('SELECT state FROM gateway_operations WHERE id=?').get(primary.operation_id).state,'claimed');
  const next=(await s.poll()).body.operation;
  assert.equal(JSON.parse(next.request_json).name,'rdc_preview_frame');
  assert.notEqual(next.operation_id,primary.operation_id);
  assert.equal((await s.poll()).body.operation,null);
});

test('observer selector is a strict boolean and cannot turn a heartbeat into a claim',async()=>{
  const s=setup();
  for(const observation_only of ['true',1,{},null])assert.equal((await s.poll({observation_only})).status,400);
  assert.equal((await s.poll({claim:false,observation_only:true})).status,400);
  assert.equal((await s.poll({claim:false,observation_only:false})).status,200);
});

test('activity result and identity retention stay bounded while mutations remain recoverable',async()=>{
  const s=setup({maxOperations:3,frameTtlMs:1000,frameOperationTtlMs:2000});
  await s.poll({claim:false});
  const args={value:'preserve action',_rdc_request_id:'observer-retained-mutation'};
  await s.mcp('rdc_file_write',args);const primary=(await s.poll()).body.operation;
  await s.complete(primary,result('actual completed mutation'));
  let first;
  for(let i=0;i<12;i++){
    const queued=await s.mcp('rdc_preview_activity',{value:'read-'+i});
    assert.equal(queued.body.result.structuredContent.pending,true);
    const observed=(await s.poll({observation_only:true})).body.operation;
    first??=observed;
    await s.complete(observed,result('current-'+i));
    s.advance(2001);await s.poll({claim:false});
    assert.equal(s.env.DB.sqlite.prepare('SELECT COUNT(*) AS n FROM gateway_operations').get().n,1);
  }
  assert.equal((await s.mcp('rdc_file_write',args)).body.result.structuredContent.value,'actual completed mutation');
  assert.equal((await s.complete(first)).body.error.code,'operation_not_found');
});

test('activity returns the original pending identity immediately without waiting for the worker',async()=>{
  const s=setup({callWaitMs:20000,previewWaitMs:8000});await s.poll({claim:false});
  const before=s.now();
  const args={value:'activity',_rdc_request_id:'one-activity-request'};
  const first=await s.mcp('rdc_preview_activity',args);
  assert.equal(s.now(),before);
  assert.equal(first.body.result.structuredContent.pending,true);
  const again=await s.mcp('rdc_preview_activity',args);
  assert.equal(again.body.result.structuredContent.operation_id,first.body.result.structuredContent.operation_id);
  assert.equal(s.env.DB.sqlite.prepare('SELECT COUNT(*) AS n FROM gateway_operations').get().n,1);
});

test('backlog and body limits reject work before dispatch',async()=>{
  const s=setup({maxBacklog:1});await s.poll({claim:false});
  assert.equal((await s.mcp('rdc_file_write',{value:'x'})).status,400);
  await s.mcp('rdc_system_status',{});
  assert.equal((await s.mcp('rdc_system_status',{})).body.result.structuredContent.error.code,'gateway_busy');
  const request=s.request('/device/result',{device_id:DEVICE,result_json:'A'.repeat(13*1024*1024)},{'X-RDC-Device-Key':KEY});
  assert.equal((await s.gateway.result(request,s.env)).status,413);
});


// Contract source: modelcontextprotocol/modelcontextprotocol schema/2026-07-28/schema.ts
// https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/schema/2026-07-28/schema.ts
// Complete results carry resultType; discovery/lists/resource reads additionally
// carry nonnegative ttlMs and public/private cacheScope. Zero/private prevents
// retaining observations while satisfying both modern and legacy clients.
// These boundary checks catch modern-host rejection before the iframe mounts.
const modernMeta = version => ({'io.modelcontextprotocol/protocolVersion':version,
  'io.modelcontextprotocol/clientCapabilities':{}});
async function modern(s,method,params={},version='2026-07-28',headers={}) {
  const response=await s.gateway.mcp(s.request('/mcp',{jsonrpc:'2.0',id:'modern',method,
    params:{...params,_meta:modernMeta(version)}},{'MCP-Protocol-Version':version,'Mcp-Method':method,
      ...((method==='tools/call'||method==='resources/read')?{'Mcp-Name':params.name??params.uri}:{}),
      'oai-authenticated-user-id':'owner-1',...headers}),s.env);
  return {status:response.status,body:await response.json()};
}

test('modern discovery and cacheable resource responses satisfy required result fields',async()=>{
  const s=setup();
  for(const [method,params] of [['server/discover',{}],['tools/list',{}],['resources/list',{}],
    ['resources/templates/list',{}],['resources/read',{uri:'ui://rdc/preview-v2.html'}]]){
    const response=await modern(s,method,params);
    assert.equal(response.status,200,JSON.stringify(response.body));
    assert.equal(response.body.result.resultType,'complete',method);
    assert.ok(Number.isInteger(response.body.result.ttlMs)&&response.body.result.ttlMs>=0,method);
    assert.ok(['public','private'].includes(response.body.result.cacheScope),method);
  }
  const call=await modern(s,'tools/call',{name:'rdc_connection_status',arguments:{}});
  assert.equal(call.body.result.resultType,'complete');
  assert.equal(call.body.result.structuredContent.ok,true);
});

test('preview resources prefer inline and preserve every published alias',async()=>{
  const s=setup();
  const listing=await modern(s,'resources/list');
  assert.deepEqual(listing.body.result.resources.map(resource=>resource.uri),['ui://rdc/preview-v7.html']);
  for(const uri of ['ui://rdc/preview-v7.html','ui://rdc/preview-v6.html','ui://rdc/preview-v5.html','ui://rdc/preview-v4.html','ui://rdc/preview-v3.html','ui://rdc/preview-v2.html','ui://rdc/preview-v1.html']){
    const response=await modern(s,'resources/read',{uri});
    assert.equal(response.status,200);
    assert.equal(response.body.result.contents[0].uri,uri);
    assert.match(response.body.result.contents[0].text,/Real embedded/);
    assert.deepEqual(response.body.result.contents[0]._meta['openai/ui'],{availableDisplayModes:['inline','fullscreen'],preferredDisplayMode:'inline'});
  }
});

test('modern routing header mismatches are rejected before dispatch or version negotiation',async()=>{
  const s=setup();await s.poll({claim:false});
  for(const headers of [
    {'MCP-Protocol-Version':'2099-01-01'},
    {'Mcp-Method':'resources/read'},
    {'Mcp-Name':'rdc_system_status'},
  ]){
    const response=await modern(s,'tools/call',{name:'rdc_preview_open',arguments:{}},'2026-07-28',headers);
    assert.equal(response.status,400);
    assert.equal(response.body.error.code,-32020);
  }
  assert.equal(s.env.DB.sqlite.prepare('SELECT COUNT(*) AS n FROM gateway_operations').get().n,0);
});

test('modern unsupported versions report the requested and supported revisions without dispatch',async()=>{
  const s=setup();await s.poll({claim:false});
  const response=await modern(s,'tools/call',{name:'rdc_preview_open',arguments:{}},'2099-01-01');
  assert.equal(response.status,400);
  assert.equal(response.body.error.code,-32022);
  assert.deepEqual(response.body.error.data,{requested:'2099-01-01',supported:['2026-07-28']});
  assert.equal(s.env.DB.sqlite.prepare('SELECT COUNT(*) AS n FROM gateway_operations').get().n,0);
});

test('modern envelopes require protocol version and client capabilities while legacy initializes remain compatible',async()=>{
  const s=setup();
  for(const meta of [{},{'io.modelcontextprotocol/protocolVersion':'2026-07-28'}]){
    const response=await s.gateway.mcp(s.request('/mcp',{jsonrpc:'2.0',id:1,method:'tools/list',params:{_meta:meta}},
      {'MCP-Protocol-Version':'2026-07-28','Mcp-Method':'tools/list'}),s.env);
    assert.equal(response.status,400);
    assert.equal((await response.json()).error.code,-32602);
  }
  for(const protocolVersion of ['2024-11-05','2025-03-26','2025-06-18','2025-11-25']){
    const response=await s.gateway.mcp(s.request('/mcp',{jsonrpc:'2.0',id:2,method:'initialize',params:{protocolVersion}}),s.env);
    assert.equal(response.status,200);
    assert.equal((await response.json()).result.protocolVersion,protocolVersion);
  }
});

test('preview open queues once and immediately returns its original operation identity without device wait',async()=>{
  const s=setup({callWaitMs:20000,previewWaitMs:8000});await s.poll({claim:false});
  const start=s.now();
  const opened=await s.mcp('rdc_preview_open',{value:'selected',_rdc_request_id:'preview-original'});
  assert.equal(s.now(),start,'Mounting the UI must not wait for a device response');
  const pending=opened.body.result.structuredContent;
  assert.equal(pending.pending,true);
  const op=(await s.poll()).body.operation;
  assert.equal(op.operation_id,pending.operation_id);
  assert.deepEqual(JSON.parse(op.request_json),{name:'rdc_preview_open',arguments:{value:'selected'}});
  s.advance(121000);await s.poll({claim:false});
  const repeated=await s.mcp('rdc_preview_open',{value:'selected',_rdc_request_id:'preview-original'});
  assert.equal(repeated.body.result.structuredContent.operation_id,pending.operation_id);
  assert.equal(repeated.body.result.structuredContent.error.code,'outcome_unknown');
  assert.equal((await s.poll()).body.operation,null);
  await s.complete(op,result('original preview'));
  const recovered=await s.mcp('rdc_operation_status',{operation_id:pending.operation_id});
  assert.equal(recovered.body.result.structuredContent.value,'original preview');
  assert.equal(recovered.body.result._meta['rdc/operation_id'],pending.operation_id);
});

test('offline and full backlog preview opens mount availability without queueing or inventing device results',async()=>{
  for(const [status,message,limits,online] of [
    ['device_offline','The paired device is offline. No operation was queued.',{},false],
    ['gateway_busy','The relay has reached its bounded backlog or retention capacity. No operation was queued.',{maxBacklog:0},true],
  ]){
    const s=setup(limits);if(online)await s.poll({claim:false});
    const response=await s.mcp('rdc_preview_open');
    assert.equal(response.status,200);
    assert.equal(response.body.result.isError,false);
    assert.deepEqual(response.body.result.structuredContent,{ok:true,preview_unavailable:true,preview_status:status,message,device_id:DEVICE});
    assert.equal(s.env.DB.sqlite.prepare('SELECT COUNT(*) AS n FROM gateway_operations').get().n,0);
    assert.equal((await s.mcp('rdc_preview_open',{},'another-owner')).status,403);
    assert.equal((await s.mcp('rdc_preview_open',{},null)).status,401);
  }
});


test('bare legacy discovery and tools calls retain their fields alongside modern complete markers',async()=>{
  const s=setup();
  for(const method of ['server/discover','tools/list','resources/list','resources/templates/list']){
    const response=await s.gateway.mcp(s.request('/mcp',{jsonrpc:'2.0',id:1,method}),s.env);
    const payload=(await response.json()).result;
    assert.equal(response.status,200);
    assert.equal(payload.resultType,'complete');
    assert.equal(payload.ttlMs,0);
    assert.equal(payload.cacheScope,'private');
    if(method==='server/discover')assert.deepEqual(payload.supportedVersions,['2026-07-28']);
    if(method==='tools/list')assert.ok(payload.tools.some(tool=>tool.name==='rdc_file_write'));
  }
  const call=await s.mcp('rdc_connection_status');
  assert.equal(call.body.result.resultType,'complete');
  assert.equal(call.body.result.structuredContent.device_id,DEVICE);
  assert.deepEqual(JSON.parse(call.body.result.content[0].text),call.body.result.structuredContent);
});

test('an explicit modern envelope rejects absent routing headers without dispatch',async()=>{
  const s=setup();await s.poll({claim:false});
  const method='tools/call',params={name:'rdc_preview_open',arguments:{},_meta:modernMeta('2026-07-28')};
  for(const headers of [
    {'Mcp-Method':method,'Mcp-Name':params.name},
    {'MCP-Protocol-Version':'2026-07-28','Mcp-Name':params.name},
    {'MCP-Protocol-Version':'2026-07-28','Mcp-Method':method},
  ]){
    const response=await s.gateway.mcp(s.request('/mcp',{jsonrpc:'2.0',id:1,method,params},headers),s.env);
    assert.equal(response.status,400);
    assert.equal((await response.json()).error.code,-32020);
  }
  assert.equal(s.env.DB.sqlite.prepare('SELECT COUNT(*) AS n FROM gateway_operations').get().n,0);
});

test('invalid preview arguments still fail before offline availability and do not queue',async()=>{
  const s=setup();
  const response=await s.mcp('rdc_preview_open',{_rdc_request_id:''});
  assert.equal(response.status,400);
  assert.equal(response.body.error.data.code,'request_id_required');
  assert.equal(s.env.DB.sqlite.prepare('SELECT COUNT(*) AS n FROM gateway_operations').get().n,0);
});
