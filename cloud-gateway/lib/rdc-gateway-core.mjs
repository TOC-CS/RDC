/* Authenticated outbound relay. The device remains the authority for grants.
 * Queued operations are claimed once; uncertainty never causes redispatch.
 */
const UI_URI='ui://rdc/preview-v8.html';
const UI_V7_URI='ui://rdc/preview-v7.html';
const UI_V6_URI='ui://rdc/preview-v6.html';
const UI_V5_URI='ui://rdc/preview-v5.html';
const UI_V4_URI='ui://rdc/preview-v4.html';
const UI_PREVIOUS_URI='ui://rdc/preview-v3.html';
const UI_V2_URI='ui://rdc/preview-v2.html';
const UI_LEGACY_URI='ui://rdc/preview-v1.html';
const UI_MIME='text/html;profile=mcp-app';
const UI_EXTENSION='io.modelcontextprotocol/ui';
const LEGACY_PROTOCOL_VERSIONS=['2024-11-05','2025-03-26','2025-06-18','2025-11-25'];
const MODERN_PROTOCOL_VERSIONS=['2026-07-28'];
const PROTOCOL_VERSION_META='io.modelcontextprotocol/protocolVersion';
const CLIENT_CAPABILITIES_META='io.modelcontextprotocol/clientCapabilities';
const CACHEABLE_METHODS=new Set(['server/discover','tools/list','resources/list','resources/templates/list','resources/read']);
const encoder=new TextEncoder();
const DEFAULTS={callWaitMs:20_000,previewWaitMs:8_000,pollWaitMs:10_000,pollStepMs:500,
  queueTtlMs:30_000,onlineMs:35_000,unknownMs:120_000,operationTtlMs:86_400_000,
  resultTtlMs:3_600_000,frameTtlMs:30_000,frameOperationTtlMs:60_000,maxBacklog:32,maxOperations:2000,
  maxRequestBytes:1_048_576,maxResultBytes:12*1024*1024,maxUploadBytes:16*1024*1024,
  maxStoredRequestBytes:32*1024*1024,maxStoredResultBytes:512*1024*1024,
  maxInlineResultBytes:8192};

