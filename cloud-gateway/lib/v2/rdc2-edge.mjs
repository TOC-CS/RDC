/**
 * RDC 2.0 owner-private Site gateway adapter.
 * Entire new route remains disabled without exact runtime opt-in.
 * Device Durable Object is the only journal; no v1 D1/R2 state is shared.
 */
const MAX_BODY=1_048_576;
const encoder=new TextEncoder();
const validObject=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
const validText=(value,length=256)=>typeof value==='string'&&value.length>0&&value.length<=length;
function reply(body,status=200){
  return Response.json(body,{status,headers:{'Cache-Control':'no-store'}});
}
function gatewayError(id,code,status=400){
  return reply({jsonrpc:'2.0',id,error:{code:-32000,message:'RDC 2.0 request unavailable.',
    data:{code}}},status);
}
function toolResult(value,isError=false){
  return {content:[{type:'text',text:JSON.stringify(value)}],
    structuredContent:value,isError};
}
function toolFailure(code){
  return toolResult({ok:false,error:{code}},true);
}
async function sha256(value){
  const digest=await crypto.subtle.digest('SHA-256',encoder.encode(value));
  return Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,'0')).join('');
}
async function equivalent(left,right){
  if(typeof left!=='string'||typeof right!=='string')return false;
  const [a,b]=await Promise.all([sha256(left),sha256(right)]);
  let mismatch=0;
  for(let i=0;i<a.length;i++)mismatch|=a.charCodeAt(i)^b.charCodeAt(i);
  return mismatch===0;
}
function canonical(value,depth=0){
  if(depth>48)throw new Error('nesting');
  if(Array.isArray(value))return value.map(x=>canonical(x,depth+1));
  if(validObject(value)){
    const result=Object.create(null);
    for(const key of Object.keys(value).sort())result[key]=canonical(value[key],depth+1);
    return result;
  }
  return value;
}
async function parseRequest(request){
  if(request.method!=='POST'||request.headers.get('Content-Type')?.split(';')[0].trim()!=='application/json')
    throw Error('method_or_content_type');
  const declared=request.headers.get('Content-Length');
  if(declared!==null&&(!/^\d+$/.test(declared)||Number(declared)>MAX_BODY))
    throw Error('invalid_length');
  const reader=request.body?.getReader();
  if(!reader)throw Error('missing_body');
  let length=0;const parts=[];
  while(true){
    const {done,value}=await reader.read();
    if(done)break;
    length+=value.byteLength;
    if(length>MAX_BODY){await reader.cancel();throw Error('body_too_large')}
    parts.push(value);
  }
  const bytes=new Uint8Array(length);let offset=0;
  for(const part of parts){bytes.set(part,offset);offset+=part.byteLength}
  const parsed=JSON.parse(new TextDecoder().decode(bytes));
  if(!validObject(parsed))throw Error('invalid_json');
  return parsed;
}
function isActive(env){
  return env?.RDC2_RUNTIME_ENABLED==='1';
}
function configured(env){
  return typeof env?.RDC2_DEVICE?.idFromName==='function'&&
    typeof env?.RDC2_DEVICE?.get==='function'&&
    validText(env?.RDC_DEVICE_ID,100)&&
    validText(env?.RDC2_INTERNAL_KEY,256)&&env.RDC2_INTERNAL_KEY.length>=32;
}
async function actorRequest(env,path,data){
  const address=env.RDC2_DEVICE.idFromName(env.RDC_DEVICE_ID);
  const stub=env.RDC2_DEVICE.get(address);
  const response=await stub.fetch(new Request('https://rdc2.internal'+path,{
    method:'POST',
    headers:{'Content-Type':'application/json','X-RDC2-Internal-Key':env.RDC2_INTERNAL_KEY},
    body:JSON.stringify(data)
  }));
  const result=await response.json();
  return {status:response.status,...result};
}
function completeOutput(data){
  if(data.state==='completed'&&typeof data.resultJson==='string'){
    try{
      const result=JSON.parse(data.resultJson);
      if(validObject(result)&&Array.isArray(result.content))
        return result;
    }catch{}
    return toolFailure('invalid_retained_result');
  }
  if(data.state==='unknown'||data.state==='expired'||data.state==='result_expired')
    return toolFailure(data.state);
  return toolResult({ok:true,pending:true,operation_id:data.id,status:data.state,
    recovery_tool:'rdc_operation_status'});
}

