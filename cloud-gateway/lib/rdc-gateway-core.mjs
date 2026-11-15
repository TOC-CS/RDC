/* Authenticated outbound relay. The device remains the authority for grants.
 * Queued operations are claimed once; uncertainty never causes redispatch.
 */
const UI_URI='ui://rdc/preview-v1.html';
const UI_MIME='text/html;profile=mcp-app';
const UI_EXTENSION='io.modelcontextprotocol/ui';
const encoder=new TextEncoder();
const DEFAULTS={callWaitMs:20_000,previewWaitMs:8_000,pollWaitMs:10_000,pollStepMs:500,
  queueTtlMs:30_000,onlineMs:35_000,unknownMs:120_000,operationTtlMs:86_400_000,
  resultTtlMs:3_600_000,frameTtlMs:30_000,frameOperationTtlMs:60_000,maxBacklog:32,maxOperations:2000,
  maxRequestBytes:1_048_576,maxResultBytes:12*1024*1024,maxUploadBytes:16*1024*1024,
  maxStoredRequestBytes:32*1024*1024,maxStoredResultBytes:512*1024*1024};

class GatewayError extends Error {
  constructor(status,code,message){super(message);this.status=status;this.code=code}
}
const fail=(status,code,message)=>{throw new GatewayError(status,code,message)};
const object=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
const text=(x,max=256)=>typeof x==='string'&&x.length>0&&x.length<=max;
const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{
  'Content-Type':'application/json','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
const toolResult=(data,isError=false)=>({content:[{type:'text',text:JSON.stringify(data)}],structuredContent:data,isError});
const toolFailure=(code,message,extra={})=>toolResult({ok:false,error:{code,message},...extra},true);
const sleepDefault=ms=>new Promise(resolve=>setTimeout(resolve,ms));

export async function sha256(value){
  const hash=await crypto.subtle.digest('SHA-256',encoder.encode(value));
  return Array.from(new Uint8Array(hash),b=>b.toString(16).padStart(2,'0')).join('');
}
async function sameSecret(left,right){
  const [a,b]=await Promise.all([sha256(left),sha256(right)]);
  let difference=0;
  for(let i=0;i<a.length;i++)difference|=a.charCodeAt(i)^b.charCodeAt(i);
  return difference===0;
}
function canonical(value,depth=0){
  if(depth>64)fail(400,'invalid_arguments','Request nesting is too deep.');
  if(Array.isArray(value))return value.map(v=>canonical(v,depth+1));
  if(object(value)){
    const sorted=Object.create(null);
    for(const key of Object.keys(value).sort())sorted[key]=canonical(value[key],depth+1);
    return sorted;
  }
  if(typeof value==='number'&&!Number.isFinite(value))fail(400,'invalid_arguments','Numbers must be finite.');
  return value;
}
async function readBody(request,max){
  if(request.method!=='POST')fail(405,'method_not_allowed','POST is required.');
  if(request.headers.get('Content-Type')?.split(';')[0].trim()!=='application/json')
    fail(415,'content_type','application/json is required.');
  const declared=request.headers.get('Content-Length');
  if(declared!==null&&(!/^\d+$/.test(declared)||Number(declared)>max))
    fail(413,'body_too_large','Request exceeds the gateway size limit.');
  const reader=request.body?.getReader();
  if(!reader)fail(400,'invalid_json','A JSON object is required.');
  const decoder=new TextDecoder('utf-8',{fatal:true});
  const pieces=[];let bytes=0;
  try{
    while(true){
      const {done,value}=await reader.read();if(done)break;
      bytes+=value.byteLength;
      if(bytes>max){await reader.cancel();fail(413,'body_too_large','Request exceeds the gateway size limit.');}
      pieces.push(decoder.decode(value,{stream:true}));
    }
    pieces.push(decoder.decode());
    const body=JSON.parse(pieces.join(''));
    if(!object(body))fail(400,'invalid_json','A JSON object is required.');
    return body;
  }catch(error){
    if(error instanceof GatewayError)throw error;
    fail(400,'invalid_json','The request must contain valid UTF-8 JSON.');
  }finally{reader.releaseLock();}
}

export function createGateway({catalog,resourceHtml,iconDataUri,clock=Date.now,sleep=sleepDefault,limits={}}){
  const L={...DEFAULTS,...limits};
  const sourceTools=new Map(catalog.map(item=>[item.name,item]));
  const tools=catalog.map(item=>{
    const descriptor=structuredClone(item);
    const mutating=item['x-rdc-mutating']===true;
    descriptor.inputSchema.properties={...descriptor.inputSchema.properties,
      _rdc_request_id:{type:'string',minLength:1,maxLength:200,
        description:'Stable unique ID for this cloud operation. Reuse this same ID and identical arguments after a lost response; never substitute a new ID to retry an uncertain mutation.'}};
    descriptor.inputSchema.required=[...(descriptor.inputSchema.required??[])];
    if(mutating)descriptor.inputSchema.required.push('_rdc_request_id');
    delete descriptor['x-rdc-mutating'];
    return descriptor;
  });
  tools.push({name:'rdc_operation_status',description:'Recover a pending or uncertain cloud operation by operation_id. Returns its original result when ready. This never dispatches or repeats the operation.',
    inputSchema:{type:'object',properties:{operation_id:{type:'string',minLength:1,maxLength:100}},required:['operation_id'],additionalProperties:false},
    annotations:{readOnlyHint:true,idempotentHint:true,destructiveHint:false,openWorldHint:false},
    _meta:{ui:{visibility:['model','app']},'openai/widgetAccessible':true}});
  tools.push({name:'rdc_connection_status',description:'Read the authenticated RDC cloud connection, device availability and queue counts without issuing device commands.',
    inputSchema:{type:'object',properties:{},additionalProperties:false},
    annotations:{readOnlyHint:true,idempotentHint:true,destructiveHint:false,openWorldHint:false}});
  const serverInfo={name:'rdc',title:'RDC',version:'0.1.0a5',description:'Independent agent workspace with an embedded live preview.',
    ...(iconDataUri?{icons:[{src:iconDataUri,mimeType:'image/png'}]}:{})};
  const capabilities={tools:{listChanged:false},resources:{subscribe:false,listChanged:false},extensions:{[UI_EXTENSION]:{}}};
  const instructions='RDC controls the paired device through its existing local grants. Open rdc_preview_open to see the embedded live view. Closing or moving that view never stops work. Mutating cloud tools require a stable _rdc_request_id. When a call returns pending, recover it using rdc_operation_status and the returned operation_id. Never repeat an uncertain mutation under a new ID. Mutation request IDs are retained for 24 hours; preview frame results and operation identities have short retention. Owner approvals remain in the local owner administration.';

  function configured(env){
    if(!env.DB||!env.BUCKET||!text(env.RDC_DEVICE_ID,100))fail(503,'configuration_required','The RDC gateway is not configured yet.');
  }
  async function owner(request,env){
    configured(env);
    const principal=request.headers.get('oai-authenticated-user-id');
    if(!text(principal,256))fail(401,'sign_in_required','Sign in with ChatGPT to use this RDC connection.');
    let row=await env.DB.prepare('SELECT principal FROM gateway_owner WHERE id=1').bind().first();
    if(!row){
      if(env.RDC_OWNER_BOOTSTRAP!=='private-site')fail(503,'owner_not_bound','Private owner enrollment has not been enabled.');
      // This deployment is explicitly owner-private. Once enrolled, a later
      // audience change cannot transfer ownership to a different Site visitor.
      await env.DB.prepare('INSERT OR IGNORE INTO gateway_owner (id,principal,created_ms) VALUES (1,?,?)').bind(principal,clock()).run();
      row=await env.DB.prepare('SELECT principal FROM gateway_owner WHERE id=1').bind().first();
    }
    if(row.principal!==principal)fail(403,'owner_mismatch','This device belongs to another authenticated Site user.');
    return principal;
  }
  async function device(request,env){
    configured(env);
    const key=request.headers.get('X-RDC-Device-Key')??'';
    if(!text(env.RDC_DEVICE_SECRET,256)||env.RDC_DEVICE_SECRET.length<32)
      fail(503,'device_not_paired','The device connection has not been paired.');
    if(!text(key,256)||!await sameSecret(key,env.RDC_DEVICE_SECRET))
      fail(401,'invalid_device_key','The device credential is invalid.');
    // Sites separately validates OAI-Sites-Authorization at its private edge.
    // The consumed edge credential is not available here and is not a user identity.
  }
  async function clean(env){
    const now=clock();
    await env.DB.prepare("UPDATE gateway_operations SET state='expired',request_json=NULL,request_size=0 WHERE state='queued' AND expires_ms<=?").bind(now).run();
    await env.DB.prepare("UPDATE gateway_operations SET state='unknown' WHERE state='claimed' AND claimed_ms<=?").bind(now-L.unknownMs).run();
    const old=await env.DB.prepare('SELECT id,result_key FROM gateway_operations WHERE result_key IS NOT NULL AND result_expires_ms<=? LIMIT 16').bind(now).all();
    for(const row of old.results){
      await env.BUCKET.delete(row.result_key);
      await env.DB.prepare('UPDATE gateway_operations SET result_key=NULL,result_size=0 WHERE id=? AND result_key=?').bind(row.id,row.result_key).run();
    }
    // Frequent, read-only frames must not consume the full day's mutation
    // capacity. A late upload of a retired frame receives operation_not_found;
    // the pump retires that obsolete observation without repeating any work.
    await env.DB.prepare(`DELETE FROM gateway_operations WHERE id IN (
      SELECT id FROM gateway_operations WHERE state IN ('completed','expired','unknown') AND result_key IS NULL
        AND (created_ms<? OR (mutating=0 AND tool='rdc_preview_frame'
          AND COALESCE(completed_ms,claimed_ms,created_ms)<=?)) LIMIT 32)`)
      .bind(now-L.operationTtlMs,now-L.frameOperationTtlMs).run();
  }
  async function connection(env){
    const row=await env.DB.prepare('SELECT last_seen_ms FROM gateway_device WHERE id=?').bind(env.RDC_DEVICE_ID).first();
    const counts=await env.DB.prepare("SELECT COUNT(*) AS count FROM gateway_operations WHERE device_id=? AND state IN ('queued','claimed')").bind(env.RDC_DEVICE_ID).first();
    return {ok:true,device_id:env.RDC_DEVICE_ID,online:!!row&&clock()-row.last_seen_ms<=L.onlineMs,
      last_seen_ms:row?.last_seen_ms??null,pending_operations:counts.count,
      server_time_ms:clock(),preview_tool:'rdc_preview_open'};
  }
  async function operationResult(op,env){
    if(op.state==='completed'){
      if(!op.result_key)return toolFailure('result_expired','The operation completed, but its retained response expired. Inspect the device state before repeating a mutation.',{operation_id:op.id,completed:true});
      const stored=await env.BUCKET.get(op.result_key);
      if(!stored)return toolFailure('result_unavailable','The stored response is unavailable. The operation will not be repeated.',{operation_id:op.id,completed:true});
      const value=JSON.parse(await stored.text());
      return {...value,_meta:{...(value._meta??{}),'rdc/operation_id':op.id}};
    }
    if(op.state==='expired')return toolFailure('expired_before_execution','The queued operation expired before the device claimed it. It was not dispatched.',{operation_id:op.id,status:op.state});
    if(op.state==='unknown')return toolFailure('outcome_unknown','The device may have executed this operation. It will not be dispatched again. Recover status or inspect the device before another mutation.',{operation_id:op.id,status:op.state});
    return toolResult({ok:true,pending:true,operation_id:op.id,status:op.state,
      recovery_tool:'rdc_operation_status',message:'The operation is still active. Retrieve this operation ID; do not dispatch it again.'});
  }
  async function getOperation(id,principal,env){
    const op=await env.DB.prepare('SELECT * FROM gateway_operations WHERE id=? AND principal=? AND device_id=?').bind(id,principal,env.RDC_DEVICE_ID).first();
    if(!op)fail(404,'operation_not_found','The operation was not found for this connection.');
    return op;
  }
  async function dispatch(name,args,principal,env){
    const descriptor=sourceTools.get(name);
    if(!descriptor)fail(400,'unknown_tool','Unknown RDC tool.');
    if(!object(args))fail(400,'invalid_arguments','Tool arguments must be an object.');
    const mutating=descriptor['x-rdc-mutating']===true;
    const requestKey=args._rdc_request_id;
    if((requestKey!==undefined&&!text(requestKey,200))||(mutating&&!text(requestKey,200)))
      fail(400,'request_id_required','Supply a stable _rdc_request_id for this mutation.');
    const localArgs={...args};delete localArgs._rdc_request_id;
    const requestJson=JSON.stringify({name,arguments:canonical(localArgs)});
    const requestSize=encoder.encode(requestJson).length;
    if(requestSize>L.maxRequestBytes)fail(413,'arguments_too_large','Tool arguments exceed the gateway limit.');
    const digest=await sha256(requestJson);
    const key=requestKey??crypto.randomUUID();
    let op=await env.DB.prepare('SELECT * FROM gateway_operations WHERE principal=? AND device_id=? AND request_key=?').bind(principal,env.RDC_DEVICE_ID,key).first();
    if(op){
      if(op.request_sha256!==digest)fail(409,'request_id_conflict','This request ID already belongs to different arguments.');
      return operationResult(op,env);
    }
    if(!(await connection(env)).online)return toolFailure('device_offline','The paired device is offline. No operation was queued.');
    const id=crypto.randomUUID(),now=clock();
    op=await env.DB.prepare(`INSERT INTO gateway_operations
      (id,principal,device_id,request_key,tool,request_json,request_sha256,request_size,mutating,state,created_ms,expires_ms)
      SELECT ?,?,?,?,?,?,?,?,?, 'queued',?,?
      WHERE (SELECT COUNT(*) FROM gateway_operations WHERE device_id=? AND state IN ('queued','claimed'))<?
        AND (SELECT COUNT(*) FROM gateway_operations WHERE device_id=?)<?
        AND (SELECT COALESCE(SUM(request_size),0) FROM gateway_operations WHERE device_id=?)+?<=?
        AND (SELECT COALESCE(SUM(result_size),0) FROM gateway_operations WHERE device_id=?)
          +((SELECT COUNT(*) FROM gateway_operations WHERE device_id=? AND state IN ('queued','claimed','unknown'))+1)*?<=?
      ON CONFLICT(principal,device_id,request_key) DO NOTHING RETURNING *`)
      .bind(id,principal,env.RDC_DEVICE_ID,key,name,requestJson,digest,requestSize,mutating?1:0,now,now+L.queueTtlMs,
        env.RDC_DEVICE_ID,L.maxBacklog,env.RDC_DEVICE_ID,L.maxOperations,
        env.RDC_DEVICE_ID,requestSize,L.maxStoredRequestBytes,
        env.RDC_DEVICE_ID,env.RDC_DEVICE_ID,L.maxResultBytes,L.maxStoredResultBytes).first();
    if(!op){
      op=await env.DB.prepare('SELECT * FROM gateway_operations WHERE principal=? AND device_id=? AND request_key=?').bind(principal,env.RDC_DEVICE_ID,key).first();
      if(!op)return toolFailure('gateway_busy','The relay has reached its bounded backlog or retention capacity. No operation was queued.');
      if(op.request_sha256!==digest)fail(409,'request_id_conflict','This request ID already belongs to different arguments.');
    }
    const stop=clock()+Math.min(L.callWaitMs,name.startsWith('rdc_preview_')?L.previewWaitMs:L.callWaitMs);
    while(op.state!=='completed'&&op.state!=='expired'&&op.state!=='unknown'&&clock()<stop){
      await sleep(Math.min(L.pollStepMs,stop-clock()));
      op=await getOperation(op.id,principal,env);
    }
    return operationResult(op,env);
  }
  async function mcp(request,env){
    let id=null;
    try{
      const message=await readBody(request,L.maxRequestBytes);
      if(message.jsonrpc!=='2.0'||!text(message.method,200))fail(400,'invalid_request','A JSON-RPC 2.0 method is required.');
      id=message.id??null;
      if(message.id!==undefined&&!(typeof id==='string'||typeof id==='number'&&Number.isFinite(id)))
        fail(400,'invalid_request','The request ID must be a string or number.');
      const params=message.params??{};
      if(!object(params))fail(400,'invalid_params','Parameters must be an object.');
      if(message.id===undefined){
        if(['notifications/initialized','notifications/cancelled'].includes(message.method))return new Response(null,{status:202});
        fail(400,'invalid_request','A request ID is required.');
      }
      let response;
      switch(message.method){
        case 'initialize':response={protocolVersion:['2024-11-05','2025-03-26','2025-06-18','2025-11-25'].includes(params.protocolVersion)?params.protocolVersion:'2025-11-25',capabilities,serverInfo,instructions};break;
        case 'server/discover':response={supportedVersions:['2026-07-28'],capabilities,instructions,_meta:{'io.modelcontextprotocol/serverInfo':serverInfo}};break;
        case 'ping':response={};break;
        case 'tools/list':response={tools};break;
        case 'resources/list':response={resources:[{uri:UI_URI,name:'rdc-preview',title:'RDC Live Preview',mimeType:UI_MIME}]};break;
        case 'resources/templates/list':response={resourceTemplates:[]};break;
        case 'resources/read':
          if(params.uri!==UI_URI)fail(404,'resource_not_found','RDC preview resource not found.');
          response={contents:[{uri:UI_URI,mimeType:UI_MIME,text:resourceHtml,_meta:{ui:{prefersBorder:true,csp:{connectDomains:[],resourceDomains:[],frameDomains:[]}},
            'openai/ui':{availableDisplayModes:['inline','fullscreen','pip']},'openai/widgetDescription':'Live RDC workspace. Hiding the preview keeps active work running.'}}]};break;
        case 'tools/call':{
          const principal=await owner(request,env);await clean(env);
          if(params.name==='rdc_connection_status')response=toolResult(await connection(env));
          else if(params.name==='rdc_operation_status'){
            if(!text(params.arguments?.operation_id,100))fail(400,'invalid_arguments','operation_id is required.');
            response=await operationResult(await getOperation(params.arguments.operation_id,principal,env),env);
          }else response=await dispatch(params.name,params.arguments??{},principal,env);
          break;
        }
        default:return json({jsonrpc:'2.0',id,error:{code:-32601,message:'Method not found'}},400);
      }
      return json({jsonrpc:'2.0',id,result:response});
    }catch(error){
      const known=error instanceof GatewayError;
      return json({jsonrpc:'2.0',id,error:{code:known?(error.status===404?-32002:-32000):-32603,
        message:known?error.message:'The RDC gateway is temporarily unavailable.',data:{code:known?error.code:'gateway_unavailable'}}},known?error.status:503);
    }
  }
  async function poll(request,env){
    try{
      await device(request,env);const body=await readBody(request,4096);
      if(body.device_id!==env.RDC_DEVICE_ID)fail(403,'device_mismatch','This credential belongs to another device.');
      if(body.claim!==undefined&&typeof body.claim!=='boolean')fail(400,'invalid_request','claim must be a boolean.');
      await env.DB.prepare('INSERT INTO gateway_device(id,last_seen_ms) VALUES (?,?) ON CONFLICT(id) DO UPDATE SET last_seen_ms=excluded.last_seen_ms').bind(env.RDC_DEVICE_ID,clock()).run();
      await clean(env);
      const stop=clock()+(body.claim===false?0:L.pollWaitMs);
      let op=null;
      if(body.claim!==false){
        do{
          const now=clock();
          op=await env.DB.prepare(`UPDATE gateway_operations SET state='claimed',claim_id=?,claimed_ms=?
            WHERE id=(SELECT id FROM gateway_operations WHERE device_id=? AND state='queued' AND expires_ms>? ORDER BY created_ms,id LIMIT 1)
              AND state='queued' RETURNING *`).bind(crypto.randomUUID(),now,env.RDC_DEVICE_ID,now).first();
          if(op||clock()>=stop)break;
          await sleep(Math.min(L.pollStepMs,stop-clock()));
        }while(clock()<=stop);
      }
      return json({ok:true,device_id:env.RDC_DEVICE_ID,server_time_ms:clock(),poll_after_ms:250,
        operation:op?{operation_id:op.id,claim_id:op.claim_id,request_json:op.request_json,
          request_sha256:op.request_sha256,expires_at_ms:op.expires_ms}:null});
    }catch(error){return apiError(error);}
  }
  async function result(request,env){
    try{
      await device(request,env);const body=await readBody(request,L.maxUploadBytes);
      if(typeof body.result_json==='string'&&encoder.encode(body.result_json).length>L.maxResultBytes)
        fail(413,'result_too_large','The result exceeds the 12 MiB relay limit.');
      if(body.device_id!==env.RDC_DEVICE_ID)fail(403,'device_mismatch','This credential belongs to another device.');
      if(!text(body.operation_id,100)||!text(body.claim_id,100)||!text(body.request_sha256,64)||typeof body.result_json!=='string')
        fail(400,'invalid_result','An operation, claim, request hash and result_json are required.');
      const op=await env.DB.prepare('SELECT * FROM gateway_operations WHERE id=? AND device_id=?').bind(body.operation_id,env.RDC_DEVICE_ID).first();
      if(!op)fail(404,'operation_not_found','The operation was not found.');
      if(op.claim_id!==body.claim_id||op.request_sha256!==body.request_sha256)
        fail(409,'claim_mismatch','The result does not match this claimed operation.');
      const digest=await sha256(body.result_json);
      if(op.result_sha256){
        if(op.result_sha256!==digest)fail(409,'result_conflict','A different result is already recorded for this operation.');
        return json({ok:true,operation_id:op.id,status:'completed',duplicate:true});
      }
      if(!['claimed','unknown'].includes(op.state))fail(409,'operation_not_claimed','Only a claimed operation can receive a result.');
      let value;try{value=JSON.parse(body.result_json)}catch{fail(400,'invalid_result','result_json must contain valid JSON.');}
      if(!object(value)||!Array.isArray(value.content)||value.content.length>1000||
        (value.isError!==undefined&&typeof value.isError!=='boolean'))
        fail(400,'invalid_result','A standard MCP CallToolResult is required.');
      const key=`rdc-results/${env.RDC_DEVICE_ID}/${op.id}/${digest}.json`;
      // The object is durable before the database advertises completion. A lost
      // acknowledgment only repeats this upload; it never repeats device work.
      // D1 failure after this write can leave an unrecorded orphan. Admission
      // bounds committed/reserved bytes, not every object in the R2 bucket.
      await env.BUCKET.put(key,body.result_json,{httpMetadata:{contentType:'application/json'}});
      const completed=await env.DB.prepare(`UPDATE gateway_operations SET state='completed',completed_ms=?,result_key=?,result_sha256=?,result_size=?,result_expires_ms=?,request_json=NULL,request_size=0
        WHERE id=? AND device_id=? AND result_sha256 IS NULL AND state IN ('claimed','unknown') RETURNING id`)
        .bind(clock(),key,digest,encoder.encode(body.result_json).length,clock()+(op.tool==='rdc_preview_frame'?L.frameTtlMs:L.resultTtlMs),op.id,env.RDC_DEVICE_ID).first();
      if(!completed){
        const current=await env.DB.prepare('SELECT result_sha256 FROM gateway_operations WHERE id=?').bind(op.id).first();
        if(current?.result_sha256!==digest){await env.BUCKET.delete(key);fail(409,'result_conflict','A different result won the completion race.');}
      }
      return json({ok:true,operation_id:op.id,status:'completed',duplicate:!completed});
    }catch(error){return apiError(error);}
  }
  function apiError(error){
    return error instanceof GatewayError?json({ok:false,error:{code:error.code,message:error.message}},error.status):
      json({ok:false,error:{code:'gateway_unavailable',message:'The RDC gateway is temporarily unavailable.'}},503);
  }
  async function status(request,env){
    try{await owner(request,env);await clean(env);return json(await connection(env));}
    catch(error){return apiError(error);}
  }
  return {mcp,poll,result,status};
}
