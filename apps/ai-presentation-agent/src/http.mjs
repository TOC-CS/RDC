import http from 'node:http';
import {timingSafeEqual} from 'node:crypto';
import {createDeckVersionHasher} from './deck-version.mjs';
import {renderDeckHtml} from './deck.mjs';
import {renderStageConfidenceHtml} from './worship-stage-view.mjs';
import {renderBroadcastOverlayHtml} from './worship-stream-view.mjs';
const HEADERS={
 'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store',
 'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
 'X-Frame-Options':'DENY','Cross-Origin-Resource-Policy':'same-origin'
};
const lookChangeRoutes=Object.freeze({
 '/v1/worship/looks/audience':'audience',
 '/v1/worship/looks/stage':'stage',
 '/v1/worship/looks/broadcast':'broadcast'
});
const visibilityRoutes=Object.freeze({
 '/v1/worship/visibility/audience':'audience',
 '/v1/worship/visibility/stage':'stage',
 '/v1/worship/visibility/broadcast':'broadcast'
});
const routes=Object.freeze({
 '/v1/load':'presentation_load','/v1/worship/load':'presentation_load_worship',
 '/v1/worship/library/load':'presentation_load_worship_library',
 '/v1/communications/prepare':'presentation_communication_prepare',
 '/v1/create':'presentation_create',
 '/v1/worship/macro/preview':'presentation_worship_macro_preview',
 '/v1/unload':'presentation_unload',
 '/v1/start':'presentation_start','/v1/stop':'presentation_stop','/v1/command':'presentation_command',
 '/v1/cue':'presentation_cue','/v1/watch':'presentation_watch',
 '/v1/voice':'presentation_voice','/v1/output':'presentation_select_output',
 '/v1/arm':'presentation_arm','/v1/export/html':'presentation_export_html',
 '/v1/export/json':'presentation_export_json',
 '/v1/export/pptx':'presentation_export_pptx'
});
function reply(res,status,value){
 const body=JSON.stringify(value);
 res.writeHead(status,{...HEADERS,'Content-Length':Buffer.byteLength(body)});
 res.end(body);
}
function readJson(req){
 return new Promise((resolve,reject)=>{
   const pieces=[];let size=0,ended=false;
   req.on('data',b=>{
      size+=b.length;
      if(size>1_048_576){
        if(!ended){ended=true;reject(Object.assign(new Error('Request too large.'),{status:413}));}
        req.destroy();
      }else pieces.push(b);
   });
   req.on('end',()=>{
     if(ended)return;
     try{
       const input=pieces.length?JSON.parse(Buffer.concat(pieces).toString('utf8')):{};
       if(!input||typeof input!=='object'||Array.isArray(input))throw new Error('JSON object required.');
       resolve(input);
     }catch(e){reject(Object.assign(new Error('Invalid JSON request: '+e.message),{status:400}));}
   });
   req.once('error',reject);
 });
}
export function createHttpServer({handler,token,viewerToken=null,stageToken=null,streamToken=null}={}){
 if(typeof handler!=='function')throw new TypeError('MCP handler required.');
 if(typeof token!=='string'||Buffer.byteLength(token)<16||Buffer.byteLength(token)>512)
   throw new Error('Start local HTTP gateway with a strong bearer token of at least 16 bytes.');
 if(viewerToken!==null&&(typeof viewerToken!=='string'||
    Buffer.byteLength(viewerToken)<16||Buffer.byteLength(viewerToken)>512))
   throw new Error('Viewer token must be 16 to 512 bytes when enabled.');
 if(stageToken!==null&&(typeof stageToken!=='string'||
    Buffer.byteLength(stageToken)<16||Buffer.byteLength(stageToken)>512||
    stageToken===token||stageToken===viewerToken))
   throw new Error('Stage monitor requires an independent private token.');
 if(streamToken!==null&&(typeof streamToken!=='string'||
    Buffer.byteLength(streamToken)<16||Buffer.byteLength(streamToken)>512||
    [token,viewerToken,stageToken].includes(streamToken)))
   throw new Error('Broadcast overlay requires a distinct read-only token.');
 const secret=Buffer.from(token);
 const viewerSecret=viewerToken===null?null:Buffer.from(viewerToken);
 const stageSecret=stageToken===null?null:Buffer.from(stageToken);
 const streamSecret=streamToken===null?null:Buffer.from(streamToken);
 const equal=(attempted,expected)=>attempted.length===expected.length&&timingSafeEqual(attempted,expected);
 const deckVersion=createDeckVersionHasher();
 const getStatus=async()=>{
   const answer=await handler({jsonrpc:'2.0',id:++nextId,method:'tools/call',
      params:{name:'presentation_status',arguments:{}}});
   return answer?.result?.structuredContent??null;
 };
 let nextId=0;
 return http.createServer(async(req,res)=>{
   try{
     const origin=req.headers.origin;
     if(origin){
       const parsed=new URL(origin);
       if(parsed.protocol!=='http:'||!['127.0.0.1','localhost','[::1]'].includes(parsed.hostname))
         return reply(res,403,{error:'Origin forbidden.'});
     }
     const parsedPath=new URL(req.url,'http://localhost');
     const path=parsedPath.pathname;
     if(req.method==='GET'&&
       ['/v1/look/audience','/v1/look/stage','/v1/look/broadcast'].includes(path)){
       const destination=path.slice('/v1/look/'.length);
       const expected=destination==='audience'?viewerSecret:
         destination==='stage'?stageSecret:streamSecret;
       if(!expected||typeof handler.getWorshipLook!=='function')
         return reply(res,404,{error:'Worship Look destination not configured.'});
       const key=Buffer.from(parsedPath.searchParams.get('key')??'');
       if(!equal(key,expected))
         return reply(res,401,{error:'Output-specific authorization required.'});
       if(parsedPath.searchParams.size!==1||!parsedPath.searchParams.has('key'))
         return reply(res,400,{error:'Only the output-specific key is supported.'});
       const packet=handler.getWorshipLook(destination,
         destination==='stage'?stageToken:null);
       if(!packet)return reply(res,409,{error:'Load a worship service first.'});
       return reply(res,200,packet);
     }
     if(req.method==='GET'&&(path==='/v1/stream-overlay'||path==='/v1/stream-events')){
       if(!streamSecret||typeof handler.getBroadcastCue!=='function')
         return reply(res,404,{error:'Public stream overlay is disabled.'});
       const key=Buffer.from(parsedPath.searchParams.get('key')??'');
       if(!equal(key,streamSecret))return reply(res,401,{error:'Stream overlay authorization required.'});
       if(path==='/v1/stream-overlay'){
         const html=renderBroadcastOverlayHtml({
           eventsPath:'/v1/stream-events?key='+encodeURIComponent(streamToken)
         });
         return res.writeHead(200,{
           'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store',
           'Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff',
           'X-Frame-Options':'DENY',
           'Content-Security-Policy':"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; object-src 'none'"
         }).end(html);
       }
       res.writeHead(200,{
         'Content-Type':'text/event-stream; charset=utf-8',
         'Cache-Control':'no-store, no-transform','Connection':'keep-alive',
         'Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff',
         'X-Accel-Buffering':'no'
       });
       let prior='',closed=false;
       const present=()=>{
         if(closed||res.destroyed)return;
         try{
           const state=handler.getBroadcastCue();
           const payload=JSON.stringify(state?{...state,loaded:true}:{
             loaded:false,current:null
           });
           if(payload!==prior){prior=payload;res.write('data: '+payload+'\n\n');}
         }catch{
           if(!res.destroyed)res.write(': stream cue unavailable\n\n');
         }
       };
       const unsubscribe=typeof handler.subscribe==='function'?
         handler.subscribe(present):null;
       const fallback=unsubscribe?null:setInterval(present,180);
       const heartbeat=setInterval(()=>{
         if(!closed&&!res.destroyed)res.write(': heartbeat\n\n');
       },15000);
       heartbeat.unref?.();
       const cleanup=()=>{
         if(closed)return;closed=true;
         if(fallback)clearInterval(fallback);
         clearInterval(heartbeat);unsubscribe?.();
       };
       res.once('close',cleanup);req.once('aborted',cleanup);
       present();return;
     }
     if(req.method==='GET'&&path==='/v1/stage/teleprompt'){
       if(!stageSecret||typeof handler.getPrivateTeleprompt!=='function')
         return reply(res,404,{error:'Private stage teleprompter is unavailable.'});
       const supplied=Buffer.from(parsedPath.searchParams.get('key')??'');
       if(!equal(supplied,stageSecret))
         return reply(res,401,{error:'Separate private stage authorization required.'});
       if(parsedPath.searchParams.size!==1||!parsedPath.searchParams.has('key'))
         return reply(res,400,{error:'Unexpected private teleprompter query.'});
       const data=handler.getPrivateTeleprompt(stageToken);
       if(!data)return reply(res,409,{error:'Load a worship service first.'});
       return reply(res,200,data);
     }
     if(req.method==='GET'&&path==='/v1/stage/clock'){
       if(!stageSecret||typeof handler.getPrivateStageClock!=='function')
         return reply(res,404,{error:'Private stage clock is unavailable.'});
       const supplied=Buffer.from(parsedPath.searchParams.get('key')??'');
       if(!equal(supplied,stageSecret))
         return reply(res,401,{error:'Private stage authorization required.'});
       if(parsedPath.searchParams.size!==1)
         return reply(res,400,{error:'Unexpected stage clock query fields.'});
       const state=handler.getPrivateStageClock(stageToken);
       if(!state)return reply(res,409,{error:'Load a worship service first.'});
       return reply(res,200,state);
     }
     if(req.method==='GET'&&(path==='/v1/stage'||path==='/v1/stage-events')){
       if(!stageSecret||typeof handler.getPrivateStageCue!=='function')
         return reply(res,404,{error:'Private stage monitor is not configured.'});
       const key=Buffer.from(parsedPath.searchParams.get('key')??'');
       if(!equal(key,stageSecret))return reply(res,401,{error:'Private stage authorization required.'});
       if(path==='/v1/stage'){
         const html=renderStageConfidenceHtml({
           eventsPath:'/v1/stage-events?key='+encodeURIComponent(stageToken)
         });
         return res.writeHead(200,{
           'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store',
           'Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff',
           'X-Frame-Options':'DENY',
           'Content-Security-Policy':"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; object-src 'none'"
         }).end(html);
       }
       res.writeHead(200,{
         'Content-Type':'text/event-stream; charset=utf-8',
         'Cache-Control':'no-store, no-transform','Connection':'keep-alive',
         'Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff',
         'X-Accel-Buffering':'no'
       });
       let previous='',closed=false;
       const present=()=>{
         if(closed||res.destroyed)return;
         try{
           const state=handler.getPrivateStageCue(stageToken);
           const payload=JSON.stringify(state?{...state,loaded:true}:{
             loaded:false,current:null,next:null
           });
           if(payload!==previous){previous=payload;res.write('data: '+payload+'\n\n');}
         }catch{
           if(!res.destroyed)res.write(': private stage status unavailable\n\n');
         }
       };
       const unsubscribe=typeof handler.subscribe==='function'?
         handler.subscribe(present):null;
       const fallback=unsubscribe?null:setInterval(present,180);
       const timerRefresh=setInterval(()=>{
         if(!closed&&handler.getPrivateStageClock?.(stageToken)?.running)present();
       },1000);
       timerRefresh.unref?.();
       const heartbeat=setInterval(()=>{
         if(!closed&&!res.destroyed)res.write(': heartbeat\n\n');
       },15000);
       heartbeat.unref?.();
       const cleanup=()=>{
         if(closed)return;closed=true;
         if(fallback)clearInterval(fallback);
         clearInterval(timerRefresh);
         clearInterval(heartbeat);unsubscribe?.();
       };
       res.once('close',cleanup);req.once('aborted',cleanup);
       present();return;
     }
     if(req.method==='GET'&&(path==='/v1/viewer'||path==='/v1/view-events')){
       if(!viewerSecret)return reply(res,404,{error:'Local viewer is disabled.'});
       const key=Buffer.from(parsedPath.searchParams.get('key')??'');
       if(!equal(key,viewerSecret))return reply(res,401,{error:'Viewer authorization required.'});
       const state=await getStatus();
       if(!state?.slides?.length)return reply(res,409,{error:'Load a presentation before opening the viewer.'});
       const version=deckVersion(state);
       if(path==='/v1/viewer'){
         const html=renderDeckHtml({title:state.title,slides:state.slides,theme:state.theme},
           {liveEventsPath:'/v1/view-events?key='+encodeURIComponent(viewerToken),deckVersion:version});
         return res.writeHead(200,{
           'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store',
           'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
           'Content-Security-Policy':"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; object-src 'none'",
           'X-Frame-Options':'DENY'
         }).end(html);
       }
       res.writeHead(200,{
         'Content-Type':'text/event-stream; charset=utf-8','Cache-Control':'no-store, no-transform',
         'Connection':'keep-alive','X-Content-Type-Options':'nosniff','X-Accel-Buffering':'no'
       });
       let prior='',closed=false;
       const present=snapshot=>{
         if(closed||res.destroyed)return;
         const data=JSON.stringify({
           index:snapshot?.index??null,slideId:snapshot?.current?.id??null,
           loaded:Array.isArray(snapshot?.slides)&&snapshot.slides.length>0,
           started:snapshot?.started===true,held:snapshot?.held===true,
           armed:snapshot?.armed===true,dryRun:snapshot?.dryRun===true,
           outputFaulted:snapshot?.outputFaulted===true,
           recoveryPreview:snapshot?.recoveryPreview===true,
           look:typeof handler.getAudienceLook==='function'?handler.getAudienceLook():null,
           source:snapshot?.adapter??null,
           deckVersion:deckVersion(snapshot??{title:'',slides:[]})
         });
         if(data!==prior){prior=data;res.write('data: '+data+'\n\n');}
       };
       const emit=async()=>{
         if(closed||res.destroyed)return;
         try{present(await getStatus());}
         catch{if(!closed&&!res.destroyed)res.write(': status unavailable\n\n');}
       };
       // New agents notify the viewer directly from the serialized director.
       // Older handlers still work with bounded polling as a compatibility
       // fallback; neither path sends viewer control or API tokens in events.
       const unsubscribe=typeof handler.subscribe==='function'?
         handler.subscribe(present):null;
       const pollTimer=unsubscribe?null:setInterval(()=>{void emit();},120);
       const heartbeat=setInterval(()=>{
         if(!closed&&!res.destroyed)res.write(': heartbeat\n\n');
       },15000);
       heartbeat.unref?.();
       const cleanup=()=>{
         if(closed)return;
         closed=true;
         if(pollTimer)clearInterval(pollTimer);
         clearInterval(heartbeat);
         if(unsubscribe)unsubscribe();
       };
       res.once('close',cleanup);
       req.once('aborted',cleanup);
       await emit();
       return;
     }
     const header=req.headers.authorization??'';
     const attempted=typeof header==='string'&&header.startsWith('Bearer ')?Buffer.from(header.slice(7)):Buffer.alloc(0);
     if(!equal(attempted,secret))
       return reply(res,401,{error:'Authentication required.'});
     if(req.method==='POST'&&path==='/v1/stage/teleprompt'){
       if(!stageSecret||typeof handler.updatePrivateTeleprompt!=='function')
         return reply(res,404,{error:'Private stage teleprompter is unavailable.'});
       const supplied=typeof req.headers['x-stage-credential']==='string'?
         Buffer.from(req.headers['x-stage-credential']):Buffer.alloc(0);
       if(!equal(supplied,stageSecret))
         return reply(res,401,{error:'Separate private stage authorization required.'});
       if(!String(req.headers['content-type']??'').startsWith('application/json'))
         return reply(res,415,{error:'JSON content type required.'});
       const input=await readJson(req);
       try{return reply(res,200,handler.updatePrivateTeleprompt(stageToken,input));}
       catch(error){return reply(res,422,{error:String(error.message??error)});}
     }
     if(req.method==='POST'&&path==='/v1/stage/clock'){
       if(!stageSecret||typeof handler.updatePrivateStageClock!=='function')
         return reply(res,404,{error:'Private stage clock is unavailable.'});
       const supplied=typeof req.headers['x-stage-credential']==='string'?
         Buffer.from(req.headers['x-stage-credential']):Buffer.alloc(0);
       if(!equal(supplied,stageSecret))
         return reply(res,401,{error:'Separate private stage authorization required.'});
       if(!String(req.headers['content-type']??'').startsWith('application/json'))
         return reply(res,415,{error:'JSON content type required.'});
       const input=await readJson(req);
       try{return reply(res,200,handler.updatePrivateStageClock(stageToken,input));}
       catch(error){return reply(res,422,{error:String(error.message??error)});}
     }
     let tool,args={};
     if(req.method==='GET'){
       if(path==='/v1/status')tool='presentation_status';
       else if(path==='/v1/worship/rundown')tool='presentation_worship_rundown';
       else if(path==='/v1/readback')tool='presentation_readback';
       else if(path==='/v1/capabilities')tool='presentation_capabilities';
       else if(path==='/v1/communications/capabilities')tool='presentation_communication_capabilities';
       else if(path==='/v1/readiness')tool='presentation_readiness';
       else return reply(res,404,{error:'Unknown endpoint.'});
     }else if(req.method==='POST'&&Object.hasOwn(visibilityRoutes,path)){
       tool='presentation_worship_visibility_set';
       if(!String(req.headers['content-type']??'').startsWith('application/json'))
         return reply(res,415,{error:'JSON content type required.'});
       const body=await readJson(req);
       if(Object.keys(body).some(key=>key!=='mode')||!Object.hasOwn(body,'mode'))
         return reply(res,400,{error:'Visibility change requires only a mode.'});
       args={destination:visibilityRoutes[path],mode:body.mode};
     }else if(req.method==='POST'&&Object.hasOwn(lookChangeRoutes,path)){
       tool='presentation_worship_look_set';
       if(!String(req.headers['content-type']??'').startsWith('application/json'))
         return reply(res,415,{error:'JSON content type required.'});
       const body=await readJson(req);
       if(Object.keys(body).some(key=>key!=='look')||!Object.hasOwn(body,'look'))
         return reply(res,400,{error:'Look edit requires only a validated look object.'});
       args={destination:lookChangeRoutes[path],look:body.look};
     }else if(req.method==='POST'&&Object.hasOwn(routes,path)){
       tool=routes[path];
       if(!String(req.headers['content-type']??'').startsWith('application/json'))
         return reply(res,415,{error:'JSON content type required.'});
       args=await readJson(req);
     }else return reply(res,404,{error:'Unknown endpoint.'});
     const response=await handler({jsonrpc:'2.0',id:++nextId,method:'tools/call',
       params:{name:tool,arguments:args}});
     if(response?.result?.isError)
       return reply(res,422,{error:response.result.content?.[0]?.text??'Tool rejected request.'});
     if(response?.error)return reply(res,500,{error:response.error.message});
     return reply(res,200,response.result.structuredContent);
   }catch(error){if(!res.headersSent)reply(res,error.status??400,{error:String(error.message??error)});}
 });
}