class GatewayError extends Error {
  constructor(status,code,message,rpcCode,data){super(message);this.status=status;this.code=code;this.rpcCode=rpcCode;this.data=data}
}
const fail=(status,code,message)=>{throw new GatewayError(status,code,message)};
const object=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
const text=(x,max=256)=>typeof x==='string'&&x.length>0&&x.length<=max;
const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{
  'Content-Type':'application/json','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
const toolResult=(data,isError=false)=>({content:[{type:'text',text:JSON.stringify(data)}],structuredContent:data,isError});
const toolFailure=(code,message,extra={})=>toolResult({ok:false,error:{code,message},...extra},true);
const sleepDefault=ms=>new Promise(resolve=>setTimeout(resolve,ms));

// MCP 2026-07-28 carries its negotiation fields on each request. Legacy
// initialize clients retain their existing request shape and fallback version.
function validateProtocol(request,message,params){
  const header=request.headers.get('MCP-Protocol-Version');
  const meta=params._meta;
  const modern=(header!==null&&!LEGACY_PROTOCOL_VERSIONS.includes(header))||
    (object(meta)&&Object.hasOwn(meta,PROTOCOL_VERSION_META));
  if(!modern)return;
  const reject=(code,message,data)=>{throw new GatewayError(400,'invalid_protocol',message,code,data)};
  if(!object(meta)||!Object.hasOwn(meta,PROTOCOL_VERSION_META)||!Object.hasOwn(meta,CLIENT_CAPABILITIES_META))
    reject(-32602,'params._meta must include the protocol version and client capabilities.');
  const version=meta[PROTOCOL_VERSION_META];
  if(header===null||header!==version)
    reject(-32020,'MCP-Protocol-Version header does not match the request envelope protocol version.');
  if(request.headers.get('Mcp-Method')!==message.method)
    reject(-32020,'Mcp-Method header does not match the request method.');
  const name=message.method==='tools/call'?params.name:message.method==='resources/read'?params.uri:undefined;
  if(name!==undefined&&request.headers.get('Mcp-Name')!==name)
    reject(-32020,'Mcp-Name header does not match the request name.');
  if(!MODERN_PROTOCOL_VERSIONS.includes(version))
    reject(-32022,'Unsupported protocol version',{requested:version,supported:MODERN_PROTOCOL_VERSIONS});
  if(!object(meta[CLIENT_CAPABILITIES_META]))
    reject(-32602,'The client capabilities must be an object.');
}

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

/** @typedef {{notify?: (deviceId:string)=>Promise<void>, wait?: (deviceId:string,ms:number)=>Promise<boolean>, notifyResult?: (deviceId:string,operationId:string)=>Promise<void>, waitResult?: (deviceId:string,operationId:string,ms:number)=>Promise<boolean>}} WakeChannel */
export function createGateway({catalog,resourceHtml,iconDataUri,clock=Date.now,sleep=sleepDefault,limits={},chatRouter=null,wakeChannel=/** @type {WakeChannel | ((env:any)=>WakeChannel|null) | null} */ (null)}){
  const L={...DEFAULTS,...limits};
  function notifierFor(env){
    try{
      const bound=typeof wakeChannel==='function'?wakeChannel(env):wakeChannel;
      return bound&&typeof bound==='object'?bound:null;
    }catch{ return null; } // Missing optional binding cannot disable D1 claims.
  }
  const sourceTools=new Map(catalog.map(item=>[item.name,item]));
  // Gateway-local methods are owner-only regardless of future worker
  // catalog collisions; never route them through atomic worker admission.
  const gatewayOnlyTools=new Set([
    'rdc_connection_status','rdc_recent_operation_metrics',
    'rdc_chat_session_status','rdc_operation_status'
  ]);
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
  tools.push({name:'rdc_operation_status',description:'Recover a pending or uncertain cloud operation by operation_id. Returns its original result when ready. Set diagnostics:true for owner-only phase durations instead of the result. This never dispatches or repeats the operation.',
    inputSchema:{type:'object',properties:{operation_id:{type:'string',minLength:1,maxLength:100},
      diagnostics:{type:'boolean',description:'Return only the existing operation state and gateway phase durations in milliseconds, without retrieving the result.'}},required:['operation_id'],additionalProperties:false},
    annotations:{readOnlyHint:true,idempotentHint:true,destructiveHint:false,openWorldHint:false},
    _meta:{ui:{visibility:['model','app']},'openai/widgetAccessible':true}});
  tools.push({name:'rdc_connection_status',description:'Read the authenticated RDC cloud connection, device availability and queue counts without issuing device commands.',
    inputSchema:{type:'object',properties:{},additionalProperties:false},
    annotations:{readOnlyHint:true,idempotentHint:true,destructiveHint:false,openWorldHint:false}});
  tools.push({name:'rdc_chat_session_status',description:'Check whether this authenticated ChatGPT tool call supplies a bounded conversation identity. Return a pseudonymous ID only. Does not enroll a native ChatGPT Project or create/wake other chats.',
    inputSchema:{type:'object',properties:{},additionalProperties:false},
    annotations:{readOnlyHint:true,idempotentHint:true,destructiveHint:false,openWorldHint:false}});
  const chatOps=[
    {name:'rdc_chat_inbox',description:'Read up to 20 pending messages for the host-authenticated, independently project-enrolled conversation. No browser takeover.',required:[],properties:{cursor:{type:'string',maxLength:200},limit:{type:'integer',minimum:1,maximum:20}}},
    {name:'rdc_chat_send',description:'Send one durable message to an independently verified recipient in the same authorized project.',required:['target_session','text','_rdc_request_id'],properties:{target_session:{type:'string',minLength:1,maxLength:128},text:{type:'string',minLength:1,maxLength:3000}}},
    {name:'rdc_chat_reply',description:'Reply once to an observed message, preserving causation and root conversation ID.',required:['parent_id','text','_rdc_request_id'],properties:{parent_id:{type:'string',minLength:1,maxLength:128},text:{type:'string',minLength:1,maxLength:3000}}},
    {name:'rdc_chat_ack',description:'Acknowledge an exact recipient message only after observed delivery.',required:['message_id','_rdc_request_id'],properties:{message_id:{type:'string',minLength:1,maxLength:128}}},
    {name:'rdc_chat_create',description:'Request a new conversation under a one-time project grant, only through an authorized host with readback.',required:['provider','_rdc_request_id'],properties:{provider:{type:'string',minLength:1,maxLength:64}}},
    {name:'rdc_chat_wake',description:'Request an approved wake signal for a safe idle chat; never assume a model resumed.',required:['target_session','_rdc_request_id'],properties:{target_session:{type:'string',minLength:1,maxLength:128}}},
    {name:'rdc_chat_route_status',description:'Read independently approved Atlas cross-project route capability without attempting delivery.',required:[],properties:{}},
    {name:'rdc_chat_cross_project_send',description:'Submit a durable message through an independently approved Atlas route only; no direct BusStore bypass.',required:['target_project','target_session','text','_rdc_request_id'],properties:{target_project:{type:'string',enum:['atlas','rdc','bandmates','presentation']},target_session:{type:'string',minLength:1,maxLength:128},text:{type:'string',minLength:1,maxLength:3000}}},
  ];
  const chatOpsByName=new Map(chatOps.map(x=>[x.name,x]));
  for(const op of chatOps){
    const mutating=op.required.includes('_rdc_request_id');
    tools.push({name:op.name,description:op.description,inputSchema:{type:'object',properties:{...op.properties,...(mutating?{_rdc_request_id:{type:'string',minLength:1,maxLength:200}}:{})},required:op.required,additionalProperties:false},annotations:{readOnlyHint:!mutating,idempotentHint:!mutating,destructiveHint:mutating,openWorldHint:true}});
  }
  function validateChatOp(name,args){
    const op=chatOpsByName.get(name);
    if(!op)return;
    if(!object(args))fail(400,'invalid_arguments','Chat tool arguments must be a JSON object.');
    const spec=tools.find(x=>x.name===name).inputSchema;
    for(const field of Object.keys(args)){
      const p=spec.properties[field];
      if(!p)fail(400,'invalid_arguments','Unknown chat operation argument.');
      const v=args[field];
      if(p.type==='string'){
        if(typeof v!=='string'||(p.minLength!==undefined&&v.length<p.minLength)||v.length>(p.maxLength??32000)||(p.enum&&!p.enum.includes(v)))fail(400,'invalid_arguments','Invalid chat operation text field.');
      }else if(p.type==='integer'&&(!Number.isInteger(v)||v<(p.minimum??0)||v>(p.maximum??Number.MAX_SAFE_INTEGER)))fail(400,'invalid_arguments','Invalid chat operation numeric field.');
    }
    for(const field of op.required)if(!Object.hasOwn(args,field))fail(400,'request_id_required','Missing required chat operation field.');
  }
  tools.push({name:'rdc_recent_operation_metrics',
    description:'Read owner-only completed RDC gateway phase durations for up to 50 recent operations. Never exposes arguments, messages, results, tokens, identities or full operation IDs.',
    inputSchema:{type:'object',properties:{limit:{type:'integer',minimum:1,maximum:50}},required:[],additionalProperties:false},
    annotations:{readOnlyHint:true,idempotentHint:true,destructiveHint:false,openWorldHint:false}});
  const serverInfo={name:'rdc',title:'RDC',version:'0.1.0a8',description:'Independent agent workspace with an embedded live preview.',
    ...(iconDataUri?{icons:[{src:iconDataUri,mimeType:'image/png',sizes:['192x192']}]}:{})};
  const capabilities={tools:{listChanged:false},resources:{subscribe:false,listChanged:false},extensions:{[UI_EXTENSION]:{}}};
  const instructions='RDC controls the paired device through its existing local grants. Pass the current task session_id to rdc_preview_open to see only that live visual source. Closing or moving that view never stops work. Mutating cloud tools require a stable _rdc_request_id. When a call returns pending, recover it using rdc_operation_status and the returned operation_id. Never repeat an uncertain mutation under a new ID. Mutation request IDs are retained for 24 hours; preview frame and activity results and operation identities have short retention. Owner approvals remain in the local owner administration.';

  function configured(env){
    if(!env.DB||!env.BUCKET||!text(env.RDC_DEVICE_ID,100))fail(503,'configuration_required','The RDC gateway is not configured yet.');
  }
  async function chatSessionStatus(meta,principal,env){
    // This diagnostic is read-only. The host account authentication above
    // cannot establish native ChatGPT Project membership from tool metadata.
    const secret=env.RDC_CHAT_IDENTITY_SECRET;
    if(!text(secret,1024)||secret.length<32)
      return {ok:true,available:false,reason:'IDENTITY_KEY_UNAVAILABLE',chat_project_verified:false};
    const subject=object(meta)?meta['openai/subject']:null;
    const session=object(meta)?meta['openai/session']:null;
    if(!text(subject,256)||!text(session,256))
      return {ok:true,available:false,reason:'CHAT_CONTEXT_UNAVAILABLE',chat_project_verified:false};
    const key=await crypto.subtle.importKey('raw',encoder.encode(secret),{name:'HMAC',hash:'SHA-256'},false,['sign']);
    const bytes=encoder.encode(['rdc-chat-status-v1',principal,subject,session].join(String.fromCharCode(0)));
    const digest=await crypto.subtle.sign('HMAC',key,bytes);
    const hashed=Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,'0')).join('');
    return {ok:true,available:true,opaque_session_id:'chatgpt-'+hashed.slice(0,40),
      session_metadata_present:true,chat_project_verified:false,
      chat_project_status:'PROJECT_UNVERIFIED',can_create:false,can_wake:false,can_send:false};
  }
  function authenticatedPrincipal(request,env){
    configured(env);
    const principal=request.headers.get('oai-authenticated-user-id');
    if(!text(principal,256))fail(401,'sign_in_required','Sign in with ChatGPT to use this RDC connection.');
    return principal;
  }
  async function owner(request,env){
    const principal=authenticatedPrincipal(request,env);
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
    const old=await env.DB.prepare('SELECT id,result_key FROM gateway_operations WHERE (result_key IS NOT NULL OR result_inline_json IS NOT NULL) AND result_expires_ms<=? LIMIT 16').bind(now).all();
    for(const row of old.results){
      // Inline payloads and R2 objects share the same retention deadline.
      // An inline expiry must not issue an R2 delete for a null key.
      if(row.result_key!==null)await env.BUCKET.delete(row.result_key);
      await env.DB.prepare('UPDATE gateway_operations SET result_key=NULL,result_inline_json=NULL,result_size=0 WHERE id=? AND result_expires_ms<=?')
        .bind(row.id,now).run();
    }
    // Frequent, read-only observations must not consume the day's mutation
    // capacity. A late upload of a retired frame receives operation_not_found;
    // the pump retires that obsolete observation without repeating any work.
    await env.DB.prepare(`DELETE FROM gateway_operations WHERE id IN (
      SELECT id FROM gateway_operations WHERE state IN ('completed','expired','unknown')
        AND result_key IS NULL AND result_inline_json IS NULL
        AND (created_ms<? OR (mutating=0 AND tool IN ('rdc_preview_frame','rdc_preview_activity')
          AND COALESCE(completed_ms,claimed_ms,created_ms)<=?)) LIMIT 32)`)
      .bind(now-L.operationTtlMs,now-L.frameOperationTtlMs).run();
  }
  // Dispatch consumes only liveness. Keep the pending-operation COUNT in the
  // public status method where that information is actually requested.
  async function deviceOnline(env){
    const row=await env.DB.prepare('SELECT last_seen_ms FROM gateway_device WHERE id=?').bind(env.RDC_DEVICE_ID).first();
    return !!row&&clock()-row.last_seen_ms<=L.onlineMs;
  }
  async function connection(request,env,principal){
    // Once enrolled, private ownership, online state and pending queue count
    // share one D1 statement and network roundtrip. The owner predicate
    // prevents a different Site principal from observing device state.
    // Expired queue rows are excluded without changing retained records.
    const now=clock();
    const read=()=>env.DB.prepare(`
      SELECT d.last_seen_ms,
        (SELECT COUNT(*) FROM gateway_operations WHERE device_id=?
          AND ((state='queued' AND expires_ms>?) OR (state='claimed' AND claimed_ms>?))) AS count
      FROM gateway_owner AS o LEFT JOIN gateway_device AS d ON d.id=?
      WHERE o.id=1 AND o.principal=? LIMIT 1
    `).bind(env.RDC_DEVICE_ID,now,now-L.unknownMs,env.RDC_DEVICE_ID,principal).first();
    let row=await read();
    if(!row){
      // Preserve explicit bootstrap and historical 403-before-disclosure on
      // first use, absent owner pin, and nonowner calls. No state is leaked.
      await owner(request,env);
      row=await read();
      if(!row)fail(503,'owner_not_bound','Private owner enrollment is unavailable.');
    }
    return {ok:true,device_id:env.RDC_DEVICE_ID,online:row.last_seen_ms!==null&&now-row.last_seen_ms<=L.onlineMs,
      last_seen_ms:row.last_seen_ms??null,pending_operations:Number(row.count),
      server_time_ms:now,preview_tool:'rdc_preview_open'};
  }
  async function recentMetrics(args,principal,env){
    if(!object(args)||Object.keys(args).some(k=>k!=='limit'))
      fail(400,'invalid_arguments','Only the bounded limit is supported.');
    const limit=args.limit??20;
    if(!Number.isInteger(limit)||limit<1||limit>50)
      fail(400,'invalid_arguments','Limit must be an integer between 1 and 50.');
    // Never read args, request IDs, result bodies, tokens or principal into
    // the output. This is an owner-authenticated, read-only D1 query.
    const rows=await env.DB.prepare(
      "SELECT tool,created_ms,claimed_ms,completed_ms FROM gateway_operations "+
      "WHERE principal=? AND device_id=? AND state='completed' AND completed_ms IS NOT NULL "+
      "ORDER BY completed_ms DESC LIMIT ?"
    ).bind(principal,env.RDC_DEVICE_ID,limit).all();
    const delta=(later,earlier)=>later===null||earlier===null||
      later===undefined||earlier===undefined?null:Math.max(0,later-earlier);
    const samples=rows.results.map(row=>({
      tool:row.tool,
      queue_wait_ms:delta(row.claimed_ms,row.created_ms),
      claim_to_result_ms:delta(row.completed_ms,row.claimed_ms),
      total_gateway_ms:delta(row.completed_ms,row.created_ms)
    }));
    return {ok:true,count:samples.length,completed_only:true,samples};
  }
  function operationDiagnostics(op){
    const now=clock();
    const created=op.created_ms;
    const claimed=op.claimed_ms;
    const completed=op.completed_ms;
    const interval=(end,start)=>end===null||end===undefined||start===null||start===undefined?
      null:Math.max(0,end-start);
    return {ok:true,diagnostics:true,operation_id:op.id,tool:op.tool,state:op.state,
      elapsed_ms:interval(now,created),
      queue_age_ms:op.state==='queued'?interval(now,created):null,
      queue_wait_ms:interval(claimed,created),
      inflight_age_ms:op.state==='claimed'?interval(now,claimed):null,
      claim_to_result_ms:interval(completed,claimed),
      completed_age_ms:op.state==='completed'?interval(now,completed):null};
  }
  async function operationResult(op,env){
    if(op.state==='completed'){
      // A completed preview read whose response was retired is a terminal
      // observation state. Keep it as a normal result so hosts do not replace
      // its structured recovery contract with a transport exception. The UI
      // may request a fresh read; this gateway never redispatches the original.
      // Both the explicit allowlist and persisted mutation bit are required.
      const previewRead=op.mutating===0&&['rdc_preview_open','rdc_preview_frame','rdc_preview_activity'].includes(op.tool);
      const missingResult=reason=>previewRead?toolResult({ok:true,preview_refresh_required:true,refresh_tool:op.tool,
        operation_id:op.id,completed:true,reason,message:reason==='result_expired'?
          'This preview observation completed, but its response expired. Request a fresh read-only snapshot.':
          'This preview observation completed, but its stored response is unavailable. Request a fresh read-only snapshot.'}):
        toolFailure(reason,reason==='result_expired'?
          'The operation completed, but its retained response expired. Inspect the device state before repeating a mutation.':
          'The stored response is unavailable. The operation will not be repeated.',{operation_id:op.id,completed:true});
      if(op.result_expires_ms!==null&&op.result_expires_ms!==undefined&&
          op.result_expires_ms<=clock())return missingResult('result_expired');
      if(!op.result_key&&!op.result_inline_json)return missingResult('result_expired');
      // For small results the same authorized operation record is the durable
      // result store. Larger payloads keep the existing R2 readback path.
      let resultJson=op.result_inline_json;
      if(!resultJson){
        const stored=await env.BUCKET.get(op.result_key);
        if(!stored)return missingResult('result_unavailable');
        resultJson=await stored.text();
      }
      const value=JSON.parse(resultJson);
      // Some host tool connectors retain structuredContent but strip MCP
      // result _meta. Keep the authoritative operation ID in both places so
      // the owner can request phase diagnostics after a fast completed call.
      // The gateway-owned ID overrides any untrusted worker placeholder.
      return {...value,
        ...(object(value.structuredContent)?{structuredContent:{
          ...value.structuredContent,_rdc_gateway_operation_id:op.id}}:{}),
        _meta:{...(value._meta??{}),'rdc/operation_id':op.id}};
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
  async function dispatch(name,args,principal,env,ownerRequest=null){
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
    // Successful first-time requests go straight to one durable conditional
    // D1 INSERT. Only a refused INSERT needs the duplicate-key SELECT.
    // The unique request key and original hash remain the idempotency guard.
    async function recoverExisting(){
      let existing=await env.DB.prepare('SELECT * FROM gateway_operations WHERE principal=? AND device_id=? AND request_key=?')
        .bind(principal,env.RDC_DEVICE_ID,key).first();
      if(!existing)return null;
      if(existing.request_sha256!==digest)
        fail(409,'request_id_conflict','This request ID already belongs to different arguments.');
      const dueRetirement=(existing.state==='completed'&&existing.result_expires_ms!==null&&
          existing.result_expires_ms!==undefined&&existing.result_expires_ms<=clock())||
        (existing.state==='queued'&&existing.expires_ms<=clock())||
        (existing.state==='claimed'&&existing.claimed_ms!==null&&existing.claimed_ms<=clock()-L.unknownMs);
      if(dueRetirement){
        await clean(env);
        existing=await getOperation(existing.id,principal,env);
      }
      return operationResult(existing,env);
    }
    let op=null;
    const unavailable=(code,message)=>name==='rdc_preview_open'?
      toolResult({ok:true,preview_unavailable:true,preview_status:code,message,device_id:env.RDC_DEVICE_ID}):toolFailure(code,message);
    // New admissions check liveness atomically inside the same D1 INSERT
    // used to enforce durable backlog and byte limits. Only a failed
    // admission needs a separate liveness query to explain why it failed.
    const id=crypto.randomUUID(),now=clock();
    const admit=()=>env.DB.prepare(`INSERT INTO gateway_operations
      (id,principal,device_id,request_key,tool,request_json,request_sha256,request_size,mutating,state,created_ms,expires_ms)
      SELECT ?,?,?,?,?,?,?,?,?, 'queued',?,?
      WHERE EXISTS(SELECT 1 FROM gateway_owner WHERE id=1 AND principal=?)
        AND EXISTS(SELECT 1 FROM gateway_device WHERE id=? AND last_seen_ms>=?)
        AND (SELECT COUNT(*) FROM gateway_operations WHERE device_id=? AND state IN ('queued','claimed'))<?
        AND (SELECT COUNT(*) FROM gateway_operations WHERE device_id=?)<?
        AND (SELECT COALESCE(SUM(request_size),0) FROM gateway_operations WHERE device_id=?)+?<=?
        AND (SELECT COALESCE(SUM(result_size),0) FROM gateway_operations WHERE device_id=?)
          +((SELECT COUNT(*) FROM gateway_operations WHERE device_id=? AND state IN ('queued','claimed','unknown'))+1)*?<=?
      ON CONFLICT(principal,device_id,request_key) DO NOTHING RETURNING *`)
      .bind(id,principal,env.RDC_DEVICE_ID,key,name,requestJson,digest,requestSize,mutating?1:0,now,now+L.queueTtlMs,
        principal,env.RDC_DEVICE_ID,now-L.onlineMs,
        env.RDC_DEVICE_ID,L.maxBacklog,env.RDC_DEVICE_ID,L.maxOperations,
        env.RDC_DEVICE_ID,requestSize,L.maxStoredRequestBytes,
        env.RDC_DEVICE_ID,env.RDC_DEVICE_ID,L.maxResultBytes,L.maxStoredResultBytes).first();
    op=await admit();
    if(!op){
      // On the fast path a refused INSERT must pass the original D1 owner
      // check BEFORE any recovery or housekeeping. This handles initial
      // private enrollment and denies other visitors without side effects.
      if(ownerRequest)await owner(ownerRequest,env);
      const existing=await recoverExisting();
      if(existing)return existing;
      // A first-ever owner enrollment needs a fresh admission after pinning.
      if(ownerRequest)op=await admit();
    }
    if(!op){
      // Only the failed admission pays for retention maintenance. Retry the
      // EXACT SAME durable operation once after expired queue/claim/result
      // rows are retired, without resubmitting any local worker action.
      await clean(env);
      op=await admit();
    }
    if(!op){
      if(!(await deviceOnline(env)))
        return unavailable('device_offline','The paired device is offline. No operation was queued.');
      // Capacity recovery is bounded and runs only after admission refusal.
      // Preserve every mutation, unknown execution, active job and live result.
      const usage=await env.DB.prepare('SELECT COUNT(*) AS n FROM gateway_operations WHERE device_id=?')
        .bind(env.RDC_DEVICE_ID).first();
      if(Number(usage?.n??0)>=L.maxOperations){
        await env.DB.prepare(`DELETE FROM gateway_operations WHERE id IN (
          SELECT id FROM gateway_operations WHERE device_id=? AND mutating=0
            AND result_key IS NULL AND result_inline_json IS NULL
            AND ((state='completed' AND result_expires_ms<=?)
              OR (state='expired' AND expires_ms<=?))
          ORDER BY created_ms LIMIT 32)`)
          .bind(env.RDC_DEVICE_ID,now,now).run();
        op=await admit();
      }
    }
    const notifier=notifierFor(env);
    if(op&&notifier&&typeof notifier.notify==='function'){
      // Signal only an actually admitted operation, including one admitted
      // through a safe capacity retry. D1 remains the claim authority.
      try{await notifier.notify(env.RDC_DEVICE_ID)}catch{}
    }
    if(!op){
      const existing=await recoverExisting();
      if(existing)return existing;
      return unavailable('gateway_busy','The relay has reached its bounded backlog or retention capacity. No operation was queued.');
    }
    // Bootstrap the UI immediately after durable admission. Its existing
    // operation-status polling recovers this same observation without replay.
    if(name==='rdc_preview_open'||name==='rdc_preview_activity')return operationResult(op,env);
    const stop=clock()+Math.min(L.callWaitMs,name.startsWith('rdc_preview_')?L.previewWaitMs:L.callWaitMs);
    let claimedFastProbes=0, resultHintCount=0;
    while(op.state!=='completed'&&op.state!=='expired'&&op.state!=='unknown'&&clock()<stop){
      // Once the relay claims this operation, make at most three brief checks
      // for a fast result upload. Do not accelerate queued/idle work, and fall
      // back to the normal interval for longer-running commands.
      const fastClaim=op.state==='claimed'&&claimedFastProbes<3;
      const interval=fastClaim?Math.min(100,L.pollStepMs):L.pollStepMs;
      if(fastClaim)claimedFastProbes++;
      const remaining=Math.min(interval,stop-clock());
      if(notifier&&typeof notifier.waitResult==='function'&&resultHintCount<3){
        const started=clock();let signaled=false;
        try{signaled=(await notifier.waitResult(env.RDC_DEVICE_ID,op.id,remaining))===true}
        catch{ /* Durable result polling remains available. */ }
        if(signaled)resultHintCount++;
        if(!signaled){
          const idle=Math.max(0,remaining-(clock()-started));
          if(idle>0)await sleep(idle);
        }
      }else await sleep(remaining);
      // Notifications carry no result bytes and never authorize execution.
      // Read the original committed operation before replying to ChatGPT.
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
      validateProtocol(request,message,params);
      if(message.id===undefined){
        if(['notifications/initialized','notifications/cancelled'].includes(message.method))return new Response(null,{status:202});
        fail(400,'invalid_request','A request ID is required.');
      }
      let response;
      switch(message.method){
        case 'initialize':response={protocolVersion:LEGACY_PROTOCOL_VERSIONS.includes(params.protocolVersion)?params.protocolVersion:'2025-11-25',capabilities,serverInfo,instructions};break;
        case 'server/discover':response={supportedVersions:MODERN_PROTOCOL_VERSIONS,capabilities,instructions,_meta:{'io.modelcontextprotocol/serverInfo':serverInfo}};break;
        case 'ping':response={};break;
        case 'tools/list':response={tools};break;
        case 'resources/list':response={resources:[{uri:UI_URI,name:'rdc-preview',title:'RDC Live Preview',mimeType:UI_MIME}]};break;
        case 'resources/templates/list':response={resourceTemplates:[]};break;
        case 'resources/read':
          if(![UI_URI,UI_V7_URI,UI_V6_URI,UI_V5_URI,UI_V4_URI,UI_PREVIOUS_URI,UI_V2_URI,UI_LEGACY_URI].includes(params.uri))fail(404,'resource_not_found','RDC preview resource not found.');
          response={contents:[{uri:params.uri,mimeType:UI_MIME,text:resourceHtml,_meta:{ui:{prefersBorder:false,csp:{connectDomains:[],resourceDomains:[],frameDomains:[]}},
            'openai/ui':{availableDisplayModes:['inline','fullscreen'],preferredDisplayMode:'inline'},'openai/widgetDescription':'Live view of the selected RDC session. Hiding the view leaves work running.'}}]};break;
        case 'tools/call':{
          // The normal authorized worker route validates owner identity in
          // the SAME D1 INSERT as capacity and device liveness. Every other
          // owner-only route keeps its historical explicit D1 owner check.
          const fastWorkerTool=sourceTools.has(params.name)&&!gatewayOnlyTools.has(params.name);
          const fastStatusTool=params.name==='rdc_connection_status';
          const principal=fastWorkerTool||fastStatusTool?
            authenticatedPrincipal(request,env):await owner(request,env);
          if(fastStatusTool){
            // Pinned-owner authorization and both status values are checked
            // within one read. First enrollment and denial still use owner().
            response=toolResult(await connection(request,env,principal));
          }else if(params.name==='rdc_recent_operation_metrics'){
            response=toolResult(await recentMetrics(params.arguments??{},principal,env));
          }else if(params.name==='rdc_chat_session_status'){
            if(!object(params.arguments??{})||Object.keys(params.arguments??{}).length!==0)
              fail(400,'invalid_arguments','This read-only tool accepts no model-supplied identity or project.');
            response=toolResult(await chatSessionStatus(params._meta,principal,env));
          }else{
            if(params.name==='rdc_operation_status'){
              // Exact recovery still performs the original cleanup first.
              await clean(env);
              if(!text(params.arguments?.operation_id,100))fail(400,'invalid_arguments','operation_id is required.');
              const diagnostics=params.arguments?.diagnostics;
              if(diagnostics!==undefined&&typeof diagnostics!=='boolean')
                fail(400,'invalid_arguments','diagnostics must be a boolean.');
              const operation=await getOperation(params.arguments.operation_id,principal,env);
              response=diagnostics===true?toolResult(operationDiagnostics(operation)):await operationResult(operation,env);
            }else if(chatOpsByName.has(params.name)){
              const args=params.arguments??{};
              validateChatOp(params.name,args);
              if(!chatRouter||typeof chatRouter.invoke!=='function'){
                response=toolFailure('chat_bridge_not_enrolled','No authenticated live ChatGPT project/Atlas messenger has been installed. The request was not sent.');
              }else{
                const copy={...args};delete copy._rdc_request_id;
                try{
                  // Never trust _meta as an independent project grant. The
                  // injected host broker must verify session origin, project
                  // enrollment, per-project approval, exact recipient and its
                  // own durable no-replay receipt before any side effect.
                  const outcome=await chatRouter.invoke({name:params.name,args:copy,
                    request_key:args._rdc_request_id??null,principal,meta:params._meta??null});
                  if(!object(outcome)||typeof outcome.ok!=='boolean')
                    response=toolFailure('chat_broker_invalid','Chat broker returned no validated delivery result.');
                  else response=toolResult(outcome,outcome.ok!==true);
                }catch{
                  response=toolFailure('chat_broker_unavailable','Chat broker could not verify or perform this operation. No automatic replay will be attempted.');
                }
              }
            }else{
              try{
                response=await dispatch(params.name,params.arguments??{},principal,env,
                  fastWorkerTool?request:null);
              }catch(error){
                // The old transport checked the pinned owner before reporting
                // ANY malformed argument or worker error. Keep that privacy
                // guarantee on failed fast operations while skipping the
                // redundant D1 owner read on healthy successful admissions.
                if(fastWorkerTool)await owner(request,env);
                throw error;
              }
            }
          }
          break;
        }
        default:return json({jsonrpc:'2.0',id,error:{code:-32601,message:'Method not found'}},400);
      }
      // Required on the advertised modern wire and tolerated as extension
      // fields by legacy peers. Never advertise cacheability of device data.
      return json({jsonrpc:'2.0',id,result:{...response,resultType:'complete',
        ...(CACHEABLE_METHODS.has(message.method)?{ttlMs:0,cacheScope:'private'}:{})}});
    }catch(error){
      const known=error instanceof GatewayError;
      return json({jsonrpc:'2.0',id,error:{code:known?(error.rpcCode??(error.status===404?-32002:-32000)):-32603,
        message:known?error.message:'The RDC gateway is temporarily unavailable.',
        ...(known&&error.rpcCode!==undefined?(error.data===undefined?{}:{data:error.data}):{data:{code:known?error.code:'gateway_unavailable'}})}},known?error.status:503);
    }
  }
  async function poll(request,env){
    try{
      await device(request,env);const body=await readBody(request,4096);
      if(body.device_id!==env.RDC_DEVICE_ID)fail(403,'device_mismatch','This credential belongs to another device.');
      if(body.claim!==undefined&&typeof body.claim!=='boolean')fail(400,'invalid_request','claim must be a boolean.');
      if(body.observation_only!==undefined&&typeof body.observation_only!=='boolean')fail(400,'invalid_request','observation_only must be a boolean.');
      if(body.observation_only===true&&body.claim===false)fail(400,'invalid_request','An observer poll must claim an activity observation.');
      const heartbeat=env.DB.prepare('INSERT INTO gateway_device(id,last_seen_ms) VALUES (?,?) ON CONFLICT(id) DO UPDATE SET last_seen_ms=excluded.last_seen_ms').bind(env.RDC_DEVICE_ID,clock());
      // The original D1 claim is safe without a cleanup sweep: expired queue
      // rows are excluded by expires_ms. Complete work FIRST when it exists.
      // Heartbeat-only polls update liveness but never claim or retire work.
      // A primary empty poll performs bounded retention maintenance below.
      const stop=clock()+(body.claim===false||body.observation_only===true?0:L.pollWaitMs);
      let op=null, wakeHintCount=0;
      // Retain the private V2 channel's sequence cursor through the entire
      // long poll, rather than re-reading already-consumed wake hints.
      const notifier=body.claim===false?null:notifierFor(env);
      if(body.claim===false)await heartbeat.run();
      let firstClaim=true;
      if(body.claim!==false){
        do{
          const now=clock();
          // UUID order is random; the rowid table preserves admission order
          // when multiple queued operations share the same timestamp.
          const claimStatement=env.DB.prepare(`UPDATE gateway_operations SET state='claimed',claim_id=?,claimed_ms=?
            WHERE id=(SELECT id FROM gateway_operations WHERE device_id=? AND state='queued' AND expires_ms>?
              AND (?=0 OR (mutating=0 AND tool='rdc_preview_activity')) ORDER BY created_ms,rowid LIMIT 1)
              AND state='queued' RETURNING *`).bind(crypto.randomUUID(),now,env.RDC_DEVICE_ID,now,body.observation_only===true?1:0);
          if(firstClaim){
            firstClaim=false;
            if(typeof env.DB.batch==='function'){
              // D1 batches heartbeat and claim in one transaction and network
              // request. The conditional D1 claim remains authoritative.
              const results=await env.DB.batch([heartbeat,claimStatement]);
              if(!Array.isArray(results)||results.length!==2||!Array.isArray(results[1]?.results))
                fail(503,'gateway_unavailable','The D1 claim batch returned an invalid result.');
              op=results[1].results[0]??null;
            }else{
              // Older test/dev D1 adapters may lack batch support.
              await heartbeat.run();
              op=await claimStatement.first();
            }
          }else op=await claimStatement.first();
          if(op||clock()>=stop)break;
          const interval=Math.min(L.pollStepMs,stop-clock());
          if(notifier&&typeof notifier.wait==='function'&&wakeHintCount<3){
            // Wake signals are optional hints only. The durable D1 claim
            // remains authoritative, and a missed signal still falls back
            // to the normal bounded sweep instead of losing queued work.
            const started=clock();let signaled=false;
            try{signaled=(await notifier.wait(env.RDC_DEVICE_ID,interval))===true}
            catch{ /* A disconnected notifier must not interrupt the relay. */ }
            if(signaled)wakeHintCount++;
            if(!signaled){
              const remaining=Math.max(0,interval-(clock()-started));
              if(remaining>0)await sleep(remaining);
            }
          }else await sleep(interval);
        }while(clock()<=stop);
      }
      // Remove four or more D1 housekeeping probes from the critical queue
      // pickup and heartbeat paths. An idle primary poll still retires expired
      // operations and payloads; ordinary authenticated tool dispatch also
      // preserves its existing cleanup policy.
      if(body.claim!==false&&!op)await clean(env);
      return json({ok:true,device_id:env.RDC_DEVICE_ID,server_time_ms:clock(),poll_after_ms:250,
        observation_tools:['rdc_preview_activity'],observation_only:body.observation_only===true,
        operation:op?{operation_id:op.id,claim_id:op.claim_id,request_json:op.request_json,
          request_sha256:op.request_sha256,expires_at_ms:op.expires_ms}:null});
    }catch(error){return apiError(error);}
  }
  async function result(request,env){
    try{
      await device(request,env);const body=await readBody(request,L.maxUploadBytes);
      const resultBytes=typeof body.result_json==='string'?encoder.encode(body.result_json).length:0;
      if(resultBytes>L.maxResultBytes)
        fail(413,'result_too_large','The result exceeds the 12 MiB relay limit.');
      if(body.device_id!==env.RDC_DEVICE_ID)fail(403,'device_mismatch','This credential belongs to another device.');
      if(!text(body.operation_id,100)||!text(body.claim_id,100)||!text(body.request_sha256,64)||typeof body.result_json!=='string')
        fail(400,'invalid_result','An operation, claim, request hash and result_json are required.');
      const digest=await sha256(body.result_json);
      function validateMcpResult(){
        let value;
        try{value=JSON.parse(body.result_json)}
        catch{fail(400,'invalid_result','result_json must contain valid JSON.')}
        if(!object(value)||!Array.isArray(value.content)||value.content.length>1000||
          (value.isError!==undefined&&typeof value.isError!=='boolean'))
          fail(400,'invalid_result','A standard MCP CallToolResult is required.');
      }
      // Short results commit through one authoritative D1 statement.
      // The claim ID and request digest are checked by the UPDATE itself,
      // before ANY response bytes enter persistent storage. If refused, the
      // original lookup below still distinguishes duplicate and forged uploads.
      if(resultBytes<=L.maxInlineResultBytes){
        validateMcpResult();
        const now=clock();
        const committed=await env.DB.prepare(
          "UPDATE gateway_operations SET state='completed',completed_ms=?,result_key=NULL,"+
          "result_inline_json=?,result_sha256=?,result_size=?,"+
          "result_expires_ms=CASE WHEN tool IN ('rdc_preview_frame','rdc_preview_activity') THEN ? ELSE ? END,"+
          "request_json=NULL,request_size=0 "+
          "WHERE id=? AND device_id=? AND claim_id=? AND request_sha256=? "+
          "AND result_sha256 IS NULL AND state IN ('claimed','unknown') RETURNING id"
        ).bind(now,body.result_json,digest,resultBytes,
          now+L.frameTtlMs,now+L.resultTtlMs,body.operation_id,env.RDC_DEVICE_ID,
          body.claim_id,body.request_sha256).first();
        if(committed){
          const notifier=notifierFor(env);
          if(notifier&&typeof notifier.notifyResult==='function'){
            try{await notifier.notifyResult(env.RDC_DEVICE_ID,body.operation_id)}catch{}
          }
          return json({ok:true,operation_id:body.operation_id,status:'completed',duplicate:false});
        }
      }
      const op=await env.DB.prepare('SELECT * FROM gateway_operations WHERE id=? AND device_id=?').bind(body.operation_id,env.RDC_DEVICE_ID).first();
      if(!op)fail(404,'operation_not_found','The operation was not found.');
      if(op.claim_id!==body.claim_id||op.request_sha256!==body.request_sha256)
        fail(409,'claim_mismatch','The result does not match this claimed operation.');
      if(op.result_sha256){
        if(op.result_sha256!==digest)fail(409,'result_conflict','A different result is already recorded for this operation.');
        return json({ok:true,operation_id:op.id,status:'completed',duplicate:true});
      }
      if(!['claimed','unknown'].includes(op.state))fail(409,'operation_not_claimed','Only a claimed operation can receive a result.');
      validateMcpResult();
      const inline=resultBytes<=L.maxInlineResultBytes?body.result_json:null;
      const key=inline===null?`rdc-results/${env.RDC_DEVICE_ID}/${op.id}/${digest}.json`:null;
      // At most 8 KiB remains inline in the same committed D1 operation record.
      // Larger results remain durable in R2 before D1 advertises completion.
      // A lost acknowledgment only repeats the exact result upload, never work.
      // D1 failure after a large R2 PUT may still leave an orphan object.
      if(key!==null)await env.BUCKET.put(key,body.result_json,{httpMetadata:{contentType:'application/json'}});
      const completed=await env.DB.prepare(`UPDATE gateway_operations SET state='completed',completed_ms=?,result_key=?,result_inline_json=?,result_sha256=?,result_size=?,result_expires_ms=?,request_json=NULL,request_size=0
        WHERE id=? AND device_id=? AND result_sha256 IS NULL AND state IN ('claimed','unknown') RETURNING id`)
        .bind(clock(),key,inline,digest,resultBytes,clock()+(['rdc_preview_frame','rdc_preview_activity'].includes(op.tool)?L.frameTtlMs:L.resultTtlMs),op.id,env.RDC_DEVICE_ID).first();
      if(!completed){
        const current=await env.DB.prepare('SELECT result_sha256 FROM gateway_operations WHERE id=?').bind(op.id).first();
        if(current?.result_sha256!==digest){
          if(key!==null)await env.BUCKET.delete(key);
          fail(409,'result_conflict','A different result won the completion race.');
        }
      }else{
        // Notify only after the D1 result is committed. A dropped hint must
        // never discard the durable answer or cause a tool replay.
        const notifier=notifierFor(env);
        if(notifier&&typeof notifier.notifyResult==='function'){
          try{await notifier.notifyResult(env.RDC_DEVICE_ID,op.id)}catch{}
        }
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


/**
 * Post-migration rollback target: the same authenticated, owner-scoped reader
 * that understands BOTH v17 D1-inline and legacy R2 results, but a writer that
 * ALWAYS stores new results in R2. The historical v16 binary cannot read
 * inline-only rows and MUST NOT be selected as a post-inline rollback.
 *
 * Save a separate owner-private Sites version of this factory before activating
 * any inline writer. This function does not migrate, deploy or rewrite data.
 */
export function createRollbackCompatibleGateway(options){
  return createGateway({...options,limits:{...(options?.limits??{}),maxInlineResultBytes:0}});
}
