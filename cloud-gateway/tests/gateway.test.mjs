import assert from 'node:assert/strict';
import { test } from 'node:test';
import { DatabaseSync } from 'node:sqlite';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import { createGateway } from '../lib/rdc-gateway-core.mjs';
import * as GatewayCore from '../lib/rdc-gateway-core.mjs';

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
  constructor(){this.objects=new Map();this.puts=0;this.gets=0;this.deletes=0}
  async put(key,body){this.puts++;this.objects.set(key,String(body));return {key}}
  async get(key){this.gets++;const body=this.objects.get(key);return body===undefined?null:{size:Buffer.byteLength(body),text:async()=>body}}
  async delete(keys){this.deletes++;for(const key of Array.isArray(keys)?keys:[keys])this.objects.delete(key)}
}
function setup(limits={},testCatalog=catalog,waitHook=async()=>{},chatRouter=null) {
  let now=1700000000000;
  const env={DB:new D1(),BUCKET:new R2(),RDC_DEVICE_ID:DEVICE,RDC_DEVICE_SECRET:KEY,RDC_OWNER_BOOTSTRAP:'private-site'};
  const gateway=createGateway({catalog:testCatalog,resourceHtml:'<!doctype html><html>Real embedded resource fixture</html>',iconDataUri:'data:image/png;base64,eA==',clock:()=>now,sleep:async ms=>{now+=ms;await waitHook()},limits:{callWaitMs:0,pollWaitMs:0,...limits},chatRouter});
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

test('owner-only gateway metrics expose completion phase times without payloads',async()=>{
  const s=setup();
  await s.poll({claim:false});
  const queued=await s.mcp('rdc_file_write',{
    value:'private-sentinel-do-not-disclose',_rdc_request_id:'metrics-qa-private-key'});
  assert.equal(queued.status,200);
  s.advance(125);
  const claim=await s.poll();
  assert.ok(claim.body.operation);
  s.advance(50);
  const done=await s.complete(claim.body.operation,result('private-dont-echo'));
  assert.equal(done.status,200);
  const queries=[];
  const original=s.env.DB.prepare.bind(s.env.DB);
  s.env.DB.prepare=sql=>{queries.push(sql);return original(sql);};
  const metrics=await s.mcp('rdc_recent_operation_metrics',{limit:5});
  assert.equal(metrics.status,200);
  const payload=metrics.body.result.structuredContent;
  assert.equal(payload.ok,true);
  assert.equal(payload.count,1);
  assert.equal(payload.samples[0].tool,'rdc_file_write');
  assert.equal(payload.samples[0].queue_wait_ms,125);
  assert.equal(payload.samples[0].claim_to_result_ms,50);
  assert.equal(payload.samples[0].total_gateway_ms,175);
  assert.ok(!JSON.stringify(payload).includes('private-sentinel'));
  assert.ok(!JSON.stringify(payload).includes('private-dont-echo'));
  assert.ok(!JSON.stringify(payload).includes('metrics-qa-private-key'));
  assert.ok(!JSON.stringify(payload).includes(claim.body.operation.operation_id));
  assert.equal(queries.filter(sql=>/^(UPDATE|DELETE|INSERT) /i.test(sql.trim())).length,0,
    'metrics must be read-only, with no extra maintenance writes');
  assert.equal((await s.mcp('rdc_recent_operation_metrics',{limit:5},'other-owner')).status,403);
  assert.equal((await s.mcp('rdc_recent_operation_metrics',{limit:0})).status,400);
  assert.equal((await s.mcp('rdc_recent_operation_metrics',{limit:51})).status,400);
  assert.equal((await s.mcp('rdc_recent_operation_metrics',{limit:5,request_id:'inject'})).status,400);
});

test('connection status omits maintenance writes and ignores expired queued items',async()=>{
  const s=setup();
  await s.poll({claim:false});
  const first=await s.mcp('rdc_file_write',{value:'claimed',_rdc_request_id:'health-claimed-001'});
  assert.equal(first.status,200);
  const claimed=await s.poll();
  assert.ok(claimed.body.operation);
  const second=await s.mcp('rdc_file_write',{value:'expire',_rdc_request_id:'health-queued-002'});
  assert.equal(second.status,200);
  s.advance(30_050); // queued TTL is 30 seconds; claimed is still active.
  const before=s.env.DB.sqlite.prepare("SELECT state FROM gateway_operations WHERE request_key=?")
    .get('health-queued-002');
  assert.equal(before.state,'queued');
  const queries=[];
  const prior=s.env.DB.prepare.bind(s.env.DB);
  s.env.DB.prepare=sql=>{queries.push(sql); return prior(sql);};
  const status=await s.mcp('rdc_connection_status');
  assert.equal(status.status,200);
  assert.equal(status.body.result.structuredContent.pending_operations,1);
  assert.equal(status.body.result.structuredContent.online,true);
  assert.equal(queries.filter(sql=>/^(UPDATE|DELETE|INSERT) /i.test(sql.trim())).length,0,
    'read-only status must not run clean() updates or deletions');
  const still=s.env.DB.sqlite.prepare("SELECT state FROM gateway_operations WHERE request_key=?")
    .get('health-queued-002');
  assert.equal(still.state,'queued','status does not perform maintenance');
  await s.poll({claim:false});
  assert.equal(s.env.DB.sqlite.prepare("SELECT state FROM gateway_operations WHERE request_key=?")
    .get('health-queued-002').state,'expired','ordinary worker poll still cleans up due items');
});

test('normal cloud dispatch checks worker liveness without a status COUNT query',async()=>{
  const s=setup();
  await s.poll({claim:false});
  const queries=[];
  const original=s.env.DB.prepare.bind(s.env.DB);
  s.env.DB.prepare=sql=>{queries.push(sql);return original(sql);};
  const sent=await s.mcp('rdc_file_write',{value:'harmless',_rdc_request_id:'perf-online-only-20261117'});
  assert.equal(sent.status,200);
  const queueCounts=()=>queries.filter(sql=>sql.includes("SELECT COUNT(*) AS count FROM gateway_operations")).length;
  assert.equal(queueCounts(),0,
    'dispatch only uses online state; it need not issue a separate status COUNT');
  queries.length=0;
  const status=await s.mcp('rdc_connection_status');
  assert.equal(status.status,200);
  assert.equal(queueCounts(),1,'the public status tool still reports pending_operations');
});

test('synced one-call browser startup advertises durable session setup safely',async()=>{
  const assets=JSON.parse(readFileSync(new URL('../lib/rdc-assets.json',import.meta.url),'utf8'));
  const selected=assets.catalog.find(item=>item.name==='rdc_browser_start_navigate_observe');
  assert.ok(selected,'the worker catalog must include the one-call startup route');
  assert.equal(selected['x-rdc-mutating'],true);
  assert.deepEqual(selected.inputSchema.required,['url']);
  assert.ok(selected.inputSchema.properties.browser);
  assert.ok(selected.inputSchema.properties.width);
  assert.ok(selected.inputSchema.properties.height);
  const s=setup({},assets.catalog);
  const response=await s.gateway.mcp(s.request('/mcp',{jsonrpc:'2.0',id:123,method:'tools/list'}),s.env);
  assert.equal(response.status,200);
  const advertised=(await response.json()).result.tools.find(t=>t.name==='rdc_browser_start_navigate_observe');
  assert.ok(advertised);
  assert.equal(advertised.annotations.readOnlyHint,false);
  assert.deepEqual(advertised.inputSchema.required,['url','_rdc_request_id']);
});

test('batched coding edits advertise one durable mutating operation and replay guard',async()=>{
  const assets=JSON.parse(readFileSync(new URL('../lib/rdc-assets.json',import.meta.url),'utf8'));
  const source=assets.catalog.find(item=>item.name==='rdc_code_edit_many');
  assert.ok(source,'sync the new bounded project-scoped batch edit into the gateway');
  assert.equal(source['x-rdc-mutating'],true);
  assert.equal(source.inputSchema.properties.edits.maxItems,10);
  assert.deepEqual(source.inputSchema.required,['path','edits']);
  const s=setup({},assets.catalog);
  await s.poll({claim:false});
  const tools=await s.gateway.mcp(s.request('/mcp',{
    jsonrpc:'2.0',id:110,method:'tools/list'}),s.env);
  const published=(await tools.json()).result.tools.find(t=>t.name==='rdc_code_edit_many');
  assert.ok(published);
  assert.deepEqual(published.inputSchema.required,['path','edits','_rdc_request_id']);
  const args={path:'/synthetic/project',edits:[{
      file_path:'first.py',old_text:'bad',new_text:'fixed',expected_sha256:'a'.repeat(64)
    }],_rdc_request_id:'perf-code-edit-batch-001'};
  const first=await s.mcp('rdc_code_edit_many',args);
  assert.equal(first.status,200);
  const original=first.body.result.structuredContent.operation_id;
  assert.ok(original);
  const again=await s.mcp('rdc_code_edit_many',args);
  assert.equal(again.status,200);
  assert.equal(again.body.result.structuredContent.operation_id,original);
  assert.equal((await s.mcp('rdc_code_edit_many',{...args,edits:[{
    ...args.edits[0],new_text:'changed'
  }]})).status,409);
  const count=s.env.DB.sqlite.prepare(
    "SELECT COUNT(*) AS count FROM gateway_operations WHERE tool='rdc_code_edit_many'").get().count;
  assert.equal(count,1);
});

test('synced RDC gateway advertises bounded, read-only batched coding context',async()=>{
  const assets=JSON.parse(readFileSync(new URL('../lib/rdc-assets.json',import.meta.url),'utf8'));
  const target=assets.catalog.find(x=>x.name==='rdc_code_context');
  assert.ok(target,'The on-disk engine code-context tool must be synced to the gateway');
  assert.equal(target['x-rdc-mutating'],false);
  assert.ok(target.inputSchema.required.includes('path'));
  assert.equal(target.inputSchema.properties.list_limit.maximum,200);
  assert.equal(target.inputSchema.properties.search_limit.maximum,100);
  assert.equal(target.inputSchema.properties.max_files.maximum,1000);
  assert.equal(target.inputSchema.properties.file_paths.maxItems,20);
  assert.deepEqual(target.inputSchema.properties.search_mode.enum,['source','all']);
  const s=setup({},assets.catalog);
  const response=await s.gateway.mcp(s.request('/mcp',{
    jsonrpc:'2.0',id:'code-list',method:'tools/list'
  }),s.env);
  assert.equal(response.status,200);
  const body=await response.json();
  const spec=body.result.tools.find(x=>x.name==='rdc_code_context');
  assert.ok(spec);
  assert.equal(spec.annotations.readOnlyHint,true);
});

test('synced browser action/observe tools are one guarded cloud mutation each',async()=>{
  const assets=JSON.parse(readFileSync(new URL('../lib/rdc-assets.json',import.meta.url),'utf8'));
  const expected=[
    ['rdc_browser_navigate_observe',['session_id','url']],
    ['rdc_browser_click_observe',['session_id','observation_id','handle']],
    ['rdc_browser_fill_observe',['session_id','observation_id','handle','text']]
  ];
  const s=setup({},assets.catalog);
  const listing=await s.gateway.mcp(s.request('/mcp',{
    jsonrpc:'2.0',id:'atomic-tools',method:'tools/list'
  }),s.env);
  assert.equal(listing.status,200);
  const tools=(await listing.json()).result.tools;
  for(const [name,required] of expected){
    const source=assets.catalog.find(x=>x.name===name);
    assert.ok(source,name+' must be synced into the gateway');
    assert.equal(source['x-rdc-mutating'],true);
    assert.equal(source.annotations.readOnlyHint,false);
    assert.deepEqual(source.inputSchema.required,required);
    const cloud=tools.find(x=>x.name===name);
    assert.ok(cloud);
    assert.equal(cloud.annotations.readOnlyHint,false);
    assert.deepEqual(cloud.inputSchema.required,[...required,'_rdc_request_id']);
  }
});

test('shipped RDC server icon stays compact, branded, and recoverable in initialize metadata',async()=>{
  const assets=JSON.parse(readFileSync(new URL('../lib/rdc-assets.json',import.meta.url),'utf8'));
  assert.match(assets.iconDataUri,/^data:image\/png;base64,/);
  const png=Buffer.from(assets.iconDataUri.split(',')[1],'base64');
  const compact=readFileSync(new URL('../public/rdc-mcp-icon.png',import.meta.url));
  assert.deepEqual(png,compact,'The embedded icon must exactly match the shipped branded thumbnail');
  assert.equal(png.subarray(0,8).toString('hex'),'89504e470d0a1a0a');
  assert.equal(png.readUInt32BE(16),192);
  assert.equal(png.readUInt32BE(20),192);
  assert.ok(png.byteLength<60_000,'Branded icon metadata must not carry the 1 MB full-size logo');
  const gw=createGateway(assets);
  const response=await gw.mcp(new Request('https://rdc.example/mcp',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({jsonrpc:'2.0',id:2,method:'initialize',params:{protocolVersion:'2025-11-25'}})
  }),{});
  const text=await response.text();
  const obj=JSON.parse(text);
  assert.equal(response.status,200);
  assert.equal(obj.result.serverInfo.icons[0].src,assets.iconDataUri);
  assert.deepEqual(obj.result.serverInfo.icons[0].sizes,['192x192']);
  assert.ok(Buffer.byteLength(text)<80_000,'MCP initialization must remain small and fast');
});