/** @param {{catalog?: Array<{name:string, description?:string, inputSchema:{properties?:Record<string,unknown>,required?:string[]}, "x-rdc-mutating"?:boolean}>}} options */
export function createRDC2Edge({catalog=[]}={}){
  const workerTools=new Map(catalog.filter(entry=>validText(entry.name,128))
    .map(entry=>[entry.name,entry]));
  const metadata=[...workerTools.values()].map(item=>{
    const tool=structuredClone(item);
    const requiresId=item['x-rdc-mutating']===true;
    tool.inputSchema.properties={...tool.inputSchema.properties,
      _rdc_request_id:{type:'string',minLength:1,maxLength:200}};
    tool.inputSchema.required=[...(tool.inputSchema.required??[]),
      ...(requiresId?['_rdc_request_id']:[])];
    delete tool['x-rdc-mutating'];
    return tool;
  });
  metadata.push({name:'rdc_connection_status',
    description:'Private RDC 2.0 device online and queue status.',
    inputSchema:{type:'object',properties:{},additionalProperties:false}});
  metadata.push({name:'rdc_operation_status',
    description:'Recover original RDC 2.0 operation only; never replay.',
    inputSchema:{type:'object',properties:{operation_id:{type:'string',minLength:1,maxLength:100}},
      required:['operation_id'],additionalProperties:false}});
  async function mcp(request,env){
    if(!isActive(env))return gatewayError(null,'v2_disabled',404);
    if(!configured(env))return gatewayError(null,'v2_not_configured',503);
    let id=null;
    try{
      const body=await parseRequest(request);
      id=body.id??null;
      if(body.jsonrpc!=='2.0'||!validText(body.method,100))
        return gatewayError(id,'invalid_jsonrpc',400);
      if(body.method==='initialize')
        return reply({jsonrpc:'2.0',id,result:{protocolVersion:'2025-11-25',
          serverInfo:{name:'rdc-v2',version:'2.0.0-dev'},
          capabilities:{tools:{listChanged:false}}}});
      if(body.method==='tools/list')
        return reply({jsonrpc:'2.0',id,result:{tools:metadata}});
      if(body.method!=='tools/call'||!validObject(body.params)||
        !validText(body.params.name,128))
        return gatewayError(id,'invalid_method',400);
      // The private ChatGPT Site must have authenticated and injected this
      // original user identity. A model-supplied principal is never accepted.
      const principal=request.headers.get('oai-authenticated-user-id');
      if(!validText(principal,256))return gatewayError(id,'sign_in_required',401);
      // The V2 actor performs first enrollment or exact owner equality
      // inside this same private actor fetch, saving one network roundtrip.
      const name=body.params.name,args=body.params.arguments??{};
      if(!validObject(args))return gatewayError(id,'invalid_arguments',400);
      let outcome;
      if(name==='rdc_connection_status')
        outcome=await actorRequest(env,'/v2/status',{principal});
      else if(name==='rdc_operation_status'){
        if(!validText(args.operation_id,100))return gatewayError(id,'invalid_arguments',400);
        outcome=await actorRequest(env,'/v2/recover',{principal,id:args.operation_id});
      }else{
        const tool=workerTools.get(name);
        if(!tool)return gatewayError(id,'unknown_tool',400);
        const mutating=tool['x-rdc-mutating']===true;
        const requestKey=args._rdc_request_id;
        if(mutating&&!validText(requestKey,200))
          return gatewayError(id,'request_id_required',400);
        if(requestKey!==undefined&&!validText(requestKey,200))
          return gatewayError(id,'invalid_request_id',400);
        const localArgs={...args};
        delete localArgs._rdc_request_id;
        const requestJson=JSON.stringify({name,arguments:canonical(localArgs)});
        if(encoder.encode(requestJson).length>MAX_BODY)
          return gatewayError(id,'payload_too_large',413);
        const requestDigest=await sha256(requestJson);
        outcome=await actorRequest(env,'/v2/admit_wait',{principal,
          requestKey:requestKey??crypto.randomUUID(),requestDigest,requestJson,
          tool:name,mutating,waitMs:2500});
      }
      if(!outcome.ok)
        return gatewayError(id,outcome.error?.code??'operation_unavailable',outcome.status);
      const result=name==='rdc_connection_status'?
        toolResult({ok:true,device_id:env.RDC_DEVICE_ID,
          online:outcome.online,last_seen_ms:outcome.lastSeenMs,
          pending_operations:outcome.pending,protocol_version:2}):
        completeOutput(outcome);
      return reply({jsonrpc:'2.0',id,result});
    }catch{
      return gatewayError(id,'v2_unavailable',503);
    }
  }
  async function deviceSocket(request,env){
    if(!isActive(env))return reply({ok:false,error:{code:'v2_disabled'}},404);
    if(!configured(env)||!validText(env.RDC_DEVICE_SECRET,256)||
       env.RDC_DEVICE_SECRET.length<32)
      return reply({ok:false,error:{code:'v2_not_configured'}},503);
    const credential=request.headers.get('X-RDC-Device-Key');
    if(!await equivalent(credential,env.RDC_DEVICE_SECRET))
      return reply({ok:false,error:{code:'invalid_device_key'}},401);
    if(request.method!=='GET'||request.headers.get('Upgrade')?.toLowerCase()!=='websocket')
      return reply({ok:false,error:{code:'upgrade_required'}},426);
    const stub=env.RDC2_DEVICE.get(env.RDC2_DEVICE.idFromName(env.RDC_DEVICE_ID));
    return await stub.fetch(new Request('https://rdc2.internal/v2/socket',{
      method:'GET',headers:{Upgrade:'websocket',
        'X-RDC2-Internal-Key':env.RDC2_INTERNAL_KEY}
    }));
  }
  return {mcp,deviceSocket};
}
