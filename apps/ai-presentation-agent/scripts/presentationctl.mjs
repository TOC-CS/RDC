#!/usr/bin/env node
// A local RDC-safe CLI that never includes the private API bearer in argv,
// stdout, client logs or any AI tool arguments. Use across multiple RDC jobs.
import {readFile,stat,lstat,writeFile,open} from 'node:fs/promises';
import {constants as fsConstants} from 'node:fs';
import {isAbsolute} from 'node:path';
import {readPrivateState} from '../src/managed-state.mjs';
import {BandMatesLiveLink} from '../integrations/bandmates-live.mjs';
import {presentationPreflight} from '../src/preflight.mjs';
import {OBSReadOnlyMonitor} from '../src/obs-monitor.mjs';
import {venueOutputReadiness} from '../src/venue-output-readiness.mjs';

const usage='AI Presentation Agent local controller\n'+
 'Usage: node scripts/presentationctl.mjs COMMAND [ARGUMENTS]\n'+
 'Commands: status, capabilities, readback, rundown, bandmates-status, preflight, venue-readiness, obs-status, obs-production-status, load --file FILE, worship-load --file FILE, worship-library-load --file OWNER_PRIVATE_BUNDLE, create --file FILE,\n'+
 ' start [manual|assisted|automatic], stop, unload, next, previous, hold, resume,\n'+
 ' goto SLIDE_NUMBER, cue --file FILE, voice --file FILE, watch --file FILE,\n'+
 ' output --file FILE, macro-preview --file FILE, look-set --file FILE, visibility-set --file FILE,\n'+
 ' viewer-check, viewer-export --file ABSOLUTE_HTML_PATH,\n'+
 ' stage-check, stage-export --file ABSOLUTE_HTML_PATH (separate private confidence view),\n'+
 ' stage-clock --file ABSOLUTE_OWNER_ONLY_JSON, stage-clock-status, stage-clock-start, stage-clock-pause, stage-clock-resume, stage-clock-reset,\n'+
 ' teleprompt --file PRIVATE_JSON, teleprompt-status, teleprompt-next, teleprompt-previous, teleprompt-hold, teleprompt-resume,\n'+
 ' stream-check, stream-export --file ABSOLUTE_HTML_PATH (public-safe transparent browser overlay).\n'+
 ' Existing server session is preserved across calls. Viewer files are private.\n'+
 ' For retry-safe slide commands, append --request-id STABLE_ID.\n';
