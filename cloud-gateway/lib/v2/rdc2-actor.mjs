/**
 * RDC 2.0 private per-device Durable Object transport actor.
 * Only an authenticated gateway may reach this future binding. This module
 * creates no public route or credentials and is not enabled by default.
 * Durable SQLite commits precede any best-effort WebSocket hint.
 */
import {RDC2Journal,RDC2Error} from './rdc2-journal.mjs';

const encoder=new TextEncoder();
const decoder=new TextDecoder();
const MAX_BODY=1_572_864;
const MAX_BULK_BODY=16*1024*1024;
const MAX_FRAME=1_572_864;
const DEVICE_TAG='rdc2-device';
const workHint=JSON.stringify({version:2,type:'work_available'});
const hexBytes=value=>Array.from(new Uint8Array(value),byte=>byte.toString(16).padStart(2,'0')).join('');
const validObject=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
const validHex=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
async function digest(value){
  return hexBytes(await crypto.subtle.digest('SHA-256',encoder.encode(value)));
}
async function equivalent(left,right){
  if(typeof left!=='string'||typeof right!=='string')return false;
  const [a,b]=await Promise.all([digest(left),digest(right)]);
  let mismatch=0;
  for(let i=0;i<a.length;i++)mismatch|=a.charCodeAt(i)^b.charCodeAt(i);
  return mismatch===0;
}
async function body(request,maxBytes=MAX_BODY){
  if(request.headers.get('Content-Type')?.split(';')[0]?.trim()!=='application/json')
    throw new RDC2Error('content_type',415);
  const declared=request.headers.get('Content-Length');
  if(declared!==null&&(!/^\d+$/.test(declared)||Number(declared)>maxBytes))
    throw new RDC2Error('payload_too_large',413);
  const reader=request.body?.getReader();
  if(!reader)throw new RDC2Error('invalid_json');
  let total=0;const parts=[];
  while(true){
    const {done,value}=await reader.read();
    if(done)break;
    total+=value.byteLength;
    if(total>maxBytes){await reader.cancel();throw new RDC2Error('payload_too_large',413)}
    parts.push(value);
  }
  const data=new Uint8Array(total);
  let index=0;for(const part of parts){data.set(part,index);index+=part.byteLength}
  try{
    const parsed=JSON.parse(decoder.decode(data));
    if(!validObject(parsed))throw new Error('not-object');
    return parsed;
  }catch{throw new RDC2Error('invalid_json')}
}
function response(data,status=200){
  return Response.json(data,{status,headers:{'Cache-Control':'no-store'}});
}
function errorResult(error){
  const known=error instanceof RDC2Error;
  return response({ok:false,error:{code:known?error.code:'v2_unavailable'}},known?error.status:503);
}
export class RDC2DeviceActor {
  constructor(state,env,options={}){
    this.state=state;
    this.env=env;
    this.journal=new RDC2Journal(state.storage,options);
    this.resultWaiters=new Map();
  }
  authorizePrincipal(principal){
    return this.journal.bindOwner(principal,{
      bootstrap:this.env?.RDC2_OWNER_BOOTSTRAP==='private-site'
    });
  }
  activeSockets(){
    return typeof this.state.getWebSockets==='function'?
      this.state.getWebSockets(DEVICE_TAG):[];
  }
  notifyWork(){
    for(const socket of this.activeSockets()){
      try{socket.send(workHint)}catch{ /* missed hint never replays a durable claim */ }
    }
  }
  notifyResult(id){
    const hint=JSON.stringify({version:2,type:'result_available',id});
    for(const socket of this.activeSockets()){
      try{socket.send(hint)}catch{ /* journal is authoritative */ }
    }
    for(const finish of [...(this.resultWaiters.get(id)??[])])finish();
  }
  async waitForResult(principal,id,waitMs){
    const initial=this.journal.recover(principal,id);
    if(!['queued','claimed'].includes(initial.state))return initial;
    return await new Promise((resolve,reject)=>{
      let group=this.resultWaiters.get(id);
      if(!group){group=new Set();this.resultWaiters.set(id,group)}
      let settled=false,timer;
      const finish=()=>{
        if(settled)return;
        settled=true;clearTimeout(timer);group.delete(finish);
        if(group.size===0)this.resultWaiters.delete(id);
        try{resolve(this.journal.recover(principal,id))}
        catch(error){reject(error)}
      };
      group.add(finish);
      timer=setTimeout(finish,waitMs);
      // Check after registering to close the commit-to-listen race.
      const latest=this.journal.recover(principal,id);
      if(!['queued','claimed'].includes(latest.state))finish();
    });
  }
  async verifyPayload(raw,expected){
    if(typeof raw!=='string'||!validHex(expected)||await digest(raw)!==expected)
      throw new RDC2Error('digest_mismatch',409);
  }
  async hydrateResult(result){
    if(result.state!=='completed'||!result.resultKey)return result;
    if(typeof this.env?.BUCKET?.get!=='function')
      throw new RDC2Error('result_store_unavailable',503);
    let stored;
    try{stored=await this.env.BUCKET.get(result.resultKey)}
    catch{throw new RDC2Error('result_store_unavailable',503)}
    if(!stored)throw new RDC2Error('result_unavailable',503);
    let raw;
    try{raw=await stored.text()}
    catch{throw new RDC2Error('result_unavailable',503)}
    if(typeof raw!=='string'||encoder.encode(raw).length>this.journal.limits.maxBulkResultBytes)
      throw new RDC2Error('result_unavailable',503);
    await this.verifyPayload(raw,result.resultDigest);
    return {id:result.id,state:'completed',resultJson:raw};
  }
  async completeBulk(args){
    if(typeof this.env?.BUCKET?.put!=='function')
      throw new RDC2Error('result_store_unavailable',503);
    await this.verifyPayload(args.resultJson,args.resultDigest);
    const size=encoder.encode(args.resultJson).length;
    if(size<=this.journal.limits.maxResultBytes||
       size>this.journal.limits.maxBulkResultBytes)
      throw new RDC2Error('payload_too_large',413);
    let parsed;
    try{parsed=JSON.parse(args.resultJson)}
    catch{throw new RDC2Error('invalid_result')}
    if(!validObject(parsed)||!Array.isArray(parsed.content)||parsed.content.length>1000||
       (parsed.isError!==undefined&&typeof parsed.isError!=='boolean'))
      throw new RDC2Error('invalid_result');
    const eligible=this.journal.preflightExternalCompletion(args);
    if(eligible.duplicate)return eligible;
    const resultKey='rdc2-results/'+args.id+'/'+args.resultDigest+'.json';
    try{
      await this.env.BUCKET.put(resultKey,args.resultJson,{
        httpMetadata:{contentType:'application/json'}
      });
    }catch{throw new RDC2Error('result_store_unavailable',503)}
    // Store the pointer only AFTER original result bytes become durable.
    // If metadata commit fails, the orphan can be cleaned without replay.
    const completed=this.journal.completeExternal({...args,resultKey,resultSize:size});
    if(!completed.duplicate)this.notifyResult(completed.id);
    return completed;
  }
  async retireExternal(){
    const expired=this.journal.expiredExternal(16);
    if(expired.length&&typeof this.env?.BUCKET?.delete!=='function')
      throw new RDC2Error('result_store_unavailable',503);
    for(const entry of expired){
      try{await this.env.BUCKET.delete(entry.resultKey)}
      catch{throw new RDC2Error('result_store_unavailable',503)}
      this.journal.clearExpiredExternal(entry.id,entry.resultKey);
    }
  }
  async fetch(request){
    try{
      const secret=this.env?.RDC2_INTERNAL_KEY;
      const provided=request.headers.get('X-RDC2-Internal-Key');
      if(typeof secret!=='string'||secret.length<32)
        throw new RDC2Error('gateway_unavailable',503);
      if(!await equivalent(provided,secret))throw new RDC2Error('unauthorized',401);
      const path=new URL(request.url).pathname;
      if(path==='/v2/socket'){
        if(request.method!=='GET'||request.headers.get('Upgrade')?.toLowerCase()!=='websocket')
          throw new RDC2Error('upgrade_required',426);
        if(typeof this.state.acceptWebSocket!=='function')
          throw new RDC2Error('websocket_unavailable',503);
        const pair=new WebSocketPair();
        const worker=pair[0],server=pair[1];
        this.state.acceptWebSocket(server,[DEVICE_TAG]);
        const status=this.journal.first("SELECT 1 AS has_work FROM rdc2_ops WHERE state='queued' AND expires_ms>? LIMIT 1",this.journal.now());
        if(status)server.send(workHint);
        return new Response(null,{status:101,webSocket:worker});
      }
      if(request.method!=='POST')throw new RDC2Error('method_not_allowed',405);
      const args=await body(request,path==='/v2/complete_bulk'?MAX_BULK_BODY:MAX_BODY);
      let data;
      switch(path){
        case '/v2/bind':
          if(args.bootstrap===true&&this.env?.RDC2_OWNER_BOOTSTRAP!=='private-site')
            throw new RDC2Error('bootstrap_denied',403);
          data={principal:this.journal.bindOwner(args.principal,{bootstrap:args.bootstrap===true})};break;
        case '/v2/heartbeat':
          data=this.journal.heartbeat();break;
        case '/v2/status':
          this.authorizePrincipal(args.principal);
          data=this.journal.status(args.principal);break;
        case '/v2/admit':{
          this.authorizePrincipal(args.principal);
          await this.verifyPayload(args.requestJson,args.requestDigest);
          data=this.journal.enqueue(args);
          if(!data.reused)this.notifyWork();
          break;
        }
        case '/v2/admit_wait':{
          this.authorizePrincipal(args.principal);
          if(!Number.isInteger(args.waitMs)||args.waitMs<1||args.waitMs>5_000)
            throw new RDC2Error('invalid_wait');
          await this.verifyPayload(args.requestJson,args.requestDigest);
          const admitted=this.journal.enqueue(args);
          if(!admitted.reused)this.notifyWork();
          data=await this.hydrateResult(await this.waitForResult(args.principal,admitted.id,args.waitMs));
          break;
        }
        case '/v2/claim':
          data={operation:this.journal.claim()};break;
        case '/v2/complete':
          await this.verifyPayload(args.resultJson,args.resultDigest);
          data=this.journal.complete(args);
          if(!data.duplicate)this.notifyResult(data.id);
          break;
        case '/v2/complete_bulk':
          data=await this.completeBulk(args);break;
        case '/v2/recover':
          this.authorizePrincipal(args.principal);
          data=await this.hydrateResult(this.journal.recover(args.principal,args.id));break;
        case '/v2/sweep':
          await this.retireExternal();
          this.journal.sweep();data={swept:true};break;
        default:throw new RDC2Error('unknown_route',404);
      }
      return response({ok:true,...data});
    }catch(error){return errorResult(error)}
  }
  // Hibernation callback. Connections reach this handler only after the
  // gateway's authenticated, privately bound /v2/socket upgrade.
  async webSocketMessage(socket,message){
    const send=payload=>{
      try{socket.send(JSON.stringify({version:2,...payload}))}catch{}
    };
    if(typeof message!=='string'||encoder.encode(message).length>MAX_FRAME){
      send({type:'protocol_error',code:'invalid_frame'});return;
    }
    let frame;
    try{frame=JSON.parse(message)}
    catch{send({type:'protocol_error',code:'invalid_frame'});return}
    if(!validObject(frame)||frame.version!==2||typeof frame.type!=='string'){
      send({type:'protocol_error',code:'invalid_frame'});return;
    }
    try{
      if(frame.type==='heartbeat'){
        send({type:'heartbeat_ack',...this.journal.heartbeat()});return;
      }
      if(frame.type==='claim'){
        const operation=this.journal.claim();
        // The original server clock is required for conservative,
        // drift-safe worker execution deadlines.
        send({type:'claimed',operation:operation?
          {...operation,serverTimeMs:this.journal.now()}:null});return;
      }
      if(frame.type==='complete'){
        await this.verifyPayload(frame.resultJson,frame.resultDigest);
        const result=this.journal.complete(frame);
        if(!result.duplicate)this.notifyResult(result.id);
        send({type:'result_ack',id:result.id,duplicate:result.duplicate});return;
      }
      send({type:'protocol_error',code:'unknown_frame'});
    }catch(error){
      send({type:'operation_error',code:error instanceof RDC2Error?error.code:'v2_unavailable'});
    }
  }
  async webSocketClose(socket,code,reason){
    // Honor Cloudflare's hibernation close handshake. Never resume a
    // claimed device action merely because its socket was closed.
    try{
      if(Number.isInteger(code)&&code>=1000&&code<5000&&
        ![1004,1005,1006,1015].includes(code))socket.close(code,reason);
      else socket.close();
    }catch{ /* already closed/disconnected */ }
  }
}
