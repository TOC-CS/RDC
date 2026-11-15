import assert from 'node:assert/strict';
import { test } from 'node:test';
import { DatabaseSync } from 'node:sqlite';
import { readFileSync, readdirSync } from 'node:fs';
import { createGateway } from '../lib/rdc-gateway-core.mjs';

const DEVICE = '00000000-0000-4000-8000-000000000001';
const KEY = 'test-device-key-with-at-least-thirty-two-bytes';
const plainTool = (name, mutating=false) => ({name, description:'Test tool', inputSchema:{type:'object', properties:{value:{type:'string'}}, additionalProperties:false}, annotations:{readOnlyHint:!mutating}, 'x-rdc-mutating':mutating});
const catalog = [plainTool('rdc_system_status'), plainTool('rdc_file_write',true), plainTool('rdc_preview_frame')];
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
  return {env,gateway,request,mcp,poll,complete,advance:ms=>now+=ms};
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
  assert.equal(expired.body.result.structuredContent.error.code,'result_expired');
  assert.equal(s.env.BUCKET.objects.size,0);
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

test('backlog and body limits reject work before dispatch',async()=>{
  const s=setup({maxBacklog:1});await s.poll({claim:false});
  assert.equal((await s.mcp('rdc_file_write',{value:'x'})).status,400);
  await s.mcp('rdc_system_status',{});
  assert.equal((await s.mcp('rdc_system_status',{})).body.result.structuredContent.error.code,'gateway_busy');
  const request=s.request('/device/result',{device_id:DEVICE,result_json:'A'.repeat(13*1024*1024)},{'X-RDC-Device-Key':KEY});
  assert.equal((await s.gateway.result(request,s.env)).status,413);
});