let args=process.argv.slice(2);
if(args.length===0||args.includes('--help')||args.includes('-h')){
 process.stdout.write(usage);process.exit(0);
}
let requestId=null;
const requestOption=args.indexOf('--request-id');
if(requestOption>=0){
 const allowed=new Set(['next','previous','hold','resume','goto']);
 if(!allowed.has(args[0])||requestOption!==args.length-2)
   throw new Error('Stable request IDs are only supported on presentation control commands.');
 requestId=args[requestOption+1];
 if(typeof requestId!=='string'||!/^[A-Za-z0-9._:-]{1,128}$/.test(requestId))
   throw new Error('Invalid presentation command request ID.');
 args=args.slice(0,requestOption);
}
const command=args[0];
const noArg=new Set(['status','capabilities','readback','rundown','stop','unload','next','previous','hold','resume','viewer-check','stage-check','stream-check']);
const fromFile=new Set(['load','worship-load','worship-library-load','create','cue','voice','watch','output','macro-preview','look-set','visibility-set']);
const paths={
 status:'/v1/status',capabilities:'/v1/capabilities',readback:'/v1/readback',
 rundown:'/v1/worship/rundown',
 load:'/v1/load','worship-load':'/v1/worship/load',
 'worship-library-load':'/v1/worship/library/load',create:'/v1/create',cue:'/v1/cue',voice:'/v1/voice',
 watch:'/v1/watch',output:'/v1/output',
 'macro-preview':'/v1/worship/macro/preview',
 'look-set':'/v1/worship/looks/audience',
 'visibility-set':'/v1/worship/visibility/audience',
 start:'/v1/start',stop:'/v1/stop',unload:'/v1/unload',next:'/v1/command',previous:'/v1/command',
 hold:'/v1/command',resume:'/v1/command',goto:'/v1/command'
};
async function readOwnerPrivateWorshipBundle(path){
 // Open the same validated file descriptor with no-follow semantics where
 // supported. A symlink swap between lstat and read must not redirect input.
 const before=await lstat(path);
 const safe=info=>info.isFile()&&!info.isSymbolicLink()&&
   info.size>1&&info.size<=1_048_576&&(info.mode&0o077)===0&&
   (typeof process.getuid!=='function'||info.uid===process.getuid());
 if(!safe(before))
   throw new Error('Worship catalog bundle must be an owner-private regular file (0600), not a symlink.');
 let handle;
 try{handle=await open(path,fsConstants.O_RDONLY|(fsConstants.O_NOFOLLOW??0));}
 catch{throw new Error('Owner-private worship catalog bundle could not be opened safely.');}
 try{
   const current=await handle.stat();
   if(!safe(current)||before.ino!==current.ino||before.dev!==current.dev)
     throw new Error('Owner-private worship catalog bundle changed during validation.');
   let body;
   try{body=JSON.parse(await handle.readFile('utf8'));}
   catch{throw new Error('Invalid owner-private worship catalog JSON.');}
   if(!body||typeof body!=='object'||Array.isArray(body)||
     !Object.hasOwn(body,'catalog')||!Object.hasOwn(body,'plan')||
     Object.keys(body).some(key=>!['catalog','plan'].includes(key)))
     throw new Error('Worship catalog bundle must contain exactly catalog and plan.');
   return body;
 }finally{await handle.close();}
}
async function readOwnerPrivateTelepromptAction(path){
 if(typeof path!=='string'||!isAbsolute(path))
   throw new Error('Private teleprompter requires an absolute owner-only JSON file.');
 const before=await lstat(path);
 const safe=info=>info.isFile()&&!info.isSymbolicLink()&&
   info.size>1&&info.size<=8192&&(info.mode&0o077)===0&&
   (typeof process.getuid!=='function'||info.uid===process.getuid());
 if(!safe(before))
   throw new Error('Private teleprompter file must be owner-only (0600), regular and not a symlink.');
 let handle;
 try{handle=await open(path,fsConstants.O_RDONLY|(fsConstants.O_NOFOLLOW??0));}
 catch{throw new Error('Private teleprompter file cannot be opened safely.');}
 try{
   const actual=await handle.stat();
   if(!safe(actual)||before.ino!==actual.ino||before.dev!==actual.dev)
     throw new Error('Owner-private teleprompter input changed during validation.');
   let body;
   try{body=JSON.parse(await handle.readFile('utf8'));}
   catch{throw new Error('Private teleprompter JSON is invalid.');}
   if(!body||typeof body!=='object'||Array.isArray(body)||
      !['configure','follow'].includes(body.action))
     throw new Error('Private teleprompter file requires a configure or follow action.');
   const allowed=body.action==='configure'?
     ['action','role','fontScale','scrollSpeed','mirrored']:
     ['action','text','confidence','final','eventId','timestamp'];
   if(Object.keys(body).some(key=>!allowed.includes(key)))
     throw new Error('Unexpected private teleprompter input.');
   return body;
 }finally{await handle.close();}
}
async function run(){
 if(command==='venue-readiness'){
   if(args.length!==1)throw new Error('Read-only venue inventory takes no arguments.');
   const result=await venueOutputReadiness();
   process.stdout.write(JSON.stringify(result)+'\n');
   return;
 }
 if(command==='obs-status'||command==='obs-production-status'){
   if(args.length!==1)throw new Error('OBS status takes no arguments.');
   const result=await new OBSReadOnlyMonitor({
     url:process.env.OBS_WS_URL??'ws://127.0.0.1:4455/',
     password:process.env.OBS_WEBSOCKET_PASSWORD??'',
     includeProductionMetrics:command==='obs-production-status'
   }).inspect();
   process.stdout.write(JSON.stringify(result)+'\n');
   return;
 }
 if(command==='preflight'){
   if(args.length!==1)throw new Error('Read-only preflight accepts no arguments.');
   const result=await presentationPreflight({
     inspectBandMates:()=>new BandMatesLiveLink({
       baseUrl:process.env.BANDMATES_LOCAL_STATUS_URL??'http://127.0.0.1:8746'
     }).inspect()
   });
   process.stdout.write(JSON.stringify(result)+'\n');
   return;
 }
 if(command==='bandmates-status'){
   if(args.length!==1)throw new Error('BandMates status accepts no arguments.');
   const result=await new BandMatesLiveLink({
     baseUrl:process.env.BANDMATES_LOCAL_STATUS_URL??'http://127.0.0.1:8746'
   }).inspect();
   process.stdout.write(JSON.stringify(result)+'\n');
   return;
 }
 if(['teleprompt','teleprompt-status','teleprompt-next','teleprompt-previous',
     'teleprompt-hold','teleprompt-resume'].includes(command)){
   let action=null,payload=null;
   if(command==='teleprompt'){
     if(args.length!==3||args[1]!=='--file')
       throw new Error('Private teleprompter requires an absolute owner-only JSON file.');
     payload=await readOwnerPrivateTelepromptAction(args[2]);
     action=payload.action;
   }else{
     if(args.length!==1)throw new Error('Private teleprompter action accepts no extra arguments.');
     if(command!=='teleprompt-status'){
       action=command.slice('teleprompt-'.length);
       payload={action};
     }
   }
   const state=await readPrivateState();
   if(typeof state.stageToken!=='string'||!state.stageToken)
     throw new Error('Current managed session has no private stage token.');
   let response;
   try{
     response=await fetch('http://127.0.0.1:'+state.port+
       '/v1/stage/teleprompt'+(payload?'':'?key='+encodeURIComponent(state.stageToken)),{
       method:payload?'POST':'GET',redirect:'error',
       headers:{...(payload?{
         Authorization:'Bearer '+state.token,'Content-Type':'application/json',
         'X-Stage-Credential':state.stageToken
       }:{})},
       ...(payload?{body:JSON.stringify(payload)}:{}),
       signal:AbortSignal.timeout(3000)
     });
   }catch{throw new Error('Private teleprompter service is unavailable; do not replay an uncertain cue.');}
   const data=await response.json().catch(()=>null);
   if(!response.ok)
     throw new Error('Private teleprompter request rejected: '+
       String(data?.error??'authorization or stage source unavailable').slice(0,160));
   if(data?.schema!=='toc.worship.stage-teleprompt/v1')
     throw new Error('Invalid private teleprompter receipt.');
   // No sermon script, lyrics, transcript, stage token or bearer in RDC output.
   process.stdout.write(JSON.stringify({
     schema:'toc.worship.stage-teleprompt-cli/v1',
     privateStage:true,updated:!!payload,
     ...(action?{action}:{}),
     role:data.role,loaded:data.loaded,position:data.position,
     lineCount:data.lineCount,progress:data.progress,
     held:data.held,mirrored:data.mirrored,
     fontScale:data.fontScale,scrollSpeed:data.scrollSpeed,
     automaticSlideAdvance:false,
     ...(data.follow?{followChanged:data.follow.changed,followReason:data.follow.reason}:{})
   })+'\n');
   return;
 }
 if(['stage-clock','stage-clock-status','stage-clock-start','stage-clock-pause','stage-clock-resume','stage-clock-reset'].includes(command)){
   let payload=null,action=null;
   if(command==='stage-clock'){
     if(args.length!==3||args[1]!=='--file'||!isAbsolute(args[2]))
       throw new Error('Private stage clock requires an absolute owner-only JSON file.');
     const details=await lstat(args[2]);
     if(!details.isFile()||details.isSymbolicLink()||details.size>8192||
       (details.mode&0o077)!==0||
       (typeof process.getuid==='function'&&details.uid!==process.getuid()))
       throw new Error('Private stage timer file must be owner-only, regular and not a symlink.');
     const body=JSON.parse(await readFile(args[2],'utf8'));
     if(!body||typeof body!=='object'||Array.isArray(body)||
       Object.keys(body).some(key=>!['action','label','durationMs'].includes(key))||
       body.action!=='configure')
       throw new Error('Invalid private stage timer configuration.');
     action='configure';payload=body;
   }else{
     if(args.length!==1)throw new Error('Private stage clock action accepts no arguments.');
     if(command!=='stage-clock-status'){
       action=command.slice('stage-clock-'.length);
       payload={action};
     }
   }
   const state=await readPrivateState();
   if(typeof state.stageToken!=='string'||!state.stageToken)
     throw new Error('Private stage display is not configured on the active presentation session.');
   const path='/v1/stage/clock'+(payload?'':'?key='+encodeURIComponent(state.stageToken));
   let response;
   try{
     response=await fetch('http://127.0.0.1:'+state.port+path,{
       method:payload?'POST':'GET',redirect:'error',
       headers:{...(payload?{
         Authorization:'Bearer '+state.token,'Content-Type':'application/json',
         'X-Stage-Credential':state.stageToken
       }:{})},
       ...(payload?{body:JSON.stringify(payload)}:{}),
       signal:AbortSignal.timeout(3000)
     });
   }catch{throw new Error('Private stage clock service is unavailable.');}
   const result=await response.json().catch(()=>null);
   if(!response.ok)throw new Error('Private stage clock rejected request: '+
     String(result?.error??'authorization or stage service unavailable').slice(0,150));
   if(result?.schema!=='toc.worship-stage-clock/v1')
     throw new Error('Private stage clock receipt invalid.');
   // A stage-only caption must never appear in general AI/RDC tool output.
   process.stdout.write(JSON.stringify({
     privateStage:true,updated:!!payload,
     ...(action?{action}:{}),
     durationMs:result.durationMs,remainingMs:result.remainingMs,
     overrunMs:result.overrunMs,running:result.running,paused:result.paused,
     automaticAdvance:false
   })+'\n');
   return;
 }
 if(['viewer-check','viewer-export','stage-check','stage-export','stream-check','stream-export'].includes(command)){
   const privateStage=command.startsWith('stage-');
   const publicStream=command.startsWith('stream-');
   const state=await readPrivateState();
   if(privateStage&&!state.stageToken)
     throw new Error('Current managed server does not have a private stage session; update only during an owner-approved restart.');
   if(publicStream&&!state.streamToken)
     throw new Error('Current managed server does not have a stream overlay session; update only during an owner-approved restart.');
   const viewerUrl='http://127.0.0.1:'+state.port+
     (privateStage?'/v1/stage?key='+encodeURIComponent(state.stageToken):
       publicStream?'/v1/stream-overlay?key='+encodeURIComponent(state.streamToken):
       '/v1/viewer?key='+encodeURIComponent(state.viewerToken));
   let res;
   try{res=await fetch(viewerUrl,{method:'GET',signal:AbortSignal.timeout(2000)});}
   catch{throw new Error('Local presentation viewer is unavailable.');}
   if(res.status!==200||!String(res.headers.get('content-type')).includes('text/html'))
     throw new Error('Local presentation viewer has no loaded deck or is not ready.');
   await res.arrayBuffer();
   if(command==='viewer-check'||command==='stage-check'||command==='stream-check'){
     if(args.length!==1)throw new Error('Viewer-check takes no arguments.');
     process.stdout.write(JSON.stringify({available:true,live:true,
       ...(privateStage?{privateStage:true}:{}),
       ...(publicStream?{publicStream:true}:{})})+'\n');
     return;
   }
   if(args.length!==3||args[1]!=='--file'||!isAbsolute(args[2])||!args[2].endsWith('.html'))
     throw new Error('Viewer export requires one absolute .html path after --file.');
   // Only the owner-selected local HTML file stores the viewer credential.
   // Never print the bearer or a viewer URL into AI chat/tool output.
   const html='<!doctype html><html><head><meta charset="utf-8">'+
     '<meta name="referrer" content="no-referrer">'+
     '<meta http-equiv="refresh" content="0; url='+viewerUrl+'">'+
     '<title>Private Presentation Viewer</title></head>'+
     '<body><p>Opening the private local presentation viewer.</p></body></html>';
   await writeFile(args[2],html,{encoding:'utf8',mode:0o600,flag:'wx'});
   process.stdout.write(JSON.stringify({created:true,file:args[2],private:true,
     ...(privateStage?{privateStage:true}:{}),
     ...(publicStream?{publicStream:true}:{})})+'\n');
   return;
 }
 if(!Object.hasOwn(paths,command))throw new Error('Unknown presentation controller command.');
 let payload=null,endpoint=paths[command];
 if(noArg.has(command)){
   if(args.length!==1)throw new Error('This command accepts no extra arguments.');
   if(command==='stop'||command==='unload')payload={};
   else if(!['status','capabilities','readback','rundown'].includes(command))payload={action:command};
 }else if(fromFile.has(command)){
   if(args.length!==3||args[1]!=='--file'||!args[2].startsWith('/'))
     throw new Error('Provide one absolute JSON file path after --file.');
   let body;
   if(command==='worship-library-load'){
     body=await readOwnerPrivateWorshipBundle(args[2]);
   }else{
     const st=await stat(args[2]);
     if(!st.isFile()||st.size>1_048_576)
       throw new Error('Presentation JSON file must be regular and at most 1 MiB.');
     body=JSON.parse(await readFile(args[2],'utf8'));
     if(!body||typeof body!=='object'||Array.isArray(body))
       throw new Error('Presentation input must be a JSON object.');
   }
   if(command==='look-set'||command==='visibility-set'){
     if(!['audience','stage','broadcast'].includes(body.destination))
       throw new Error('Unknown worship output destination.');
     const field=command==='look-set'?'look':'mode';
     if(!Object.hasOwn(body,field)||Object.keys(body).some(key=>!['destination',field].includes(key)))
       throw new Error('Unknown worship output edit field or missing settings.');
     endpoint='/v1/worship/'+(command==='look-set'?'looks':'visibility')+'/'+body.destination;
     payload={[field]:body[field]};
   }else payload=command==='load'?{deck:body}:
     command==='worship-load'?{plan:body}:
     command==='macro-preview'?{macro:body}:body;
 }else if(command==='start'){
   if(args.length>2)throw new Error('Too many start arguments.');
   const mode=args[1]??'assisted';
   if(!['manual','assisted','automatic'].includes(mode))
     throw new Error('Invalid presentation mode.');
   payload={mode};
 }else if(command==='goto'){
   if(args.length!==2||!/^[1-9]\d{0,3}$/.test(args[1]))
     throw new Error('Goto requires a positive 1-based slide number.');
   payload={action:'goto',index:Number(args[1])-1};
 }else throw new Error('Unknown command.');
 if(requestId!==null){
   if(!payload)throw new Error('Stable request ID requires a control action.');
   payload.idempotencyKey=requestId;
 }
 const state=await readPrivateState();
 const address='http://127.0.0.1:'+state.port+endpoint;
 let response;
 try{
   response=await fetch(address,{
     method:payload?'POST':'GET',
     headers:{'Authorization':'Bearer '+state.token,
        ...(payload?{'Content-Type':'application/json'}:{})},
     ...(payload?{body:JSON.stringify(payload)}:{}),
     signal:AbortSignal.timeout(3000)
   });
 }catch{
   throw new Error('Presentation session is unavailable. Verify its managed server status; avoid replaying an uncertain write.');
 }
 let result;
 try{result=await response.json();}
 catch{throw new Error('Presentation session returned malformed JSON.');}
 if(!response.ok)throw new Error('Presentation request rejected ('+response.status+'): '+
   String(result?.error??'Unknown error').slice(0,180));
 process.stdout.write(JSON.stringify(result)+'\n');
}
run().catch(error=>{process.stderr.write('Presentation control error: '+error.message+'\n');process.exitCode=2;});