test('embedded preview serves compact original-brand thumbnail without changing its independent local resource',async()=>{
  const assets=JSON.parse(readFileSync(new URL('../lib/rdc-assets.json',import.meta.url),'utf8'));
  const preview=readFileSync(new URL('../../rdc/embedded/preview.html',import.meta.url),'utf8');
  const small=readFileSync(new URL('../../rdc/assets/rdc-icon-192.png',import.meta.url));
  const expected='data:image/png;base64,'+small.toString('base64');
  assert.equal(assets.resourceHtml,preview,'Synced cloud resource must exactly match independently built RDC view');
  assert.ok(Buffer.byteLength(preview)<800_000,'Tiny preview logo must not embed 1.3 MB of full-sized PNG');
  assert.ok(preview.includes(expected),'Local preview must retain the original branded logo in the compact image');
  assert.equal((preview.match(/data:image\/png;base64,/g)??[]).length,1,'Preview must embed exactly one branded PNG');
  const gateway=createGateway(assets);
  const response=await gateway.mcp(new Request('https://rdc.example/mcp',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({jsonrpc:'2.0',id:3,method:'resources/read',params:{uri:'ui://rdc/preview-v8.html'}})
  }),{});
  const envelope=await response.json();
  assert.equal(response.status,200);
  assert.equal(envelope.result.contents[0].text,preview);
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
  // Force the R2 path so this test models a missing legacy object, not inline D1 storage.
  const s=setup({maxInlineResultBytes:0});await s.poll({claim:false});
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
  assert.deepEqual(listing.body.result.resources.map(resource=>resource.uri),['ui://rdc/preview-v8.html']);
  for(const uri of ['ui://rdc/preview-v8.html','ui://rdc/preview-v6.html','ui://rdc/preview-v5.html','ui://rdc/preview-v4.html','ui://rdc/preview-v3.html','ui://rdc/preview-v2.html','ui://rdc/preview-v1.html']){
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


test('synced terminal fast path stays durable across one cloud dispatch',async()=>{
  const assets=JSON.parse(readFileSync(new URL('../lib/rdc-assets.json',import.meta.url),'utf8'));
  const command=assets.catalog.find(t=>t.name==='rdc_job_run');
  assert.ok(command,'Regenerate synced RDC catalog so the terminal fast path is exposed');
  assert.equal(command['x-rdc-mutating'],true);
  assert.ok(command.inputSchema.required.includes('cwd'));
  assert.ok(command.inputSchema.properties.wait_ms);
  const s=setup({},assets.catalog);
  const response=await s.gateway.mcp(
    s.request('/mcp',{jsonrpc:'2.0',id:'list',method:'tools/list'}),s.env);
  const publicCatalog=(await response.json()).result.tools;
  const advertised=publicCatalog.find(t=>t.name==='rdc_job_run');
  assert.ok(advertised);
  assert.ok(advertised.inputSchema.required.includes('_rdc_request_id'));
  await s.poll({claim:false});
  const args={argv:['/bin/echo','RDC-FAST'],cwd:'/tmp',wait_ms:1500,output_limit:4096,
    idempotency_key:'job-run-one',_rdc_request_id:'cloud-fast-one'};
  const initial=await s.mcp('rdc_job_run',args);
  assert.equal(initial.status,200);
  const id=initial.body.result.structuredContent.operation_id;
  assert.equal(initial.body.result.structuredContent.pending,true);
  const repeat=await s.mcp('rdc_job_run',args);
  assert.equal(repeat.body.result.structuredContent.operation_id,id);
  assert.equal((await s.mcp('rdc_job_run',{...args,argv:['/bin/echo','OTHER']})).status,409);
  const claimed=(await s.poll()).body.operation;
  assert.equal(claimed.operation_id,id);
  assert.deepEqual(JSON.parse(claimed.request_json),{
    name:'rdc_job_run',arguments:{argv:args.argv,cwd:args.cwd,wait_ms:args.wait_ms,
      output_limit:args.output_limit,idempotency_key:args.idempotency_key}});
  assert.equal((await s.complete(claimed,result('RDC-FAST'))).status,200);
  const received=await s.mcp('rdc_operation_status',{operation_id:id});
  assert.equal(received.body.result.structuredContent.value,'RDC-FAST');
  assert.equal((await s.poll()).body.operation,null);
});


test('fast terminal command result arrives inside first cloud tool call before deadline',async()=>{
  const assets=JSON.parse(readFileSync(new URL('../lib/rdc-assets.json',import.meta.url),'utf8'));
  const s=setup({callWaitMs:2500,pollStepMs:100},assets.catalog,
    ()=>new Promise(resolve=>setTimeout(resolve,5)));
  await s.poll({claim:false});
  const args={argv:['/bin/echo','RDC-READY'],cwd:'/tmp',wait_ms:300,
    idempotency_key:'worker-one',output_limit:4096,_rdc_request_id:'cloud-one'};
  const waiting=s.mcp('rdc_job_run',args);
  let claimed;
  for(let i=0;i<40;i++){
    const response=await s.poll();
    if(response.body.operation){claimed=response.body.operation;break}
    await new Promise(resolve=>setTimeout(resolve,2));
  }
  assert.ok(claimed,'Operation was never claimed by the simulated worker');
  const workerResult={ok:true,job:{id:'job-one',status:'completed',exit_code:0},
    reused:false,complete:true,output:{job_id:'job-one',text:'RDC-READY\n',
    status:'completed',complete:true,offset:0,next_offset:10,bytes_available:10}};
  const upload=await s.complete(claimed,{
    content:[{type:'text',text:JSON.stringify(workerResult)}],
    structuredContent:workerResult,isError:false,
  });
  assert.equal(upload.status,200);
  const first=await waiting;
  assert.equal(first.status,200);
  const body=first.body.result.structuredContent;
  assert.equal(body.ok,true);
  assert.equal(body.complete,true);
  assert.equal(body.job.id,'job-one');
  assert.equal(body.output.text,'RDC-READY\n');
  const id=claimed.operation_id;
  assert.equal(body._rdc_gateway_operation_id,id,'Completed result must expose durable gateway ID');
  assert.equal(first.body.result.content[0].text,JSON.stringify(workerResult),'Gateway metadata must not rewrite original worker content');
  const diagnostics=await s.mcp('rdc_operation_status',{operation_id:body._rdc_gateway_operation_id,diagnostics:true});
  assert.equal(diagnostics.body.result.structuredContent.operation_id,id);
  assert.equal(diagnostics.body.result.structuredContent.state,'completed');
  assert.equal((await s.mcp('rdc_operation_status',{operation_id:id,diagnostics:true},'another-owner')).status,403);
  assert.equal((await s.poll()).body.operation,null);
});

test('claimed short cloud operation detects its uploaded result before the next 500ms sweep',async()=>{
  let s,claimed,completed=false,start=0,last=0;
  const intervals=[];
  s=setup({callWaitMs:1500,pollStepMs:500},catalog,async()=>{
    const now=s.now();
    intervals.push(now-last);
    last=now;
    if(intervals.length===1){
      claimed=(await s.poll()).body.operation;
      assert.ok(claimed,'Simulated device must claim original queued operation');
    }else if(!completed){
      const uploaded=await s.complete(claimed,result('quick-completion'));
      assert.equal(uploaded.status,200);
      completed=true;
    }
  });
  await s.poll({claim:false});
  start=last=s.now();
  const reply=await s.mcp('rdc_file_write',{value:'short',_rdc_request_id:'claimed-fast-detection'});
  assert.equal(reply.status,200);
  assert.equal(reply.body.result.structuredContent.value,'quick-completion');
  assert.deepEqual(intervals,[500,100],'Only post-claim result-checking may use a faster interval');
  assert.equal(s.now()-start,600);
  assert.equal(s.env.DB.sqlite.prepare('SELECT count(*) AS n FROM gateway_operations').get().n,1);
});

test('claimed completion probes stay bounded and never increase queued idle checks',async()=>{
  let s,last=0,start=0,claimed;
  const intervals=[];
  s=setup({callWaitMs:2300,pollStepMs:500},catalog,async()=>{
    const now=s.now();
    intervals.push(now-last);
    last=now;
    if(intervals.length===1)claimed=(await s.poll()).body.operation;
  });
  await s.poll({claim:false});
  start=last=s.now();
  const pending=await s.mcp('rdc_file_write',{value:'slow',_rdc_request_id:'bounded-claimed-probes'});
  assert.equal(pending.body.result.structuredContent.pending,true);
  assert.ok(claimed);
  assert.deepEqual(intervals.slice(0,5),[500,100,100,100,500],
    'Once fast probes are exhausted the existing 500ms interval must resume');
  assert.equal(intervals.filter(ms=>ms===100).length,3);
  assert.equal(s.now()-start,2300);
  assert.equal((await s.poll()).body.operation,null,'The claimed operation must not be dispatched again');

  let queued,lastQueued=0;
  const queuedIntervals=[];
  queued=setup({callWaitMs:1500,pollStepMs:500},catalog,async()=>{
    const now=queued.now();
    queuedIntervals.push(now-lastQueued);
    lastQueued=now;
  });
  await queued.poll({claim:false});
  lastQueued=queued.now();
  const unclaimed=await queued.mcp('rdc_file_write',{value:'still queued',_rdc_request_id:'queued-no-extra-reads'});
  assert.equal(unclaimed.body.result.structuredContent.pending,true);
  assert.deepEqual(queuedIntervals,[500,500,500],'Unclaimed commands must retain all original idle poll intervals');
});

test('explicit owner-only operation diagnostics reveal transport phases without request data',async()=>{
  const s=setup();await s.poll({claim:false});
  const args={value:'private-argument-must-stay-hidden',_rdc_request_id:'diagnostic-owned-operation'};
  const queued=await s.mcp('rdc_file_write',args);
  assert.equal(queued.status,200);
  const operation_id=queued.body.result.structuredContent.operation_id;
  const catalogResponse=await s.gateway.mcp(s.request('/mcp',{jsonrpc:'2.0',id:1,method:'tools/list'}),s.env);
  const advertised=(await catalogResponse.json()).result.tools.find(x=>x.name==='rdc_operation_status');
  assert.equal(advertised.inputSchema.properties.diagnostics.type,'boolean');

  s.advance(375);
  const waiting=await s.mcp('rdc_operation_status',{operation_id,diagnostics:true});
  assert.equal(waiting.status,200);
  assert.deepEqual(waiting.body.result.structuredContent,{
    ok:true,diagnostics:true,operation_id,tool:'rdc_file_write',state:'queued',
    elapsed_ms:375,queue_age_ms:375,queue_wait_ms:null,inflight_age_ms:null,
    claim_to_result_ms:null,completed_age_ms:null
  });
  assert.ok(!JSON.stringify(waiting.body).includes(args.value),'Never reveal queued request arguments');
  assert.equal((await s.mcp('rdc_operation_status',{operation_id,diagnostics:true},'another-user')).status,403);

  const op=(await s.poll()).body.operation;
  assert.equal(op.operation_id,operation_id);
  s.advance(80);
  assert.equal((await s.complete(op,result('done'))).status,200);
  s.advance(15);
  const finished=await s.mcp('rdc_operation_status',{operation_id,diagnostics:true});
  assert.ok(!JSON.stringify(finished.body).includes('private-argument-must-stay-hidden'));
  assert.ok(!JSON.stringify(finished.body).includes('done'),'Diagnostic status must not fetch stored worker results');
  assert.deepEqual(finished.body.result.structuredContent,{
    ok:true,diagnostics:true,operation_id,tool:'rdc_file_write',state:'completed',
    elapsed_ms:470,queue_age_ms:null,queue_wait_ms:375,inflight_age_ms:null,
    claim_to_result_ms:80,completed_age_ms:15
  });
  assert.equal((await s.mcp('rdc_operation_status',{operation_id})).body.result.structuredContent.value,'done');
});

test('cloud diagnostics reject invalid switches without altering operation recovery',async()=>{
  const s=setup();await s.poll({claim:false});
  const queued=await s.mcp('rdc_file_write',{value:'x',_rdc_request_id:'diagnostics-validation'});
  const operation_id=queued.body.result.structuredContent.operation_id;
  for(const diagnostics of ['true',1,null,{},[]]){
    const denied=await s.mcp('rdc_operation_status',{operation_id,diagnostics});
    assert.equal(denied.status,400);
    assert.equal(denied.body.error.data.code,'invalid_arguments');
  }
  const ordinary=await s.mcp('rdc_operation_status',{operation_id});
  assert.equal(ordinary.body.result.structuredContent.pending,true);
  assert.equal((await s.poll()).body.operation.operation_id,operation_id);
});

test('bounded small terminal results complete and recover entirely in D1 without R2 reads or puts',async()=>{
  const s=setup({resultTtlMs:1000});
  await s.poll({claim:false});
  const queued=await s.mcp('rdc_file_write',{value:'keep private',_rdc_request_id:'inline-small-one'});
  const id=queued.body.result.structuredContent.operation_id;
  const claimed=(await s.poll()).body.operation;
  const output={content:[{type:'text',text:'fast-terminal-output'}],structuredContent:{ok:true,value:'fast-terminal-output'},isError:false};
  const raw=JSON.stringify(output);
  assert.ok(Buffer.byteLength(raw)<8192);
  assert.equal((await s.complete(claimed,output)).body.duplicate,false);
  assert.equal(s.env.BUCKET.puts,0,'Bounded small result should avoid the R2 PUT');
  assert.equal(s.env.BUCKET.gets,0,'Bounded small result should not need an R2 GET');
  const row=s.env.DB.sqlite.prepare('SELECT * FROM gateway_operations WHERE id=?').get(id);
  assert.equal(row.result_key,null);
  assert.equal(row.result_inline_json,raw);
  assert.equal(row.result_size,Buffer.byteLength(raw));
  assert.equal(row.request_json,null,'Request arguments must still be purged after completion');
  const status=await s.mcp('rdc_operation_status',{operation_id:id});
  assert.deepEqual(status.body.result.structuredContent,{...output.structuredContent,_rdc_gateway_operation_id:id});
  assert.deepEqual(status.body.result.content,output.content);
  assert.equal((await s.mcp('rdc_operation_status',{operation_id:id},'other-user')).status,403);
  const diagnostic=await s.mcp('rdc_operation_status',{operation_id:id,diagnostics:true});
  assert.equal(diagnostic.body.result.structuredContent.state,'completed');
  assert.ok(!JSON.stringify(diagnostic.body).includes('fast-terminal-output'),'Diagnostics must never leak result payloads');
  assert.equal((await s.complete(claimed,output)).body.duplicate,true);
  assert.equal((await s.complete(claimed,{...output,structuredContent:{ok:true,value:'different'}})).status,409);
  assert.equal(s.env.BUCKET.gets,0);
  assert.equal(s.env.BUCKET.puts,0);
  assert.equal((await s.poll()).body.operation,null,'Completed mutation must not be claimed again');
  s.advance(900);await s.poll({claim:false});
  assert.equal(s.env.DB.sqlite.prepare('SELECT result_inline_json FROM gateway_operations WHERE id=?').get(id).result_inline_json,raw,
    'Inline data must remain until the original TTL');
  s.advance(101);await s.poll({claim:false});
  const retired=s.env.DB.sqlite.prepare('SELECT * FROM gateway_operations WHERE id=?').get(id);
  assert.equal(retired.result_inline_json,null,'Expired inline payload must be purged');
  assert.equal(retired.result_key,null);
  assert.equal(retired.result_size,0);
  assert.equal(s.env.BUCKET.deletes,0,'Inline cleanup must not attempt an R2 object deletion');
  assert.equal(retired.state,'completed');
  assert.equal((await s.mcp('rdc_operation_status',{operation_id:id})).body.result.structuredContent.error.code,'result_expired');
});

test('R2 fallback still stores oversized responses and their old records remain recoverable',async()=>{
  const s=setup({maxInlineResultBytes:8192});
  await s.poll({claim:false});
  const queued=await s.mcp('rdc_file_write',{value:'legacy fallback',_rdc_request_id:'r2-oversized-one'});
  const op=(await s.poll()).body.operation;
  assert.equal(op.operation_id,queued.body.result.structuredContent.operation_id,'The original queued operation must be claimed');
  const large={content:[{type:'text',text:'X'.repeat(10000)}],structuredContent:{ok:true,large:true}};
  assert.ok(Buffer.byteLength(JSON.stringify(large))>8192);
  assert.equal((await s.complete(op,large)).body.duplicate,false);
  assert.equal(s.env.BUCKET.puts,1,'Large responses must still use R2');
  const row=s.env.DB.sqlite.prepare('SELECT * FROM gateway_operations WHERE id=?').get(op.operation_id);
  assert.equal(row.result_inline_json,null);
  assert.match(row.result_key,/^rdc-results\//);
  const status=await s.mcp('rdc_operation_status',{operation_id:op.operation_id});
  assert.equal(status.body.result.content[0].text.length,10000);
  assert.equal(status.body.result.structuredContent.large,true);
  assert.equal((await s.complete(op,large)).body.duplicate,true);
  assert.equal(s.env.BUCKET.puts,1,'Duplicate result must not re-upload to R2');
  assert.equal((await s.poll()).body.operation,null);
});

test('additive inline migration retains queued rows and legacy R2 references',()=>{
  const db=new DatabaseSync(':memory:');
  db.exec(readFileSync(new URL('../drizzle/0000_high_fantastic_four.sql',import.meta.url),'utf8'));
  db.prepare(`INSERT INTO gateway_operations
    (id,principal,device_id,request_key,tool,request_json,request_sha256,request_size,mutating,state,created_ms,expires_ms,
     claimed_ms,completed_ms,result_key,result_sha256,result_size,result_expires_ms)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`).run(
      'legacy-id','owner-1',DEVICE,'legacy-request','rdc_job_run',null,'digest-request',0,1,'completed',100,600,
      150,200,'rdc-results/legacy.json','digest-result',512,3600000
    );
  db.exec(readFileSync(new URL('../drizzle/0001_condemned_clint_barton.sql',import.meta.url),'utf8'));
  const rows=db.prepare('SELECT * FROM gateway_operations').all();
  assert.equal(rows.length,1);
  assert.equal(rows[0].id,'legacy-id');
  assert.equal(rows[0].state,'completed');
  assert.equal(rows[0].result_key,'rdc-results/legacy.json');
  assert.equal(rows[0].result_sha256,'digest-result');
  assert.equal(rows[0].result_inline_json,null,'New nullable column must preserve legacy rows');
  assert.equal(rows[0].result_size,512);
  db.close();
});


// Scoped v17 acceptance: these tests do not migrate or deploy any real Site.
function exactUtf8Result(size,multibyte){
  const output={content:[{type:'text',text:''}],structuredContent:{ok:true,payload:'size-probe'},isError:false};
  const emptySize=Buffer.byteLength(JSON.stringify(output),'utf8');
  const remaining=size-emptySize;
  assert.ok(remaining>20,'The fixture must leave a positive payload budget');
  const text=multibyte?'界'.repeat(Math.floor(remaining/3))+
    (remaining%3===2?'é':remaining%3===1?'a':''):'A'.repeat(remaining);
  output.content[0].text=text;
  assert.equal(Buffer.byteLength(JSON.stringify(output),'utf8'),size,'Fixture must hit the exact UTF-8 JSON byte boundary');
  if(multibyte)assert.ok([...text].some(character=>character.codePointAt(0)>127),'Fixture must contain genuine multibyte text');
  return output;
}

for(const size of [8192,8193]){
  for(const multibyte of [false,true]){
    test('UTF-8 full JSON result '+size+' bytes '+(multibyte?'multibyte':'ASCII')+' honors inline/R2 and TTL',async()=>{
      const s=setup({maxInlineResultBytes:8192,resultTtlMs:1000});
      await s.poll({claim:false});
      const args={value:'size-'+size+(multibyte?'-multibyte':'-ascii'),
        _rdc_request_id:'boundary-'+size+(multibyte?'-multi':'-ascii')};
      const queued=await s.mcp('rdc_file_write',args);
      const op=(await s.poll()).body.operation;
      assert.equal(op.operation_id,queued.body.result.structuredContent.operation_id);
      const output=exactUtf8Result(size,multibyte),original=JSON.stringify(output);
      const uploaded=await s.complete(op,output);
      assert.equal(uploaded.status,200);
      assert.equal(uploaded.body.duplicate,false);
      const stored=s.env.DB.sqlite.prepare('SELECT * FROM gateway_operations WHERE id=?').get(op.operation_id);
      assert.equal(stored.result_size,size,'Stored size must use UTF-8 bytes');
      if(size===8192){
        assert.equal(stored.result_inline_json,original);
        assert.equal(stored.result_key,null);
        assert.equal(s.env.BUCKET.puts,0);
      }else{
        assert.equal(stored.result_inline_json,null);
        assert.match(stored.result_key,/^rdc-results\//);
        assert.equal(s.env.BUCKET.puts,1);
      }
      const read=await s.mcp('rdc_operation_status',{operation_id:op.operation_id});
      assert.equal(read.status,200);
      assert.deepEqual(read.body.result.content,output.content);
      assert.equal(read.body.result.structuredContent._rdc_gateway_operation_id,op.operation_id);
      assert.equal((await s.mcp('rdc_operation_status',{operation_id:op.operation_id},'wrong-owner')).status,403);
      assert.equal((await s.complete(op,output)).body.duplicate,true,'Original result upload remains idempotent');
      assert.equal((await s.poll()).body.operation,null,'No duplicate worker dispatch');
      s.advance(999);
      await s.poll({claim:false});
      const still=await s.mcp('rdc_operation_status',{operation_id:op.operation_id});
      assert.deepEqual(still.body.result.content,output.content,'Result remains available until TTL');
      s.advance(2);
      await s.poll({claim:false});
      const expired=await s.mcp('rdc_operation_status',{operation_id:op.operation_id});
      assert.equal(expired.body.result.structuredContent.error.code,'result_expired');
      const retired=s.env.DB.sqlite.prepare('SELECT state,result_key,result_inline_json FROM gateway_operations WHERE id=?').get(op.operation_id);
      assert.equal(retired.state,'completed','Expiration must not allow replay');
      assert.equal(retired.result_key,null);
      assert.equal(retired.result_inline_json,null);
      assert.equal((await s.mcp('rdc_file_write',args)).body.result.structuredContent.error.code,'result_expired',
        'Identical mutation ID stays terminal after its response TTL');
      assert.equal((await s.poll()).body.operation,null,'TTL must not redispatch a mutation');
    });
  }
}

test('forged worker gateway-operation metadata never overrides authoritative identity',async()=>{
  const s=setup();
  await s.poll({claim:false});
  const args={value:'owner-only-identity',_rdc_request_id:'hostile-worker-metadata'};
  const pending=await s.mcp('rdc_file_write',args);
  const op=(await s.poll()).body.operation;
  const fake='00000000-0000-4000-8000-000000000066';
  const submitted={content:[{type:'text',text:'worker-result'}],
    structuredContent:{ok:true,answer:'worker-result',_rdc_gateway_operation_id:fake},
    _meta:{'rdc/operation_id':fake},isError:false};
  assert.equal((await s.complete(op,submitted)).status,200);
  const dbrow=s.env.DB.sqlite.prepare('SELECT result_inline_json FROM gateway_operations WHERE id=?').get(op.operation_id);
  assert.equal(dbrow.result_inline_json,JSON.stringify(submitted),
    'The gateway must preserve the authentic worker upload for digest/idempotency checks');
  const first=await s.mcp('rdc_operation_status',{operation_id:op.operation_id});
  assert.equal(first.body.result.structuredContent._rdc_gateway_operation_id,op.operation_id);
  assert.equal(first.body.result._meta['rdc/operation_id'],op.operation_id);
  assert.equal(first.body.result.structuredContent.answer,'worker-result');
  assert.deepEqual(first.body.result.content,submitted.content);
  const retry=await s.mcp('rdc_file_write',args);
  assert.equal(retry.body.result.structuredContent._rdc_gateway_operation_id,op.operation_id);
  assert.equal(retry.body.result._meta['rdc/operation_id'],op.operation_id);
  assert.equal((await s.complete(op,submitted)).body.duplicate,true);
  assert.equal((await s.mcp('rdc_operation_status',{operation_id:op.operation_id},'other-owner')).status,403);
  const phases=await s.mcp('rdc_operation_status',{operation_id:op.operation_id,diagnostics:true});
  assert.equal(phases.body.result.structuredContent.operation_id,op.operation_id);
  assert.equal((await s.poll()).body.operation,null);
  assert.equal(pending.body.result.structuredContent.operation_id,op.operation_id);
});

test('rollback-compatible reader preserves v17 inline and v16 R2 results and TTL without replay',async()=>{
  const s=setup({resultTtlMs:1000,maxInlineResultBytes:8192});
  await s.poll({claim:false});
  const args={value:'unchanged-mutation',_rdc_request_id:'v17-before-compatible-rollback'};
  const queued=await s.mcp('rdc_file_write',args);
  const original=(await s.poll()).body.operation;
  assert.equal(queued.body.result.structuredContent.operation_id,original.operation_id);
  const resultBody={content:[{type:'text',text:'preserve-content'}],
    structuredContent:{ok:true,answer:'preserve-content'},isError:false};
  assert.equal((await s.complete(original,resultBody)).status,200);
  const originalRow=s.env.DB.sqlite.prepare('SELECT * FROM gateway_operations WHERE id=?').get(original.operation_id);
  assert.equal(originalRow.result_key,null);
  assert.ok(originalRow.result_inline_json);
  // Exact original-v16 logic was a key-only read/cleanup. That deployment
  // would report result_expired for this intact v17 inline response.
  const v16KeyOnlyRead=originalRow.result_key===null?'result_expired':'r2_result';
  const oldV16CleanupEligible=originalRow.result_key!==null&&originalRow.result_expires_ms<=s.now();
  assert.equal(v16KeyOnlyRead,'result_expired');
  assert.equal(oldV16CleanupEligible,false,'The original v16 cleanup ignores inline TTL');

  const rollback=GatewayCore.createRollbackCompatibleGateway({
    catalog,resourceHtml:'<!doctype html><html>Existing private preview</html>',
    iconDataUri:'data:image/png;base64,eA==',clock:s.now,
    limits:{callWaitMs:0,pollWaitMs:0,resultTtlMs:1000,maxInlineResultBytes:8192}
  });
  const compatibleCall=async(name,arguments_={},owner='owner-1')=>{
    const request=s.request('/mcp',{jsonrpc:'2.0',id:'compat',method:'tools/call',params:{name,arguments:arguments_}},
      owner?{'oai-authenticated-user-id':owner}:{});
    const response=await rollback.mcp(request,s.env);
    return {status:response.status,body:await response.json()};
  };
  const compatiblePoll=async(body={claim:false})=>{
    const response=await rollback.poll(s.request('/device/poll',{device_id:DEVICE,...body},
      {'X-RDC-Device-Key':KEY}),s.env);
    return {status:response.status,body:await response.json()};
  };
  const compatibleComplete=async(op,output)=>{
    const response=await rollback.result(s.request('/device/result',{
      device_id:DEVICE,operation_id:op.operation_id,claim_id:op.claim_id,
      request_sha256:op.request_sha256,result_json:JSON.stringify(output)
    },{'X-RDC-Device-Key':KEY}),s.env);
    return {status:response.status,body:await response.json()};
  };
  const recovered=await compatibleCall('rdc_operation_status',{operation_id:original.operation_id});
  assert.equal(recovered.status,200);
  assert.deepEqual(recovered.body.result.content,resultBody.content);
  assert.equal(recovered.body.result.structuredContent.answer,resultBody.structuredContent.answer);
  assert.equal(recovered.body.result.structuredContent._rdc_gateway_operation_id,original.operation_id);
  assert.equal((await compatibleCall('rdc_operation_status',{operation_id:original.operation_id},'stranger')).status,403);
  const sameMutation=await compatibleCall('rdc_file_write',args);
  assert.equal(sameMutation.body.result.structuredContent._rdc_gateway_operation_id,original.operation_id,
    'Rollback reader must recover the exact committed operation, not dispatch again');
  assert.equal((await compatiblePoll()).body.operation,null);
  s.advance(999);
  await compatiblePoll();
  assert.deepEqual((await compatibleCall('rdc_operation_status',{operation_id:original.operation_id})).body.result.content,
    resultBody.content,'Inline payload remains readable through compatible rollback until TTL');
  s.advance(2);
  const overdue=s.env.DB.sqlite.prepare('SELECT result_key,result_inline_json,result_expires_ms FROM gateway_operations WHERE id=?').get(original.operation_id);
  assert.ok(overdue.result_expires_ms<=s.now());
  assert.equal(overdue.result_key,null);
  assert.ok(overdue.result_inline_json,'The old v16 key-only cleanup would leave this overdue inline response');
  assert.equal(overdue.result_key!==null&&overdue.result_expires_ms<=s.now(),false,
    'Actual v16 key-only cleanup predicate fails even after inline TTL');
  await compatiblePoll();
  const retired=s.env.DB.sqlite.prepare('SELECT state,result_inline_json,result_key FROM gateway_operations WHERE id=?').get(original.operation_id);
  assert.equal(retired.state,'completed');
  assert.equal(retired.result_inline_json,null,'Compatible cleanup purges expired inline content');
  assert.equal(retired.result_key,null);
  assert.equal(s.env.BUCKET.deletes,0,'No R2 delete is issued for null inline-only key');
  const expired=await compatibleCall('rdc_operation_status',{operation_id:original.operation_id});
  assert.equal(expired.body.result.structuredContent.error.code,'result_expired');
  assert.equal((await compatibleCall('rdc_file_write',args)).body.result.structuredContent.error.code,'result_expired');
  assert.equal((await compatiblePoll()).body.operation,null);

  // After rollback, the compatibility writer must never introduce more
  // unreadable D1-inline results; it always writes original-v16-readable R2.
  const postArgs={value:'written-after-rollback',_rdc_request_id:'rollback-post-write'};
  const newQueued=await compatibleCall('rdc_file_write',postArgs);
  const newOp=(await compatiblePoll({claim:true})).body.operation;
  assert.equal(newQueued.body.result.structuredContent.operation_id,newOp.operation_id);
  assert.equal((await compatibleComplete(newOp,resultBody)).status,200);
  const r2row=s.env.DB.sqlite.prepare('SELECT * FROM gateway_operations WHERE id=?').get(newOp.operation_id);
  assert.equal(r2row.result_inline_json,null,'Compatible writer must not create new inline rows');
  assert.match(r2row.result_key,/^rdc-results\//);
  assert.equal(s.env.BUCKET.puts,1);
  const readR2=await compatibleCall('rdc_operation_status',{operation_id:newOp.operation_id});
  assert.deepEqual(readR2.body.result.content,resultBody.content);
  assert.equal(readR2.body.result.structuredContent._rdc_gateway_operation_id,newOp.operation_id);
  assert.equal((await compatibleComplete(newOp,resultBody)).body.duplicate,true);
  assert.equal((await compatiblePoll({claim:true})).body.operation,null);
  s.advance(1001);
  await compatiblePoll();
  assert.equal(s.env.BUCKET.deletes,1,'R2 payload TTL is enforced under compatible rollback');
  const expiredR2=await compatibleCall('rdc_operation_status',{operation_id:newOp.operation_id});
  assert.equal(expiredR2.body.result.structuredContent.error.code,'result_expired');
  assert.equal((await compatibleCall('rdc_file_write',postArgs)).body.result.structuredContent.error.code,'result_expired');
  assert.equal((await compatiblePoll({claim:true})).body.operation,null);
});


test('historical v16 gateway executable reproduces the real inline rollback failure and legacy cleanup gap',async()=>{
  // Use the precise source of the deployed v16 reader, locked by hash.
  // This regression must fail if the historical fixture is absent or edited.
  const fixtureUrl=new URL('./fixtures/rdc-gateway-core-v16.mjs',import.meta.url);
  const historicalSource=readFileSync(fixtureUrl,'utf8');
  assert.equal(createHash('sha256').update(historicalSource).digest('hex'),
    '5651f14c6fc8a7308f37a5454a006ec2b0fb459aae97997554a8d296f160cd4f');
  const {createGateway:createHistoricalV16}=await import('./fixtures/rdc-gateway-core-v16.mjs');
  const s=setup({resultTtlMs:1000,maxInlineResultBytes:8192});
  await s.poll({claim:false});
  const args={value:'historical-v16-inline',_rdc_request_id:'historical-v16-no-replay'};
  const first=await s.mcp('rdc_file_write',args);
  const op=(await s.poll()).body.operation;
  assert.equal(first.body.result.structuredContent.operation_id,op.operation_id);
  const output={content:[{type:'text',text:'safely-retained'}],structuredContent:{ok:true,value:'safely-retained'}};
  assert.equal((await s.complete(op,output)).status,200);
  const initial=s.env.DB.sqlite.prepare('SELECT result_key,result_inline_json FROM gateway_operations WHERE id=?').get(op.operation_id);
  assert.equal(initial.result_key,null);
  assert.equal(initial.result_inline_json,JSON.stringify(output));

  const options={catalog,resourceHtml:'<!doctype html><html>Historical resource</html>',
    iconDataUri:'data:image/png;base64,eA==',clock:s.now,
    limits:{callWaitMs:0,pollWaitMs:0,resultTtlMs:1000}};
  const old=createHistoricalV16(options);
  const request=s.request('/mcp',{jsonrpc:'2.0',id:'historical',method:'tools/call',
    params:{name:'rdc_operation_status',arguments:{operation_id:op.operation_id}}},
    {'oai-authenticated-user-id':'owner-1'});
  const v16Read=await old.mcp(request,s.env);
  const v16Body=await v16Read.json();
  assert.equal(v16Read.status,200);
  assert.equal(v16Body.result.structuredContent.error.code,'result_expired',
    'Actual original v16 reader loses authorized readback of a still-retained inline result');
  assert.equal((await s.mcp('rdc_operation_status',{operation_id:op.operation_id})).body.result.content[0].text,
    'safely-retained','v17 confirms payload exists before expiry');

  s.advance(1001);
  const oldPoll=await old.poll(s.request('/device/poll',{device_id:DEVICE,claim:false},
    {'X-RDC-Device-Key':KEY}),s.env);
  assert.equal(oldPoll.status,200);
  const stale=s.env.DB.sqlite.prepare('SELECT result_inline_json FROM gateway_operations WHERE id=?').get(op.operation_id);
  assert.equal(stale.result_inline_json,JSON.stringify(output),
    'Actual historical v16 cleanup skips expired inline-only results');

  const safe=GatewayCore.createRollbackCompatibleGateway(options);
  const safePoll=await safe.poll(s.request('/device/poll',{device_id:DEVICE,claim:false},
    {'X-RDC-Device-Key':KEY}),s.env);
  assert.equal(safePoll.status,200);
  const cleaned=s.env.DB.sqlite.prepare('SELECT state,result_inline_json FROM gateway_operations WHERE id=?').get(op.operation_id);
  assert.equal(cleaned.state,'completed');
  assert.equal(cleaned.result_inline_json,null);
  assert.equal(s.env.BUCKET.deletes,0,'No null-key R2 delete on inline TTL');
  assert.equal((await s.mcp('rdc_file_write',args)).body.result.structuredContent.error.code,'result_expired');
  assert.equal((await s.poll()).body.operation,null,'Original terminal mutation can never be dispatched again');
});


test('RDC chat session status uses platform metadata but does not guess project membership',async()=>{
  const s=setup();s.env.RDC_CHAT_IDENTITY_SECRET='test-hmac-secret-that-is-long-enough-and-internal-only';
  const toolCall=async(meta,args={},owner='owner-1')=>{
    const r=await s.gateway.mcp(s.request('/mcp',{
      jsonrpc:'2.0',id:'chat-context',method:'tools/call',
      params:{name:'rdc_chat_session_status',arguments:args,...(meta===undefined?{}:{_meta:meta})}
    },owner?{'oai-authenticated-user-id':owner}:{}),s.env);
    return {status:r.status,payload:await r.json()};
  };
  const list=await s.gateway.mcp(s.request('/mcp',{jsonrpc:'2.0',id:'list-chat',method:'tools/list'}),s.env);
  const spec=(await list.json()).result.tools.find(x=>x.name==='rdc_chat_session_status');
  assert.ok(spec,'The gateway must advertise the read-only session diagnostic tool');
  assert.equal(spec.annotations.readOnlyHint,true);
  const meta={'openai/subject':'anonymous-person','openai/session':'conversation-A'};
  const first=await toolCall(meta);
  assert.equal(first.status,200);
  const data=first.payload.result.structuredContent;
  assert.equal(data.ok,true);
  assert.equal(data.available,true);
  assert.equal(data.chat_project_verified,false);
  assert.equal(data.can_create,false);
  assert.equal(data.can_wake,false);
  assert.equal(data.can_send,false);
  assert.match(data.opaque_session_id,/^chatgpt-[0-9a-f]{40}$/);
  assert.equal(JSON.stringify(first).includes('anonymous-person'),false);
  assert.equal(JSON.stringify(first).includes('conversation-A'),false);
  const again=(await toolCall(meta)).payload.result.structuredContent;
  assert.equal(again.opaque_session_id,data.opaque_session_id);
  const other=(await toolCall({...meta,'openai/session':'conversation-B'})).payload.result.structuredContent;
  assert.notEqual(other.opaque_session_id,data.opaque_session_id);
  assert.equal((await toolCall(meta,{project_id:'untrusted-claim'})).status,400);
  assert.equal((await toolCall(meta,{},'foreign-owner')).status,403);
  assert.equal((await toolCall(meta,{},null)).status,401);
});
test('RDC chat session status fails closed if metadata or private HMAC key is unavailable',async()=>{
  const s=setup();
  const call=async(meta)=>{
    const r=await s.gateway.mcp(s.request('/mcp',{jsonrpc:'2.0',id:'ctx',
      method:'tools/call',params:{name:'rdc_chat_session_status',arguments:{},
      ...(meta===undefined?{}:{_meta:meta})}}, {'oai-authenticated-user-id':'owner-1'}),s.env);
    return {status:r.status,value:(await r.json()).result?.structuredContent};
  };
  const noKey=await call({'openai/subject':'user','openai/session':'one'});
  assert.equal(noKey.status,200);
  assert.equal(noKey.value.available,false);
  assert.equal(noKey.value.reason,'IDENTITY_KEY_UNAVAILABLE');
  s.env.RDC_CHAT_IDENTITY_SECRET='this-key-is-strong-enough-for-the-test-only-source';
  const noMeta=await call(undefined);
  assert.equal(noMeta.status,200);
  assert.equal(noMeta.value.available,false);
  assert.equal(noMeta.value.reason,'CHAT_CONTEXT_UNAVAILABLE');
  const incomplete=await call({'openai/subject':'user'});
  assert.equal(incomplete.value.available,false);
  assert.equal(incomplete.value.reason,'CHAT_CONTEXT_UNAVAILABLE');
});

test('ChatGPT communication tool catalog is callable but denies enrollment when bridge is missing',async()=>{
  const s=setup();
  const list=await s.gateway.mcp(s.request('/mcp',{jsonrpc:'2.0',id:'list-bridge',method:'tools/list'}),s.env);
  const tools=(await list.json()).result.tools;
  const expected=['rdc_chat_inbox','rdc_chat_send','rdc_chat_reply','rdc_chat_ack',
    'rdc_chat_create','rdc_chat_wake','rdc_chat_cross_project_send','rdc_chat_route_status'];
  for(const name of expected)assert.ok(tools.some(x=>x.name===name),'missing '+name);
  const call=async(name,args)=>{
    const response=await s.gateway.mcp(s.request('/mcp',{
      jsonrpc:'2.0',id:'unavailable',method:'tools/call',
      params:{name,arguments:args,_meta:{'openai/subject':'test-owner','openai/session':'synthetic-chat'}}
    },{'oai-authenticated-user-id':'owner-1'}),s.env);
    return {status:response.status,body:await response.json()};
  };
  const absent=await call('rdc_chat_inbox',{limit:4});
  assert.equal(absent.status,200);
  assert.equal(absent.body.result.isError,true);
  assert.equal(absent.body.result.structuredContent.error.code,'chat_bridge_not_enrolled');
  assert.equal(s.env.DB.sqlite.prepare('SELECT COUNT(*) n FROM gateway_operations').get().n,0);
  const noKey=await call('rdc_chat_send',{target_session:'verified-B',text:'Hello'});
  assert.equal(noKey.status,400);
  const fakeSource=await call('rdc_chat_send',{target_session:'verified-B',text:'Hello',
    source_project:'atlas',_rdc_request_id:'stable-1'});
  assert.equal(fakeSource.status,400);
});

test('Authenticated host adapter receives exact sender metadata and stable request IDs, not model-supplied identity',async()=>{
  const records=[];
  const adapter={async invoke(call){
    records.push(call);
    return {ok:true,receipt:{message_id:'fixture-receipt-1',state:'QUEUED'}};
  }};
  const s=setup({},catalog,async()=>{},adapter);
  const body={jsonrpc:'2.0',id:'host-accepted',method:'tools/call',
    params:{name:'rdc_chat_send',arguments:{target_session:'bound-recipient',text:'Send update',
      _rdc_request_id:'one-idempotent-request'},
      _meta:{'openai/subject':'owner-scope','openai/session':'chat-A'}}};
  const response=await s.gateway.mcp(s.request('/mcp',body,{'oai-authenticated-user-id':'owner-1'}),s.env);
  const parsed=await response.json();
  assert.equal(response.status,200);
  assert.equal(parsed.result.structuredContent.receipt.state,'QUEUED');
  assert.equal(records.length,1);
  assert.equal(records[0].name,'rdc_chat_send');
  assert.equal(records[0].request_key,'one-idempotent-request');
  assert.equal(records[0].principal,'owner-1');
  assert.equal(records[0].meta['openai/session'],'chat-A');
  assert.equal(records[0].args.target_session,'bound-recipient');
  assert.equal(records[0].args._rdc_request_id,undefined);
  assert.equal(s.env.DB.sqlite.prepare('SELECT COUNT(*) n FROM gateway_operations').get().n,0);
});

test('Independent Atlas routing cannot be enabled by model arguments or an unavailable broker',async()=>{
  const requested=[];
  let independentlyApproved=false;
  const adapter={async invoke(call){
    requested.push(call);
    if(call.name==='rdc_chat_cross_project_send' && !independentlyApproved){
      return {ok:false,error:{code:'cross_project_denied',message:'Independent Atlas grant absent'}};
    }
    return {ok:true,receipt:{state:'QUEUED',message_id:'route-fixture-id'}};
  }};
  const s=setup({},catalog,async()=>{},adapter);
  const doRoute=async(args)=>{
    const response=await s.gateway.mcp(s.request('/mcp',{
      jsonrpc:'2.0',id:'cross',method:'tools/call',
      params:{name:'rdc_chat_cross_project_send',arguments:args,
        _meta:{'openai/subject':'owner','openai/session':'session-A'}}
    },{'oai-authenticated-user-id':'owner-1'}),s.env);
    return {status:response.status,result:(await response.json()).result};
  };
  const fields={target_project:'bandmates',target_session:'bandmates-session',
    text:'Request status',_rdc_request_id:'cross-1'};
  const denied=await doRoute(fields);
  assert.equal(denied.status,200);
  assert.equal(denied.result.isError,true);
  assert.equal(denied.result.structuredContent.error.code,'cross_project_denied');
  const spoof=await doRoute({...fields,authorized:true});
  assert.equal(spoof.status,400);
  independentlyApproved=true;
  const ready=await doRoute({...fields,_rdc_request_id:'cross-2'});
  assert.equal(ready.result.isError,false);
  assert.equal(ready.result.structuredContent.receipt.state,'QUEUED');
  assert.equal(requested.length,2);
});

test('saturated retained read-only journal recovers at admission without erasing mutation identity',async()=>{
  const s=setup({maxOperations:2,resultTtlMs:1000,frameOperationTtlMs:5000});
  await s.poll({claim:false});
  const mutation=await s.mcp('rdc_file_write',{value:'preserve',_rdc_request_id:'capacity-mutation'});
  const first=(await s.poll()).body.operation;
  await s.complete(first,result('write completed'));
  const observation=await s.mcp('rdc_system_status',{_rdc_request_id:'capacity-observation'});
  const read=(await s.poll()).body.operation;
  await s.complete(read,result('read completed'));
  assert.equal(s.env.DB.sqlite.prepare('SELECT COUNT(*) n FROM gateway_operations').get().n,2);
  s.advance(1001);
  const next=await s.mcp('rdc_system_status',{_rdc_request_id:'capacity-new-read'});
  assert.equal(next.status,200);
  assert.equal(next.body.result.structuredContent.pending,true);
  assert.ok((await s.poll()).body.operation);
  const original=await s.mcp('rdc_file_write',{value:'preserve',_rdc_request_id:'capacity-mutation'});
  assert.equal(original.body.result.structuredContent.error.code,'result_expired');
  assert.equal(original.body.result.structuredContent.operation_id,first.operation_id);
  assert.equal(s.env.DB.sqlite.prepare("SELECT COUNT(*) n FROM gateway_operations WHERE mutating=1").get().n,1);
  assert.equal(s.env.DB.sqlite.prepare('SELECT COUNT(*) n FROM gateway_operations').get().n,2);
  assert.equal(observation.status,200);
  assert.equal(mutation.status,200);
});

test('capacity recovery preserves unexpired read-only results and unknown mutations',async()=>{
  const s=setup({maxOperations:1,resultTtlMs:60000});
  await s.poll({claim:false});
  const first=await s.mcp('rdc_system_status',{_rdc_request_id:'fresh-read'});
  const op=(await s.poll()).body.operation;
  await s.complete(op,result('retain recent read'));
  const busy=await s.mcp('rdc_system_status',{_rdc_request_id:'blocked-read'});
  assert.equal(busy.body.result.structuredContent.error.code,'gateway_busy');
  assert.equal((await s.mcp('rdc_operation_status',{operation_id:op.operation_id})).body.result.structuredContent.value,'retain recent read');
  assert.equal(first.status,200);
});
