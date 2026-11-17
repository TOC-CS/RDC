import {randomUUID} from 'node:crypto';

/**
 * Optional RDC presentation-output adapter.
 *
 * The host injects only currently authorized tool handlers and an exact,
 * source-bound RDC session. There are no physical keyboard/mouse operations
 * in this package. Actual UI tool access remains with RDC's own worker and
 * owner permissions, including any foreground-takeover decision.
 */
export const BRIDGE_PROTOCOL_VERSION='rdc.presentation.v1';
const NAME_PATTERN=/^[A-Za-z0-9._:-]{1,128}$/;
const SOURCE_PATTERN=/^(?:window|browser|mobile)-[A-Za-z0-9._:-]{1,128}$/;
const ACTIONS=new Set(['next','previous','goto']);

function requireName(value,label,pattern=NAME_PATTERN){
 if(typeof value!=='string'||!pattern.test(value))throw new Error('Invalid '+label+' identity.');
 return value;
}
function verifiedIndex(value){
 if(!Number.isInteger(value)||value<0||value>10000)
   throw new Error('A validated presentation slide index is required.');
 return value;
}
function failIfMisbound(record,deviceId,sourceId){
 if(!record||record.deviceId!==deviceId||record.sourceId!==sourceId)
   throw new Error('RDC presentation source/device identity mismatch.');
}

export class RdcPresentationAdapter{
 constructor({
   deviceId,sourceId,transport,authorize,clock=()=>Date.now(),
   ttlMs=2500,timeoutMs=12000
 }={}){
   this.deviceId=requireName(deviceId,'device');
   this.sourceId=requireName(sourceId,'source',SOURCE_PATTERN);
   if(!transport||typeof transport.execute!=='function')
     throw new Error('An existing RDC source-bound transport execute function is required.');
   if(typeof authorize!=='function')throw new Error('An explicit per-action RDC authorization function is required.');
   if(typeof clock!=='function')throw new Error('A presentation clock is required.');
   if(!Number.isInteger(ttlMs)||ttlMs<300||ttlMs>10000)throw new Error('Invalid RDC deadline window.');
   if(!Number.isInteger(timeoutMs)||timeoutMs<500||timeoutMs>60000)throw new Error('Invalid RDC wait timeout.');
   this.transport=transport;
   this.authorize=authorize;
   this.clock=clock;
   this.ttlMs=ttlMs;
   this.timeoutMs=timeoutMs;
   this.external=true;
   this.name='rdc-source-bound';
 }
 async checkPermission(action){
   const grant=await this.authorize({
     protocol:BRIDGE_PROTOCOL_VERSION,deviceId:this.deviceId,sourceId:this.sourceId,action
   });
   if(grant?.allowed!==true||grant?.deviceId!==this.deviceId||
       grant?.sourceId!==this.sourceId||
       (grant.action!==undefined&&grant.action!==action))
     throw new Error('RDC presentation command denied by source-bound operator authorization.');
 }
 async waitBounded(promise){
   let timer;
   try{
     return await Promise.race([
       promise,
       new Promise((_,reject)=>{
         timer=setTimeout(()=>reject(new Error('RDC presentation outcome unknown after timeout; inspect the original command receipt before any retry.')),this.timeoutMs);
       })
     ]);
   }finally{clearTimeout(timer);}
 }
 async readback({expectedIndex}={}){
   await this.checkPermission('readback');
   return this.#readState({expectedIndex});
 }
 async #readState({expectedIndex}={}){
   if(typeof this.transport.readState!=='function')
     return {supported:false,confirmed:false,reason:'readback_unavailable',sourceId:this.sourceId,deviceId:this.deviceId};
   const state=await this.waitBounded(Promise.resolve().then(()=>this.transport.readState({
     protocol:BRIDGE_PROTOCOL_VERSION,deviceId:this.deviceId,sourceId:this.sourceId
   })));
   failIfMisbound(state,this.deviceId,this.sourceId);
   const current=verifiedIndex(state.currentSlideIndex);
   return {
     supported:true,confirmed:Number.isInteger(expectedIndex)&&current===expectedIndex,
     index:current,sourceId:this.sourceId,deviceId:this.deviceId,source:'rdc-source-bound-readback'
   };
 }
 async execute(action,index){
   if(!ACTIONS.has(action))throw new Error('Unsupported RDC presentation action.');
   await this.checkPermission(action);
   // All output commands are bound to a known 0-based slide position. This is
   // normally provided by PresentationDirector as slide.position.
   const position=verifiedIndex(index);
   const now=this.clock();
   if(!Number.isFinite(now)||now<0)throw new Error('Invalid monotonic command timestamp.');
   const command={
     protocol:BRIDGE_PROTOCOL_VERSION,deviceId:this.deviceId,sourceId:this.sourceId,
     commandId:randomUUID(),action,index:position,issuedAt:now,expiresAt:now+this.ttlMs
   };
   // Do not resend a pending or unknown command automatically.
   const receipt=await this.waitBounded(Promise.resolve().then(()=>this.transport.execute(command)));
   failIfMisbound(receipt,this.deviceId,this.sourceId);
   if(receipt.commandId!==command.commandId)
     throw new Error('RDC command receipt identity mismatch.');
   if(receipt.status!=='applied')
     throw new Error('RDC presentation command pending or outcome unknown. Inspect original receipt before retry.');
   const observed=await this.#readState({expectedIndex:position});
   if(!observed.supported||!observed.confirmed)
     throw new Error('RDC presentation readback mismatch or unavailable. Display change remains unverified.');
   return {
     ok:true,confirmed:true,index:position,sourceId:this.sourceId,
     commandId:command.commandId,readback:observed
   };
 }
 async show(index){return this.execute('goto',index);}
 async next(slide){return this.execute('next',slide?.position);}
 async previous(slide){return this.execute('previous',slide?.position);}
}
