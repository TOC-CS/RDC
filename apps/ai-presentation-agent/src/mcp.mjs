import {PresentationDirector} from './director.mjs';
import {presentationReadiness} from './readiness.mjs';
import {MemoryAdapter,makeAdapter,listPresentationAdapters} from './adapters.mjs';
import {VoiceInputRouter,voiceCapabilities} from './voice.mjs';
import {buildDeck,renderDeckHtml} from './deck.mjs';
import {renderDeckPptx} from './pptx-export.mjs';
import {VisualObservationRouter} from './watch.mjs';
import {compileWorshipService} from './worship-service.mjs';
import {createWorshipLibrary,compileWorshipFromLibrary} from './worship-library.mjs';
import {compileWorshipLook} from './worship-looks.mjs';
import {WorshipLookController} from './worship-look-control.mjs';
import {WorshipOutputVisibility} from './worship-output-visibility.mjs';
import {buildWorshipOperatorRundown} from './worship-rundown.mjs';
import {WorshipStageClock} from './worship-timing.mjs';
import {WorshipTeleprompter} from './worship-teleprompt.mjs';
import {preparePresentationRoomStatus} from './rdc-communications.mjs';
import {prepareWorshipMacro} from './worship-macro-plan.mjs';
import {writeFile,mkdir} from 'node:fs/promises';
import {resolve,join} from 'node:path';
const obj=(properties,required=[])=>({type:'object',properties,required,additionalProperties:false});
const str={type:'string'},bool={type:'boolean'},num={type:'number'};
const toolSchemas=[
 ['presentation_capabilities','Discover modes and verified adapter support.',obj({})],
 ['presentation_readiness','Inspect local application and tool readiness without opening devices or apps.',obj({})],
 ['presentation_status','Read current presentation state.',obj({})],
 ['presentation_communication_capabilities','Inspect the prepared RDC/DC/Atlas Bus two- and three-way room integration without opening chats or sending messages.',obj({})],
 ['presentation_communication_prepare','Prepare a metadata-only two- or three-member room status draft for a separately authenticated RDC ChatRoom.',obj({
   localSessionId:str,roomMembers:{type:'array',items:str,minItems:2,maxItems:3},
   roomKey:str,requestId:str
 },['localSessionId','roomMembers','roomKey','requestId'])],
 ['presentation_readback','Observe actual presentation output without advancing any slide.',obj({})],
 ['presentation_load','Load a presentation with lyrics or cues.',obj({deck:{type:'object'}},['deck'])],
 ['presentation_load_worship','Compile a worship service plan into rights-filtered public deck and independently protected stage views.',obj({plan:{type:'object'}},['plan'])],
 ['presentation_load_worship_library','Validate an owner-supplied worship catalog and exact service plan before loading existing separate audience, stage and broadcast views.',obj({catalog:{type:'object'},plan:{type:'object'}},['catalog','plan'])],
 ['presentation_worship_macro_preview','Validate a worship transition without executing broadcast, OBS or native output actions.',obj({macro:{type:'object'}},['macro'])],
 ['presentation_worship_looks','Get current output-specific Look settings, excluding private stage content.',obj({})],
 ['presentation_worship_rundown','Read source-bound, rights-safe current and next service cue metadata without accessing private stage notes.',obj({})],
 ['presentation_worship_look_set','Change a presentation-only Look when separately authorized by the local operator.',obj({destination:{type:'string',enum:['audience','stage','broadcast']},look:{type:'object'}},['destination','look'])],
 ['presentation_worship_visibility','Read local-only audience, stage and broadcast visibility settings.',obj({})],
 ['presentation_worship_visibility_set','Clear a local overlay or blank an audience HTML viewer with operator authorization, without native output or stream writes.',obj({destination:{type:'string',enum:['audience','stage','broadcast']},mode:{type:'string',enum:['visible','clear','blank']}},['destination','mode'])],
 ['presentation_unload','Clear a stopped deck and its recovery state without native display writes.',obj({})],
 ['presentation_create','Create an AI-authored presentation from sections.',obj({title:str,subtitle:str,theme:str,sections:{type:'array',items:{type:'object'}}},['title','sections'])],
 ['presentation_start','Begin in manual, assisted, or automatic mode.',obj({mode:{type:'string',enum:['manual','assisted','automatic']}})],
 ['presentation_stop','Stop local control and disarm future output without changing the native screen.',obj({})],
 ['presentation_command','Advance, hold, resume, navigate or change control mode.',obj({action:str,index:{type:'integer'},id:str,mode:str,idempotencyKey:str},['action'])],
 ['presentation_cue','Receive BandMates song, scripture or voice cue.',obj({source:str,type:str,song:str,section:str,occurrence:{type:'integer',minimum:1},reference:str,text:str,confidence:num,final:bool,eventId:str,timestamp:num},['source','type'])],
 ['presentation_watch','Receive processed camera vision observations; presentation feedback is excluded.',obj({frameId:str,cameraRole:str,observedText:str,recognizedSong:str,recognizedSection:str,recognizedReference:str,gesture:str,confidence:num,final:bool,timestamp:num},['frameId','cameraRole','confidence','final'])],
 ['presentation_voice','Get recognized speech from main AI app and return spoken reply text.',obj({transcript:str,confidence:num,final:bool,pushToTalk:bool,respondAloud:bool,eventId:str,source:str},['transcript'])],
 ['presentation_select_output','Configure Keynote, PowerPoint, ProPresenter, OBS, or offline HTML deck.',obj({kind:str,baseUrl:str,presentationId:str,url:str},['kind'])],
 ['presentation_arm','Allow/disallow external presentation writes with local operator grant.',obj({enabled:bool},['enabled'])],
 ['presentation_export_html','Export offline HTML slides.',obj({name:str})],
 ['presentation_export_json','Export machine-readable deck.',obj({name:str})],
 ['presentation_export_pptx','Export an offline PowerPoint-compatible 16:9 presentation.',obj({name:str})],
 ['live_comments_status','Inspect the authorized live-comment connector and posting permissions.',obj({})],
 ['live_comments_read','Read a bounded page of new comments from the configured authorized livestream.',obj({limit:{type:'integer'}})],
 ['live_comments_draft','Generate a proposed reply without posting anything.',obj({commentId:str},['commentId'])],
 ['live_comments_mode','Choose read-only, assisted or automatic response mode.',obj({mode:{type:'string',enum:['read-only','assisted','automatic']}},['mode'])],
 ['live_comments_arm','Arm livestream comment posting with a separate local operator grant.',obj({enabled:bool},['enabled'])],
 ['live_comments_reply','Respond to an observed live comment after authorization and moderation.',obj({commentId:str,text:str},['commentId'])],
];
const definitions=toolSchemas.map(([name,description,inputSchema])=>({name,description,inputSchema}));
const out=value=>({content:[{type:'text',text:JSON.stringify(value)}],structuredContent:value});
const result=(id,value)=>({jsonrpc:'2.0',id,result:value});
const fail=(id,code,message)=>({jsonrpc:'2.0',id,error:{code,message}});
const defaultExportDir=resolve(new URL('../exports',import.meta.url).pathname);
export function createMcpHandler({adapter=new MemoryAdapter(),allowExternalControl=false,allowWorshipLookChanges=false,allowStageClockControl=false,stageClock=new WorshipStageClock(),allowTelepromptControl=false,teleprompter=new WorshipTeleprompter(),liveCommentsAgent=null,allowLiveCommentPosting=false,exportRoot=defaultExportDir,clock,recoveredSession=null,stageGrant=null}={}){
 let director=new PresentationDirector({adapter,clock});
 if(recoveredSession)director.restore(recoveredSession.deck,{index:recoveredSession.index});
 let voice=new VoiceInputRouter(director);
 let watch=new VisualObservationRouter(director,{clock});
 let worshipSession=null,worshipDeckIdentity=null;
 // In-process state notifications are optional to MCP clients, but let an
 // authenticated loopback viewer respond immediately to actual slide changes
 // without repeatedly asking the controller for its complete deck.
 const subscribers=new Set();
 const dispatch=state=>{
   for(const listener of subscribers){
     try{listener(state);}catch{}
   }
 };
 let unsubscribeDirector=director.subscribe(dispatch);
 let lookController=new WorshipLookController({onChange:()=>dispatch(director.snapshot())});
 let outputVisibility=new WorshipOutputVisibility({onChange:()=>dispatch(director.snapshot())});
 if(!(stageClock instanceof WorshipStageClock))throw new TypeError('Independent stage clock required.');
 if(!(teleprompter instanceof WorshipTeleprompter))throw new TypeError('Private stage teleprompter required.');
 // Host-stable command receipts prevent replay after an uncertain HTTP/MCP
 // response. These receipts belong to the currently loaded presentation.
 const commandReceipts=new Map();
 const receiptLimit=16384;
 function executeCommandOnce(command){
   const key=command.idempotencyKey;
   if(key===undefined)return director.command(command);
   if(typeof key!=='string'||!/^[A-Za-z0-9._:-]{1,128}$/.test(key))
     throw new Error('Invalid presentation command idempotency key.');
   const signature=JSON.stringify({
     action:command.action,index:command.index??null,
     id:command.id??null,mode:command.mode??null
   });
   const previous=commandReceipts.get(key);
   if(previous){
     if(previous.signature!==signature)
       throw new Error('Presentation idempotency key conflict: already used for a different command.');
     return previous.promise;
   }
   if(commandReceipts.size>=receiptLimit)
     throw new Error('Presentation command receipt limit reached; load a new deck before issuing more unique commands.');
   const promise=director.command(command);
   commandReceipts.set(key,{signature,promise});
   return promise;
 }
 // Both direct worship plans and content-addressed libraries must share the
 // exact same director and private-output lifecycle. Compilation happens
 // before this function so rejected rights/provenance never disturb a show.
 function commitWorshipSession(candidate){
   const state=director.load(candidate.publicDeck);
   worshipSession=candidate;worshipDeckIdentity=director.deck;
   lookController.reset({restartRevision:true});
   outputVisibility.reset({restartRevision:true});
   stageClock.configure({label:"",durationMs:0});
   teleprompter.clear();
   dispatch(director.snapshot());
   commandReceipts.clear();
   return {...state,worship:{rundown:candidate.rundown,issues:candidate.issues,
     stageAvailable:candidate.stageAvailable}};
 }
 async function call(name,args){
   if(!args||typeof args!=='object'||Array.isArray(args)||Buffer.byteLength(JSON.stringify(args))>1_048_576)
      throw new Error('Invalid or oversized tool arguments.');
   switch(name){
   case 'presentation_capabilities':return {
     voice:voiceCapabilities({localSttModel:process.env.PRESENTATION_WHISPER_MODEL??null}),
     liveInputs:{audio:'host audio transcripts or BandMates event stream',visual:'host camera vision observations',nativeCaptureVerified:false},
     adapterReadiness:{
       'web-deck':'implemented',keynote:'script dictionary inspected; native test pending',
       'powerpoint-macos':'script dictionary inspected; native test pending',
       'powerpoint-windows':'Windows PowerPoint COM adapter implemented; Windows live test pending',
       propresenter:'official REST paths; device test pending',obs:'WebSocket 5; live device test pending',
       windows:'future bridge',ios:'future bridge',android:'future bridge'},
     availableCustomAdapters:listPresentationAdapters(),exportFormats:['html','json','pptx'],
     liveComments:{
       connected:!!liveCommentsAgent,
       readAvailable:!!liveCommentsAgent,
       postingRequiresSeparateOperatorGrant:true,
       postingAllowed:!!liveCommentsAgent&&allowLiveCommentPosting,
       provider:liveCommentsAgent?.status()?.provider??null,
       streamId:liveCommentsAgent?.status()?.streamId??null
     },
     modes:['manual','assisted','automatic'],provider:'AI-neutral MCP stdio',operatorApprovalRequired:true,
     operatorGrantPresent:allowExternalControl,
     limitations:'Native live microphone/camera streams need a separately configured bridge or a voice/vision-enabled AI host.'};
   case 'presentation_readiness':return presentationReadiness();
   case 'presentation_status':return director.snapshot();
   case 'presentation_communication_capabilities':return Object.freeze({
     schema:'toc.presentation.rdc-communications-capabilities/v1',
     roomSizes:Object.freeze([2,3]),
     paths:Object.freeze(['atlas-bus','rdc-terminal','dc-terminal','authorized-direct-chat']),
     existingAtlasBusRequired:true,
     crossProjectEnrollmentVerified:false,
     liveConnected:false,directChatPushAllowed:false,
     providerConversationObserved:false,automaticPeerWakeAllowed:false,
     defaultDelivery:'pull-only',
     sourceProject:'presentation',outputControlGranted:false,
     status:'synthetic-prototype-contract-only'
   });
   case 'presentation_communication_prepare':{
     if(Object.keys(args).some(key=>
       !['localSessionId','roomMembers','roomKey','requestId'].includes(key)))
       throw new Error('Unknown RDC communication preparation field.');
     return preparePresentationRoomStatus({...args,snapshot:director.snapshot()});
   }
   case 'presentation_readback':return director.readback();
   case 'presentation_worship_looks':return lookController.snapshot();
   case 'presentation_worship_rundown':{
     if(!worshipSession||director.deck!==worshipDeckIdentity)
       throw new Error('Load a worship service before inspecting its operator rundown.');
     const state=director.snapshot();
     return buildWorshipOperatorRundown(worshipSession,{
       index:state.index,started:state.started,held:state.held,
       mode:state.mode,outputFaulted:state.outputFaulted,
       looks:lookController.snapshot(),visibility:outputVisibility.snapshot()
     });
   }
   case 'presentation_worship_visibility':return outputVisibility.snapshot();
   case 'presentation_worship_visibility_set':{
     if(!allowWorshipLookChanges)
       throw new Error('Output visibility changes require a separate local operator grant.');
     if(!worshipSession||director.deck!==worshipDeckIdentity)
       throw new Error('Load a worship service before controlling its local output visibility.');
     if(director.busy)throw new Error('Wait for an active presentation operation to finish.');
     if(args.mode==='visible'&&director.outputFaulted)
       throw new Error('Output unverified; reload the deck before restoring local display.');
     return outputVisibility.set(args.destination,args.mode);
   }
   case 'presentation_worship_look_set':{
     if(!allowWorshipLookChanges)
       throw new Error('Worship Look changes require a separate local operator grant.');
     if(!worshipSession||director.deck!==worshipDeckIdentity)
       throw new Error('Load a verified worship service before editing its output Looks.');
     if(director.busy)throw new Error('Wait for the active presentation command to finish.');
     return lookController.set(args.destination,args.look);
   }
   case 'presentation_worship_macro_preview':{
     if(!director.deck)throw new Error('Load a deck before preparing worship macros.');
     return prepareWorshipMacro(args.macro,{deck:director.deck});
   }
   case 'presentation_unload':{
     const cleared=director.unload();
     worshipSession=null;worshipDeckIdentity=null;
     lookController.reset({restartRevision:true});
     outputVisibility.reset({restartRevision:true});
     stageClock.configure({label:"",durationMs:0});
     teleprompter.clear();
     commandReceipts.clear();
     voice=new VoiceInputRouter(director);
     watch=new VisualObservationRouter(director,{clock});
     return cleared;
   }
   case 'presentation_load':{
     const state=director.load(args.deck);
     worshipSession=null;worshipDeckIdentity=null;
     lookController.reset({restartRevision:true});
     outputVisibility.reset({restartRevision:true});
     stageClock.configure({label:"",durationMs:0});
     teleprompter.clear();
     commandReceipts.clear();return state;
   }
   case 'presentation_load_worship':{
     // Private source is retained in the closure, never in public status,
     // exports, SSE or an auditorium viewer.
     return commitWorshipSession(compileWorshipService(args.plan,{stageGrant}));
   }
   case 'presentation_load_worship_library':{
     if(Object.keys(args).some(key=>!['catalog','plan'].includes(key)))
       throw new Error('Unexpected worship library load field.');
     const catalog=createWorshipLibrary(args.catalog);
     const compiled=compileWorshipFromLibrary(args.plan,catalog,{stageGrant});
     return commitWorshipSession(compiled);
   }
   case 'presentation_create':{
     const state=director.load(buildDeck(args));
     worshipSession=null;worshipDeckIdentity=null;
     lookController.reset({restartRevision:true});
     outputVisibility.reset({restartRevision:true});
     stageClock.configure({label:"",durationMs:0});
     teleprompter.clear();
     commandReceipts.clear();return state;
   }
   case 'presentation_start':return director.start(args.mode??'assisted');
   case 'presentation_stop':{
     const result=await director.command({action:'stop'});
     if(stageClock.started&&!stageClock.paused){
       stageClock.pause();dispatch(director.snapshot());
     }
     return result.state;
   }
   case 'presentation_command':{
     const result=await executeCommandOnce(args);
     if(args.action==='stop'&&stageClock.started&&!stageClock.paused){
       stageClock.pause();dispatch(director.snapshot());
     }
     return result;
   }
   case 'presentation_cue':return director.ingest(args);
   case 'presentation_watch':return watch.receive(args);
   case 'presentation_voice':return voice.receive(args);
   case 'presentation_select_output':{
     if(director.started||director.busy)throw new Error('Presentation is running or an output operation is in progress. Switch output only after it is stopped and idle.');
     const {kind,...opts}=args,previousDeck=director.deck,adapter=makeAdapter(kind,opts);
     unsubscribeDirector();
     director=new PresentationDirector({adapter,clock});
     unsubscribeDirector=director.subscribe(dispatch);
     if(previousDeck)director.load(previousDeck);
     worshipSession=null;worshipDeckIdentity=null;
     lookController.reset({restartRevision:true});
     outputVisibility.reset({restartRevision:true});
     stageClock.configure({label:"",durationMs:0});
     teleprompter.clear();
     voice=new VoiceInputRouter(director);watch=new VisualObservationRouter(director,{clock});
     commandReceipts.clear();
     return {kind,armed:false,state:director.snapshot()};}
   case 'presentation_arm':
     if(args.enabled&&!allowExternalControl)
       throw new Error('External control requires local operator approval via PRESENTATION_ALLOW_EXTERNAL_CONTROL=1 when launching the agent.');
     return director.arm(args.enabled);
   case 'live_comments_status':{
     if(!liveCommentsAgent)throw new Error('Live comments connector is not connected.');
     return liveCommentsAgent.status();}
   case 'live_comments_read':{
     if(!liveCommentsAgent)throw new Error('Live comments connector is not connected.');
     return liveCommentsAgent.pollOnce(args);}
   case 'live_comments_draft':{
     if(!liveCommentsAgent)throw new Error('Live comments connector is not connected.');
     return liveCommentsAgent.draftReply(args.commentId);}
   case 'live_comments_mode':{
     if(!liveCommentsAgent)throw new Error('Live comments connector is not connected.');
     return liveCommentsAgent.setMode(args.mode);}
   case 'live_comments_arm':{
     if(!liveCommentsAgent)throw new Error('Live comments connector is not connected.');
     if(args.enabled&&!allowLiveCommentPosting)
       throw new Error('Live comment posting requires a separate local operator approval.');
     return liveCommentsAgent.arm(args.enabled);}
   case 'live_comments_reply':{
     if(!liveCommentsAgent)throw new Error('Live comments connector is not connected.');
     if(!allowLiveCommentPosting)
       throw new Error('Live comment posting requires a separate local operator approval.');
     return liveCommentsAgent.reply(args.commentId,args.text);}
   case 'presentation_export_html':
   case 'presentation_export_json':
   case 'presentation_export_pptx':{
     if(!director.deck)throw new Error('Load a deck first.');
     const extension=name==='presentation_export_html'?'html':name==='presentation_export_pptx'?'pptx':'json',filename=args.name??'presentation';
     if(typeof filename!=='string'||!/^[\w-]{1,80}$/.test(filename))throw new Error('Invalid export filename.');
     await mkdir(exportRoot,{recursive:true});
     const destination=join(exportRoot,filename+'.'+extension);
     const content=extension==='html'?renderDeckHtml(director.deck):extension==='pptx'?await renderDeckPptx(director.deck):JSON.stringify(director.deck,null,2);
     await writeFile(destination,content,{flag:'wx'});
     return {exported:true,file:destination,format:extension};}
   default:throw new Error('Unknown tool: '+name);
   }
 }
 const handle=async request=>{
   if(!request||request.jsonrpc!=='2.0'||typeof request.method!=='string')
     return fail(request?.id??null,-32600,'Invalid JSON-RPC request.');
   const {id,method,params={}}=request;
   try{
     if(method==='initialize')return result(id,{protocolVersion:'2025-06-18',
       capabilities:{tools:{listChanged:false}},serverInfo:{name:'ai-presentation-agent',version:'0.1.0-dev'},
       instructions:'Voice defaults to the AI host. Camera observation requires a vision-enabled host. External writes require a local operator grant.'});
     if(method==='notifications/initialized'||method==='notifications/cancelled')return null;
     if(method==='ping')return result(id,{});
     if(method==='tools/list')return result(id,{tools:definitions});
     if(method==='tools/call'){
       if(typeof params?.name!=='string')return fail(id,-32602,'Tool name required.');
       try{return result(id,out(await call(params.name,params.arguments??{})));}
       catch(error){return result(id,{content:[{type:'text',text:String(error.message??error)}],isError:true});}
     }
     return fail(id,-32601,'Method not found.');
   }catch(error){return fail(id,-32603,String(error.message??error));}
 };
 handle.subscribe=listener=>{
   if(typeof listener!=='function')throw new TypeError('Presentation state subscriber must be a function.');
   subscribers.add(listener);
   return ()=>subscribers.delete(listener);
 };
 // These are in-process, host-owned getters, never exposed through MCP
 // tools or the public REST API. The HTTP stage viewer separately checks an
 // independent owner-only stage credential before invoking them.
 handle.getAudienceLook=()=>{
   if(!worshipSession||director.deck!==worshipDeckIdentity)return null;
   const look=lookController.get('audience');
   return {layout:look.layout,background:look.background,
     layers:[...look.layers],revision:lookController.revision,
     visibility:outputVisibility.get('audience')};
 };
 handle.getPrivateStageClock=providedGrant=>{
   if(!worshipSession||director.deck!==worshipDeckIdentity||
      !stageGrant||providedGrant!==stageGrant)return null;
   return stageClock.snapshot();
 };
 handle.updatePrivateStageClock=(providedGrant,args)=>{
   if(!worshipSession||director.deck!==worshipDeckIdentity)
     throw new Error('Load a worship service before using the private stage clock.');
   if(!stageGrant||providedGrant!==stageGrant)
     throw new Error('Separate private stage authorization is required.');
   if(!allowStageClockControl)
     throw new Error('Stage timer updates require separate local operator grant.');
   if(!args||typeof args!=='object'||Array.isArray(args))
     throw new Error('Private stage clock action object required.');
   const allowed=args.action==='configure'?['action','label','durationMs']:['action'];
   for(const key of Object.keys(args))
     if(!allowed.includes(key))
       throw new Error('Unexpected private stage clock field.');
   let state;
   if(args.action==='configure')state=stageClock.configure({
     label:args.label??'',durationMs:args.durationMs??0
   });
   else if(args.action==='start')state=stageClock.start();
   else if(args.action==='pause')state=stageClock.pause();
   else if(args.action==='resume')state=stageClock.resume();
   else if(args.action==='reset')state=stageClock.reset();
   else throw new Error('Unknown private stage timer action.');
   dispatch(director.snapshot());
   return state;
 };
 // One protected source for private stage teleprompter and confidence SSE.
 // The stage Look can suppress notes/text even for an authenticated monitor.
 function syncPrivateTeleprompter(providedGrant){
   if(!worshipSession||director.deck!==worshipDeckIdentity||
      !stageGrant||providedGrant!==stageGrant)return false;
   const state=director.snapshot();
   if(!Array.isArray(state.slides)||!state.slides.length)return false;
   const cue=worshipSession.getStageCue(state.index,providedGrant);
   if(!cue)return false;
   const layers=new Set(lookController.get('stage').layers);
   teleprompter.syncCue({
     id:cue.id,title:cue.title,
     text:layers.has('text')?cue.text:'',
     notes:layers.has('notes')?cue.notes:'',
     section:layers.has('section')?cue.section:''
   });
   return true;
 }
 handle.getPrivateTeleprompt=providedGrant=>{
   if(!syncPrivateTeleprompter(providedGrant))return null;
   const data=teleprompter.snapshot();
   if(outputVisibility.get('stage')==='clear')
     return Object.freeze({...data,loaded:false,current:'',next:'',title:'',section:''});
   return data;
 };
 handle.updatePrivateTeleprompt=(providedGrant,args)=>{
   if(!worshipSession||director.deck!==worshipDeckIdentity)
     throw new Error('Load a worship service before controlling the private teleprompter.');
   if(!stageGrant||providedGrant!==stageGrant)
     throw new Error('Separate private stage authorization required.');
   if(!allowTelepromptControl)
     throw new Error('Private teleprompter requires a separate local operator grant.');
   if(!args||typeof args!=='object'||Array.isArray(args))
     throw new Error('Invalid private teleprompter command.');
   const action=args.action;
   const allowed=action==='configure'?
     ['action','role','fontScale','scrollSpeed','mirrored']:
     action==='follow'?['action','text','confidence','final','eventId','timestamp']:
     ['action'];
   if(Object.keys(args).some(key=>!allowed.includes(key)))
     throw new Error('Unexpected private teleprompter field.');
   if(!syncPrivateTeleprompter(providedGrant))
     throw new Error('Private stage cue is unavailable.');
   let follow=null;
   if(action==='configure')teleprompter.configure(args);
   else if(action==='follow')follow=teleprompter.follow(args);
   else if(action==='next')teleprompter.next();
   else if(action==='previous')teleprompter.previous();
   else if(action==='hold')teleprompter.hold();
   else if(action==='resume')teleprompter.resume();
   else throw new Error('Unsupported private teleprompter action.');
   dispatch(director.snapshot());
   return Object.freeze({...teleprompter.snapshot(),
     ...(follow?{follow:Object.freeze({...follow})}:{})});
 };
 handle.getPrivateStageCue=providedGrant=>{
   if(!worshipSession||director.deck!==worshipDeckIdentity||!stageGrant||providedGrant!==stageGrant)return null;
   const state=director.snapshot();
   if(!Array.isArray(state.slides)||!state.slides.length)return null;
   const cue=worshipSession.getStageCue(state.index,providedGrant);
   if(!cue)return null;
   const look=lookController.get('stage');
   const enabled=new Set(look.layers);
   const safeCue={
     id:cue.id,title:enabled.has('title')?cue.title:'',
     text:enabled.has('text')?cue.text:'',
     section:enabled.has('section')?cue.section??'':'',
     notes:enabled.has('notes')?cue.notes:'',
     chords:enabled.has('chords')?cue.chords:[],
     key:enabled.has('key')?cue.key??'':''
   };
   const hidden=outputVisibility.get('stage')==='clear';
   return {index:state.index,started:state.started,held:state.held,
     outputFaulted:state.outputFaulted,
     current:hidden?{id:cue.id,title:'',text:'',section:'',notes:'',chords:[],key:''}:safeCue,
     next:hidden?null:enabled.has('next')?cue.next??null:null,
     visibility:outputVisibility.get('stage'),
     clock:hidden||!enabled.has('timer')?null:stageClock.snapshot(),
     teleprompt:hidden?null:handle.getPrivateTeleprompt(providedGrant),
     look:{layout:look.layout,background:look.background,
       revision:lookController.revision}};
 };
 handle.getWorshipLook=(destination,providedGrant=null,look=null)=>{
   if(!worshipSession||director.deck!==worshipDeckIdentity)return null;
   if(destination==='stage'&&(!stageGrant||providedGrant!==stageGrant))return null;
   const state=director.snapshot();
   if(!Array.isArray(state.slides)||!state.slides.length||
      !Number.isSafeInteger(state.index))return null;
   const configured=look??(()=>{const preset=lookController.get(destination);return {layout:preset.layout,background:preset.background,layers:preset.layers};})();
   const packet=compileWorshipLook(worshipSession,{
     destination,index:state.index,stageGrant:providedGrant,look:configured
   });
   const visibility=outputVisibility.get(destination);
   if(visibility==='visible')return Object.freeze({
     ...packet,revision:lookController.revision,visibility
   });
   const blankLayers=Object.freeze(Object.fromEntries(
     Object.keys(packet.layers).map(key=>[key,Array.isArray(packet.layers[key])?Object.freeze([]):''])
   ));
   return Object.freeze({
     ...packet,revision:lookController.revision,visibility,
     current:Object.freeze({id:packet.slideId,title:'',text:''}),
     layers:blankLayers
   });
 };
 handle.getBroadcastCue=()=>{
   if(!worshipSession||director.deck!==worshipDeckIdentity)return null;
   const state=director.snapshot();
   const cue=worshipSession.broadcastDeck.slides[state.index];
   if(!cue)return null;
   // Public-safe fields only, no references to the original service plan.
   const look=lookController.get('broadcast');
   const enabled=new Set(look.layers);
   const hidden=outputVisibility.get('broadcast')==='clear';
   const shown={...cue,title:!hidden&&enabled.has('title')?cue.title:'',
     text:!hidden&&enabled.has('text')?cue.text:'',
     reference:!hidden&&enabled.has('reference')?cue.reference??'':''};
   return {index:state.index,started:state.started,held:state.held,
     outputFaulted:state.outputFaulted,current:shown,
     visibility:outputVisibility.get('broadcast'),
     look:{layout:look.layout,background:look.background,
       revision:lookController.revision},obsSceneChanged:false};
 };
 return handle;
}
