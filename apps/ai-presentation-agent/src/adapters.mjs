import {spawn} from 'node:child_process';
import {createHash,randomUUID} from 'node:crypto';
import {URL} from 'node:url';
import {PowerPointWindowsAdapter} from './windows-powerpoint.mjs';
function fail(message){throw new Error(message);}
function requirePrivateUrl(raw){
 const url=new URL(raw);
 if(!['http:','ws:'].includes(url.protocol)||url.username||url.password||url.search||url.hash||url.pathname!=='/')
   fail('Presentation endpoints require plain HTTP/WebSocket on a local or private network.');
 const h=url.hostname.toLowerCase().replace(/^\[|\]$/g,'');
 const segments=h.split('.').map(Number);
 const allowed=h==='localhost'||h==='::1'||h.endsWith('.local')||h==='127.0.0.1'||
  (/^\d+\.\d+\.\d+\.\d+$/.test(h)&&segments.length===4&&
   segments.every(v=>Number.isInteger(v)&&v>=0&&v<=255)&&(
      segments[0]===10||segments[0]===127||segments[0]===192&&segments[1]===168||
      segments[0]===172&&segments[1]>=16&&segments[1]<=31));
 if(!allowed)fail('Only loopback or private network presentation endpoints are permitted.');
 return url;
}
function positiveIndex(n){if(!Number.isInteger(n)||n<0||n>10000)fail('Invalid slide index.');return n;}
export class MemoryAdapter{
 constructor(){this.name='memory';this.external=false;this.events=[];}
 async show(index,slide){this.events.push({op:'goto',index,slide});return {ok:true};}
 async next(slide){this.events.push({op:'next',slide});return {ok:true};}
 async previous(slide){this.events.push({op:'previous',slide});return {ok:true};}
}
export class ProPresenterAdapter{
 constructor({baseUrl='http://127.0.0.1:50001',fetcher=fetch,presentationId=null,timeoutMs=1500}={}){
   const url=requirePrivateUrl(baseUrl);
   this.baseUrl=url.toString();this.fetcher=fetcher;this.presentationId=presentationId;
   this.timeoutMs=timeoutMs;this.name='propresenter';this.external=true;
   this.requiresReadback=true;
 }
 async request(path){
   const url=new URL(path,this.baseUrl);
   if(url.origin!==new URL(this.baseUrl).origin)fail('Unsafe cross-host presentation request.');
   const response=await this.fetcher(url,{method:'GET',signal:AbortSignal.timeout(this.timeoutMs),redirect:'error'});
   if(!response.ok)fail('ProPresenter API returned HTTP '+response.status);
   return {ok:true,status:response.status};
 }
 async status(){return this.readback();}
 async readback({expectedIndex=null,expectedPresentationId=null}={}){
   const url=new URL('/v1/presentation/slide_index',this.baseUrl);
   if(url.origin!==new URL(this.baseUrl).origin)
     fail('Unsafe cross-host presentation readback.');
   const response=await this.fetcher(url,{method:'GET',signal:AbortSignal.timeout(this.timeoutMs),redirect:'error'});
   if(!response.ok)fail('ProPresenter readback returned HTTP '+response.status);
   if(typeof response.json!=='function')fail('ProPresenter readback did not supply JSON.');
   let payload;
   try{payload=await response.json();}
   catch{fail('Invalid ProPresenter readback response.');}
   if(payload?.presentation===null)
     return {supported:true,confirmed:false,index:null,source:'propresenter-api',reason:'no_active_presentation'};
   const index=payload?.presentation?.index;
   if(!Number.isSafeInteger(index)||index<0)
     fail('Invalid active ProPresenter cue index.');
   const rawId=payload.presentation.presentation_id;
   const presentationId=typeof rawId==='string'?rawId:
     typeof rawId?.uuid==='string'?rawId.uuid:null;
   const identityOk=expectedPresentationId===null ||
     (typeof presentationId==='string'&&presentationId.toLowerCase()===expectedPresentationId.toLowerCase());
   return {supported:true,confirmed:Number.isInteger(expectedIndex)&&index===expectedIndex&&identityOk,
     index,presentationId,source:'propresenter-api'};
 }
 async next(){return this.request('/v1/presentation/active/next/trigger');}
 async previous(){return this.request('/v1/presentation/active/previous/trigger');}
 async goto(index,{presentationId=this.presentationId}={}){
   positiveIndex(index);
   if(!presentationId||!/^[A-Za-z0-9-]{1,80}$/.test(presentationId))
     fail('ProPresenter cue targeting requires a presentation ID.');
   return this.request('/v1/presentation/'+encodeURIComponent(presentationId)+'/'+index+'/trigger');
 }
 async show(index,slide){
   return this.goto(Number.isInteger(slide?.targetIndex)?slide.targetIndex:index,
     {presentationId:slide?.presentationId??this.presentationId});
 }
}
function guardRunningMacApp(app,command,{requiresPlaying=false}={}){
 // AppleScript normally auto-launches addressed applications. Refuse any
 // native command unless the presentation app is already running.
 // The Keynote dictionary reports playing=true only for an active show.
 const active=requiresPlaying?
   'if (get playing of application "Keynote") is false then error "No Keynote slideshow is playing."\n':'';
 return 'if application "'+app+'" is not running then error "'+app+' is not running."\n'+active+command;
}
export function buildKeynoteScript(action,index){
 const operations={next:'show next',previous:'show previous'};
 if(action==='readback')
   return guardRunningMacApp('Keynote','tell application "Keynote" to get slide number of current slide of front document');
 if(action==='goto'){
   positiveIndex(index);
   // Keynote legacy scripting dictionary exposes "show" on a slide.
   return guardRunningMacApp('Keynote','tell application "Keynote" to show slide '+String(index+1)+' of front document',{requiresPlaying:true});
 }
 if(!Object.hasOwn(operations,action))fail('Unsupported Keynote action.');
 return guardRunningMacApp('Keynote','tell application "Keynote" to '+operations[action],{requiresPlaying:true});
}
export function buildPowerPointScript(action,index){
 const begin='tell application "Microsoft PowerPoint" to ';
 const view='slideshow view of slide show window 1';
 if(action==='next')return guardRunningMacApp('Microsoft PowerPoint',begin+'go to next slide ('+view+')');
 if(action==='previous')return guardRunningMacApp('Microsoft PowerPoint',begin+'go to previous slide ('+view+')');
 if(action==='readback')return guardRunningMacApp('Microsoft PowerPoint',begin+'get current show position of '+view);
 if(action==='goto'){
   positiveIndex(index);
   return guardRunningMacApp('Microsoft PowerPoint',begin+'go to slide ('+view+') number '+String(index+1));
 }
 fail('Unsupported PowerPoint action.');
}
function runScript(script,{executor=spawn,timeoutMs=4500}={}){
 if(!Number.isInteger(timeoutMs)||timeoutMs<50||timeoutMs>30000)
   throw new Error('Mac presentation command timeout must be 50 to 30000 milliseconds.');
 return new Promise((resolve,reject)=>{
   let child;
   try{
     child=executor('/usr/bin/osascript',['-e',script],{stdio:['ignore','pipe','pipe']});
   }catch(error){reject(error);return;}
   let err='',out='',settled=false;
   const finish=(error,value)=>{
     if(settled)return;settled=true;clearTimeout(timer);
     return error?reject(error):resolve(value);
   };
   const timer=setTimeout(()=>{
     finish(new Error('Mac presentation automation timed out.'));
     try{child.kill?.('SIGTERM');}catch{}
   },timeoutMs);
   child.stdout?.on('data',chunk=>{if(out.length<2048)out+=chunk.toString().slice(0,2048-out.length);});
   child.stderr?.on('data',chunk=>{if(err.length<2048)err+=chunk.toString().slice(0,2048-err.length);});
   child.once('error',error=>finish(error));
   child.once('exit',code=>code===0?
     finish(null,{ok:true,response:out.trim()}):
     finish(new Error('Mac presentation automation failed ('+code+'): '+err.trim())));
 });
}
function parseAppleSlideNumber(value){
 const raw=String(value??'').trim();
 if(!/^[1-9][0-9]{0,5}$/.test(raw))fail('AppleScript returned an invalid slide position.');
 const n=Number(raw);
 if(!Number.isSafeInteger(n)||n>10001)fail('AppleScript returned an invalid slide index.');
 return n-1;
}
export class KeynoteAdapter{
 constructor(opts={}){this.name='keynote-macos';this.timeoutMs=opts.timeoutMs??4500;this.external=true;this.executor=opts.executor??spawn;}
 async show(index){return runScript(buildKeynoteScript('goto',index),{executor:this.executor,timeoutMs:this.timeoutMs});}
 async next(){return runScript(buildKeynoteScript('next'),{executor:this.executor,timeoutMs:this.timeoutMs});}
 async previous(){return runScript(buildKeynoteScript('previous'),{executor:this.executor,timeoutMs:this.timeoutMs});}
 async readback({expectedIndex=null}={}){
   const output=await runScript(buildKeynoteScript('readback'),{executor:this.executor,timeoutMs:this.timeoutMs});
   const index=parseAppleSlideNumber(output.response);
   // Keynote's dictionary exposes the selected slide. It does not itself
   // prove the audience projection is showing this specific frame.
   return {supported:true,confirmed:false,index,positionMatches:index===expectedIndex,
      source:'keynote-selected-slide-applescript'};
 }
}
export class PowerPointMacAdapter{
 constructor(opts={}){this.name='powerpoint-macos';this.timeoutMs=opts.timeoutMs??4500;this.external=true;this.executor=opts.executor??spawn;this.requiresReadback=true;}
 async show(index){return runScript(buildPowerPointScript('goto',index),{executor:this.executor,timeoutMs:this.timeoutMs});}
 async next(){return runScript(buildPowerPointScript('next'),{executor:this.executor,timeoutMs:this.timeoutMs});}
 async previous(){return runScript(buildPowerPointScript('previous'),{executor:this.executor,timeoutMs:this.timeoutMs});}
 async readback({expectedIndex=null}={}){
   const output=await runScript(buildPowerPointScript('readback'),{executor:this.executor,timeoutMs:this.timeoutMs});
   const index=parseAppleSlideNumber(output.response);
   return {supported:true,confirmed:Number.isInteger(expectedIndex)&&index===expectedIndex,
      index,source:'powerpoint-macos-applescript'};
 }
}
export function obsWebsocketAuth(password,salt,challenge){
 const sha=(s)=>createHash('sha256').update(s).digest('base64');
 return sha(sha(password+salt)+challenge);
}
export class OBSAdapter{
 constructor({url='ws://127.0.0.1:4455/',password=process.env.OBS_WEBSOCKET_PASSWORD??'',WebSocketCtor=globalThis.WebSocket,timeoutMs=1800}={}){
   requirePrivateUrl(url);
   if(!WebSocketCtor)throw new Error('WebSocket support unavailable on this Node version.');
   this.url=url;this.password=password;this.WebSocketCtor=WebSocketCtor;
   this.timeoutMs=timeoutMs;this.name='obs';this.external=true;
 }
 async show(index,slide){
   if(!slide||typeof slide.scene!=='string'||!slide.scene.trim())
     fail('An OBS target slide must specify a scene name.');
   const socket=new this.WebSocketCtor(this.url);
   return await new Promise((resolve,reject)=>{
     let settled=false,identified=false,expectedRequestId=null,phase='idle';
     const finish=(error,result)=>{
       if(settled)return;settled=true;clearTimeout(timeout);
       try{socket.close();}catch{}
       return error?reject(error):resolve(result);
     };
     const timeout=setTimeout(()=>finish(new Error('OBS control timeout.')),this.timeoutMs);
     socket.addEventListener('error',()=>finish(new Error('OBS WebSocket connection failed.')));
     socket.addEventListener('close',()=>{if(!settled)finish(new Error('OBS closed before response.'));});
     socket.addEventListener('message',event=>{
       let message;try{message=JSON.parse(String(event.data));}
       catch{return finish(new Error('Malformed OBS response.'));}
       const {op,d}=message;
       if(op===0){
         const data={rpcVersion:1};
         if(d?.authentication){
           if(!this.password)return finish(new Error('OBS authentication password required.'));
           data.authentication=obsWebsocketAuth(this.password,d.authentication.salt,d.authentication.challenge);
         }
         socket.send(JSON.stringify({op:1,d:data}));
       }else if(op===2){
         if(d?.negotiatedRpcVersion!==1)
           return finish(new Error('OBS unsupported negotiated RPC version.'));
         identified=true;
         phase='writing';
         expectedRequestId='present-'+randomUUID();
         socket.send(JSON.stringify({op:6,d:{
           requestType:'SetCurrentProgramScene',requestId:expectedRequestId,
           requestData:{sceneName:slide.scene.trim()}
         }}));
       }else if(op===7&&identified){
         const expectedType=phase==='writing'?'SetCurrentProgramScene':'GetCurrentProgramScene';
         if(d?.requestId!==expectedRequestId||d?.requestType!==expectedType)return;
         const status=d?.requestStatus;
         if(status?.result!==true)return finish(new Error('OBS '+(phase==='writing'?'refused scene change':'scene readback failed')+': '+String(status?.comment??status?.code??'unknown')));
         if(phase==='writing'){
           // An OBS success response confirms that a command was accepted.
           // Query the actual program scene before treating it as displayed.
           phase='reading';
           expectedRequestId='verify-'+randomUUID();
           socket.send(JSON.stringify({op:6,d:{
             requestType:'GetCurrentProgramScene',requestId:expectedRequestId
           }}));
           return;
         }
         const observed=d?.responseData?.sceneName??d?.responseData?.currentProgramSceneName;
         if(observed!==slide.scene.trim())
           return finish(new Error('OBS scene readback mismatch. Expected configured scene.'));
         finish(null,{ok:true,scene:slide.scene.trim(),confirmed:true});
       }
     });
   });
 }
}
const builtInAdapterNames=new Set(['memory','web-deck','propresenter','keynote','powerpoint-macos','powerpoint-windows','obs']);
const customAdapters=new Map();
/** Optional AI host/RDC adapter registration. This never replaces native adapters. */
export function registerPresentationAdapter(name,factory){
 if(typeof name!=='string'||! /^[a-z][a-z0-9-]{2,63}$/.test(name))
   throw new Error('Invalid adapter name. Use lowercase letters, digits and hyphens.');
 if(builtInAdapterNames.has(name))throw new Error('Built-in adapter name is reserved.');
 if(typeof factory!=='function')throw new Error('Custom adapter must provide a factory.');
 if(customAdapters.has(name))throw new Error('Adapter already registered: '+name);
 customAdapters.set(name,factory);
 return ()=>{if(customAdapters.get(name)===factory)customAdapters.delete(name);};
}
export function makeAdapter(kind='memory',opts={}){
 switch(kind){
 case 'memory':case 'web-deck':return new MemoryAdapter();
 case 'propresenter':return new ProPresenterAdapter(opts);
 case 'keynote':return new KeynoteAdapter(opts);
 case 'powerpoint-macos':return new PowerPointMacAdapter(opts);
 case 'powerpoint-windows':return new PowerPointWindowsAdapter(opts);
 case 'obs':return new OBSAdapter(opts);
 default:{
   const factory=customAdapters.get(kind);
   if(!factory)throw new Error('Unknown presentation adapter: '+kind);
   const adapter=factory(opts);
   if(!adapter||typeof adapter.show!=='function'||typeof adapter.external!=='boolean')
     throw new Error('Invalid registered presentation adapter contract.');
   return adapter;
 }
 }
}


/** Read-only discovery of adapters registered by the current authorized AI host. */
export function listPresentationAdapters(){
 return [...customAdapters.keys()].sort();
}
