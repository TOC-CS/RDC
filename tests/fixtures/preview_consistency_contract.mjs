// Real pinned App/PostMessageTransport run against a synthetic host. This does
// not establish browser layout or ChatGPT's pre-mount App resource handling.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {App,PostMessageTransport} from '../../rdc/embedded/node_modules/@modelcontextprotocol/ext-apps/dist/src/app.js';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const SID='b2957a7b-2062-483f-b174-9c0a3d113d55';
const SID2='12345678-1234-1234-1234-123456789abc';
const JOB='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const OTHER_JOB='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const openData=(id=SID)=>({device_id:'fixture-device',sessions:[{session_id:id,browser:'chromium',url:'https://example.test/',width:900,height:560}],session_id:id,viewer:{bound_to_session:true}});
const toolResult=data=>({structuredContent:data,content:[{type:'text',text:JSON.stringify(data)}]});
const frameResult=(id=SID)=>({structuredContent:{device_id:'fixture-device',session_id:id,width:900,height:560,mime_type:'image/png'},content:[{type:'image',mimeType:'image/png',data:'cG5n'}]});
const pendingResult=id=>toolResult({ok:true,pending:true,operation_id:id,recovery_tool:'rdc_operation_status',status:'claimed'});
const expiredData=id=>({ok:false,error:{code:'result_expired',message:'PRIVATE_HOST_DETAIL: the worker\'s retained "response" expired.'},operation_id:id,completed:true});
const refreshRequired=(id,tool)=>toolResult({ok:true,preview_refresh_required:true,refresh_tool:tool,operation_id:id,completed:true,reason:'result_expired'});
function expiredReply(ui,request,shape='structured',changes={}){
  const data={...expiredData(request.params.arguments.operation_id),...changes};
  if(shape==='hint')ui.send({id:request.id,result:refreshRequired(data.operation_id,changes.refresh_tool||'rdc_preview_open')});
  else if(shape==='wrapped'){
    const escaped=JSON.stringify(data).replace(/\\/g,'\\\\').replace(/'/g,"\\'");
    const detail=`Error code: INVALID_ARGUMENT; Error: RuntimeException: Error calling MCP tool: [TextContent(type='text', text='${escaped}', annotations=None, meta=None)]`;
    ui.send({id:request.id,error:{code:-32603,message:JSON.stringify({detail})}});
  }else ui.send({id:request.id,result:{...toolResult(data),isError:true}});
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
// The transport logs successful wire frames at debug level. Keep warnings and
// errors visible while avoiding thousands of duplicate successful messages.
console.debug=()=>{};
class Element {
  constructor(tag='div'){this.tagName=tag.toUpperCase();this.children=[];this.style={};this.dataset={};this.value='';this.hidden=false;this.disabled=false;this.listeners={};this.attributes={};this._text='';this.clientWidth=900;this.clientHeight=560;this.classList={add(){},remove(){},toggle(){},contains(){return false;}};}
  set textContent(value){this._text=String(value??'');this.children=[];}
  get textContent(){return this._text+this.children.map(child=>child.textContent||'').join('');}
  append(...children){this.children.push(...children);}prepend(...children){this.children.unshift(...children);}replaceChildren(...children){this._text='';this.children=children;}
  addEventListener(name,fn){(this.listeners[name]??=[]).push(fn);}setAttribute(name,value){this.attributes[name]=String(value);}getAttribute(name){return this.attributes[name]??null;}removeAttribute(name){delete this.attributes[name];delete this[name];}
  focus(){}getBoundingClientRect(){return {width:900,height:560};}
}
function fixture({initialize='success',initial='open',session=SID,holdTools=false,includeInput=true,jobId=null,frameTaskId=null,hostModes=['inline','fullscreen'],clock=()=>0,legacyMode=null}={}){
  const nodes=new Map(),messageListeners=new Set(),windowListeners=new Map(),timers=new Map(),wire=[],tools=[],heldInitial=[],heldTools=[];let sequence=0,initMode=initialize,taskStatus='running';
  const openResult=()=>{const data=openData(session);if(jobId)data.viewer={...data.viewer,task_job_id:jobId,task_complete:['completed','failed','cancelled','timed_out'].includes(taskStatus)};return toolResult(data)};
  for(const match of fs.readFileSync(path.join(root,'rdc/embedded/src/index.html'),'utf8').matchAll(/<([a-z][a-z0-9]*)\b[^>]*\bid="([^"]+)"[^>]*>/g)){const node=new Element(match[1]);node.hidden=/\shidden(?:\s|>)/.test(match[0]);node.disabled=/\sdisabled(?:\s|>)/.test(match[0]);nodes.set(match[2],node);}
  const documentEvents = new Map();
  const document={getElementById:id=>nodes.get(id),createElement:tag=>new Element(tag),querySelectorAll:()=>[],
    addEventListener(name,fn){documentEvents.set(name,fn);},hidden:false,documentElement:new Element('html'),body:new Element('body')};
  function setDocumentHidden(hidden){document.hidden=hidden;documentEvents.get('visibilitychange')?.();}
  const host={postMessage(message){
    wire.push(message);
    if(message.method==='ui/initialize'){
      if(initMode==='hold')heldInitial.push(message);
      else if(initMode==='reject')queueMicrotask(()=>send({id:message.id,error:{code:-32000,message:'Synthetic initialize rejection'}}));
      else queueMicrotask(()=>initializeReply(message));
    }else if(message.method==='ui/notifications/initialized'){
      if(includeInput)queueMicrotask(()=>send({method:'ui/notifications/tool-input',params:{arguments:{session_id:session,...(jobId?{job_id:jobId}:{})}}}));
      if(initial==='open')queueMicrotask(()=>send({method:'ui/notifications/tool-result',params:openResult()}));
      else if(initial==='unbound')queueMicrotask(()=>send({method:'ui/notifications/tool-result',params:toolResult({device_id:'fixture-device',session_id:null,sessions:[],viewer:{bound_to_session:false}})}));
      else if(initial==='pending')queueMicrotask(()=>send({method:'ui/notifications/tool-result',params:pendingResult('original-open-operation')}));
      else if(initial==='offline'||initial==='busy')queueMicrotask(()=>send({method:'ui/notifications/tool-result',params:toolResult({ok:true,preview_unavailable:true,preview_status:initial==='offline'?'device_offline':'gateway_busy',message:'Fixed gateway availability result',device_id:'fixture-device'})}));
    }else if(message.method==='ui/request-display-mode'){
      const actual=hostModes.includes(message.params.mode)?message.params.mode:'inline';
      queueMicrotask(()=>send({id:message.id,result:{mode:actual}}));
    }else if(message.method==='tools/call'){
      tools.push(message.params);
      if(typeof holdTools==='function'?holdTools(message.params.name):holdTools)heldTools.push(message);
      else queueMicrotask(()=>toolReply(message));
    }else if(message.id!==undefined)queueMicrotask(()=>send({id:message.id,result:{}}));
  }};
  const window={parent:host,innerWidth:1000,innerHeight:800,addEventListener(name,fn){if(name==='message')messageListeners.add(fn);else{const items=windowListeners.get(name)||[];items.push(fn);windowListeners.set(name,items);}},removeEventListener(name,fn){if(name==='message')messageListeners.delete(fn);}};
  const legacyRequests=[];
  if(legacyMode)window.openai={displayMode:'inline',requestDisplayMode:async({mode})=>{
    legacyRequests.push(mode);
    const actual=mode==='pip'?legacyMode:'inline';
    window.openai.displayMode=actual;
    return {mode:actual};
  }};
  function send(value){for(const fn of [...messageListeners])fn({source:host,data:{jsonrpc:'2.0',...value}});}
  function initializeReply(message){send({id:message.id,result:{protocolVersion:message.params.protocolVersion,hostInfo:{name:'Pinned SDK test host',version:'1'},hostCapabilities:{serverTools:{},updateModelContext:{text:{}}},hostContext:{displayMode:'inline',availableDisplayModes:hostModes}}});}
  function toolReply(message){
    const {name,arguments:args}=message.params;
    assert.ok(['rdc_preview_open','rdc_preview_frame','rdc_operation_status'].includes(name), 'Unexpected preview call '+name);
    if(name==='rdc_preview_open')assert.equal(args.session_id,session);
    if(name==='rdc_preview_frame' && jobId) assert.equal(args.job_id,jobId);
    let result=name==='rdc_preview_frame'?frameResult(args.session_id):openResult();
    if(name==='rdc_preview_frame' && (jobId||frameTaskId)){
      const task={job_id:frameTaskId||jobId,status:taskStatus,complete:['completed','failed','cancelled','timed_out'].includes(taskStatus)};
      result=task.complete?toolResult({device_id:'fixture-device',session_id:args.session_id,task}):
        {...result,structuredContent:{...result.structuredContent,task}};
    }
    send({id:message.id,result});
  }
  // Only shorten the actual SDK request deadline. Production is still required
  // to supply its 15000ms deadline; no SDK or transport mechanics are mocked.
  class BoundedApp extends App {connect(transport,options){assert.equal(options.timeout,15000);return super.connect(transport,{...options,timeout:40});}}
  const saved={window:globalThis.window,document:globalThis.document,ResizeObserver:globalThis.ResizeObserver,requestAnimationFrame:globalThis.requestAnimationFrame};
  Object.assign(globalThis,{window,document,ResizeObserver:class{observe(){}disconnect(){}},requestAnimationFrame:fn=>fn()});
  const context=vm.createContext({App:BoundedApp,PostMessageTransport,document,window,URL,Map,Set,Date,Number,Promise,performance:{now:clock},crypto:{randomUUID:()=>SID},console,setTimeout:(fn,delay)=>{timers.set(++sequence,{fn,delay});return sequence;},clearTimeout:id=>timers.delete(id)});
  const source=fs.readFileSync(path.join(root,'rdc/embedded/src/app.js'),'utf8').replace(/^import .*?;\r?\n/,'').replace(/\nconnect\(\);\s*$/,'\n');
  vm.runInContext(source+"\nglobalThis.ui={app,state,connect,refreshSessions,refreshFrame,hidePreview,reopenPreview,dispose};",context);
  async function click(id){for(const fn of nodes.get(id).listeners.click||[])await fn({preventDefault(){}});await settle();}
  async function runDelay(delay){const entry=[...timers].find(([,item])=>item.delay===delay);assert.ok(entry,`Missing UI timer ${delay}`);timers.delete(entry[0]);const result=entry[1].fn();await settle();return {result};}
  async function cleanup(){context.ui.dispose();await context.ui.app.close();Object.assign(globalThis,saved);}
  return {...context.ui,nodes,wire,tools,legacyRequests,setDocumentHidden,heldInitial,heldTools,timers,messageListeners,send,initializeReply,toolReply,click,runDelay,cleanup,setTaskStatus:value=>{taskStatus=value;},setInitialize:value=>{initMode=value;},setHoldTools:value=>{holdTools=value;}};
}
const which=process.argv[2];
if(which==='legacy-user-float'){
  const ui=fixture({legacyMode:'pip'});try{
    await ui.connect();await settle();
    assert.deepEqual(ui.legacyRequests,[],'No unadvertised automatic mode request');
    assert.equal(ui.nodes.get('float').hidden,false,'Offer the documented host bridge on user click');
    await ui.click('float');
    assert.deepEqual(ui.legacyRequests,['pip']);
    assert.equal(ui.state.mode,'pip','Only confirmed PiP is accepted');
    assert.equal(ui.wire.filter(x=>x.method==='ui/request-display-mode').length,0);
  }finally{await ui.cleanup();}
}else if(which==='legacy-user-refused'){
  const ui=fixture({legacyMode:'fullscreen'});try{
    await ui.connect();await settle();await ui.click('float');
    assert.deepEqual(ui.legacyRequests,['pip','inline'],'Restore inline after fullscreen substitution');
    assert.equal(ui.state.mode,'inline');
    assert.equal(ui.nodes.get('float-note').textContent,'Floating is unavailable in this host.');
    assert.equal(ui.tools.length,0,'Presentation request never dispatches worker work');
  }finally{await ui.cleanup();}
}else if(which==='late-bound-input'){
  const ui=fixture({initial:'unbound',includeInput:false});try{
    await ui.connect();await settle();
    assert.equal(ui.state.haveOpenResult,false);
    assert.equal(ui.tools.length,0,'No unscoped discovery');
    ui.send({method:'ui/notifications/tool-input',params:{arguments:{session_id:SID}}});
    await settle();await ui.runDelay(0);await settle();
    assert.equal(ui.state.haveOpenResult,true,'Late explicit source must recover an unbound initial result');
    assert.equal(ui.state.sessionId,SID);
    assert.equal(ui.tools.filter(t=>t.name==='rdc_preview_open').length,1);
  }finally{await ui.cleanup();}
}else if(which==='pending-not-floating'){
  const ui=fixture({initial:'pending',holdTools:true,hostModes:['inline','fullscreen','pip']});try{
    await ui.connect();await settle();await settle();
    assert.equal(ui.state.haveOpenResult,false);
    assert.equal(ui.wire.filter(x=>x.method==='ui/request-display-mode').length,0,'Pending unverified source must not float an empty view');
  }finally{await ui.cleanup();}
}else if(which==='frame-fast-cadence'||which==='frame-slow-cadence'){
  let now=0;
  const ui=fixture({holdTools:true,clock:()=>now});try{
    await ui.connect();await settle();
    const frame=ui.refreshFrame(true);await settle();
    now=which==='frame-fast-cadence'?40:900;
    ui.toolReply(ui.heldTools.shift());await frame;
    assert.equal(ui.state.busy,false);
    assert.equal([...ui.timers.values()][0]?.delay,which==='frame-fast-cadence'?250:900,'Successful reads adapt the idle wait to measured read time');
    assert.equal(ui.tools.filter(t=>t.name==='rdc_preview_frame').length,1,'No overlapping frames');
  }finally{await ui.cleanup();}
}else if(which==='job-floating-supported'){
  const ui=fixture({jobId:JOB,hostModes:['inline','fullscreen','pip']});try{
    await ui.connect();await settle();await settle();
    assert.ok(ui.wire.some(x=>x.method==='ui/request-display-mode'&&x.params.mode==='pip'));
    assert.equal(ui.state.mode,'pip','Host-confirmed PiP must be used for floating');
    ui.setTaskStatus('completed');await ui.refreshFrame(true);await settle();
    assert.equal(ui.state.hidden,true);
    assert.ok(ui.wire.some(x=>x.method==='ui/notifications/request-teardown'));
  }finally{await ui.cleanup();}
}else if(which==='job-floating-unsupported'){
  const ui=fixture({jobId:JOB,hostModes:['inline','fullscreen']});try{
    await ui.connect();await settle();
    assert.equal(ui.state.mode,'inline');
    assert.equal(ui.nodes.get('float').hidden,true);
    assert.equal(ui.wire.filter(x=>x.method==='ui/request-display-mode').length,0);
    ui.setTaskStatus('completed');await ui.refreshFrame(true);await settle();
    assert.equal(ui.state.hidden,true);
    assert.equal(ui.wire.filter(x=>x.method==='ui/notifications/request-teardown').length,0,
      'No host floating view to close when PiP is unavailable');
  }finally{await ui.cleanup();}
}else if(which==='job-next-task'){
  const ui=fixture({jobId:JOB,hostModes:['inline','fullscreen','pip']});try{
    await ui.connect();await settle();await settle();
    ui.setTaskStatus('completed');await ui.refreshFrame(true);await settle();
    assert.equal(ui.state.hidden,true);
    ui.send({method:'ui/notifications/tool-result',params:toolResult(openData(SID))});
    await settle();
    assert.equal(ui.state.hidden,true,'Late stale result cannot revive finished job');
    ui.send({method:'ui/notifications/tool-input',params:{arguments:{session_id:SID,job_id:OTHER_JOB}}});
    const data=openData(SID);
    data.viewer={...data.viewer,task_job_id:OTHER_JOB,task_complete:false};
    ui.send({method:'ui/notifications/tool-result',params:toolResult(data)});
    await settle();
    assert.equal(ui.state.taskJobId,OTHER_JOB,'Explicit new job may claim a fresh task view');
    assert.equal(ui.state.hidden,false,"New job explicit open may reopen the previous hidden view");
  }finally{await ui.cleanup();}
}else if(which==='job-running'){
  const ui=fixture({jobId:JOB});try{
    await ui.connect();await settle();
    assert.equal(ui.state.taskJobId,JOB,'Exact source view binds only explicit host job');
    await ui.refreshFrame(true);
    assert.equal(ui.state.hidden,false);
    assert.equal(ui.nodes.get('frame').hidden,false);
    assert.equal(ui.tools.filter(t=>t.name==='rdc_preview_frame')[0].arguments.job_id,JOB);
    assert.equal(ui.wire.filter(x=>x.method==='ui/notifications/request-teardown').length,0);
  }finally{await ui.cleanup();}
}else if(which==='job-terminal'){
  const ui=fixture({jobId:JOB});try{
    await ui.connect();await settle();ui.state.mode='pip';
    ui.setTaskStatus('completed');
    await ui.refreshFrame(true);await settle();
    assert.equal(ui.state.hidden,true,'Completed exact job must auto-clear viewer');
    assert.equal(ui.state.sessionId,SID,'Source remains bound after viewer clears');
    assert.equal(ui.state.taskJobId,JOB,'Job identity survives late results');
    assert.equal(ui.timers.size,0,'No polling after terminal task');
    assert.equal(ui.tools.filter(t=>t.name==='rdc_preview_frame').length,1,'One definitive completion observation');
    assert.ok(ui.wire.some(x=>x.method==='ui/notifications/request-teardown'),'Host should receive floating-window teardown request');
  }finally{await ui.cleanup();}
}else if(which==='job-mismatch'){
  const ui=fixture({jobId:JOB,frameTaskId:OTHER_JOB});try{
    await ui.connect();await settle();ui.state.mode='pip';ui.setTaskStatus('completed');
    await ui.refreshFrame(true);await settle();
    assert.equal(ui.state.hidden,false,'Unrelated completed job cannot clear selected task');
    assert.equal(ui.state.sessionId,SID);
    assert.equal(ui.wire.filter(x=>x.method==='ui/notifications/request-teardown').length,0);
  }finally{await ui.cleanup();}
}else if(which==='job-unknown'){
  const ui=fixture({jobId:JOB});try{
    await ui.connect();await settle();ui.state.mode='pip';ui.setTaskStatus('interrupted');
    await ui.refreshFrame(true);await settle();
    assert.equal(ui.state.hidden,false,'Uncertain worker interruption cannot clear floating view');
    assert.equal(ui.nodes.get('frame').hidden,false);
    assert.equal(ui.wire.filter(x=>x.method==='ui/notifications/request-teardown').length,0);
  }finally{await ui.cleanup();}
}else if(which==='repeated'){
  for(let index=0;index<30;index++){
    const ui=fixture();try{await ui.connect();await settle();assert.equal(ui.state.connected,true);assert.equal(ui.state.sessionId,SID);assert.equal(ui.messageListeners.size,1);await ui.refreshSessions(true);await ui.refreshSessions(true);assert.equal(ui.tools.filter(item=>item.name==='rdc_preview_open').length,2);assert.equal(ui.wire.filter(item=>item.method==='ui/initialize').length,1);assert.equal(ui.messageListeners.size,1);}finally{await ui.cleanup();}assert.equal(ui.messageListeners.size,0);
  }
}else if(which==='retry'){
  const ui=fixture({initialize:'reject',initial:'none'});try{ui.state.sessionId=SID;ui.state.pendingOpen={operation_id:'original-operation',halted:true,sessionId:SID,deadline:120000};await ui.connect();assert.equal(ui.state.connected,false);assert.equal(ui.nodes.get('connection-retry').hidden,false);assert.equal(ui.messageListeners.size,0);ui.setInitialize('success');await ui.click('connection-retry');assert.equal(ui.state.connected,true);assert.equal(ui.state.sessionId,SID);assert.equal(ui.state.pendingOpen.operation_id,'original-operation');assert.equal(ui.tools.length,0);}finally{await ui.cleanup();}
}else if(which==='delayed'){
  const ui=fixture({initialize:'hold',initial:'none'});try{const connecting=ui.connect();await settle();await ui.connect();assert.equal(ui.heldInitial.length,1);assert.equal(ui.nodes.get('connection-retry').disabled,true);ui.initializeReply(ui.heldInitial.shift());await connecting;assert.equal(ui.state.connected,true);assert.equal(ui.tools.length,0);}finally{await ui.cleanup();}
}else if(which==='timeout'){
  const ui=fixture({initialize:'hold',initial:'none'});try{await ui.connect();assert.equal(ui.state.connected,false);assert.equal(ui.nodes.get('connection-retry').hidden,false);const old=ui.heldInitial.shift();const retry=ui.click('connection-retry');await settle();const current=ui.heldInitial.shift();assert.notEqual(old.id,current.id);ui.initializeReply(old);await settle();assert.equal(ui.state.connected,false,'A late expired reply must not complete the new handshake');ui.initializeReply(current);await retry;assert.equal(ui.state.connected,true);assert.equal(ui.tools.length,0);}finally{await ui.cleanup();}
}else if(which==='hide'){
  const ui=fixture();try{await ui.connect();await settle();await ui.refreshFrame(true);assert.equal(ui.nodes.get('frame').hidden,false);ui.setHoldTools(true);const pending=ui.refreshFrame(true);await settle();ui.hidePreview();ui.toolReply(ui.heldTools.shift());await pending;assert.equal(ui.nodes.get('panel').hidden,true);assert.equal(ui.state.sessionId,SID);const opens=ui.tools.filter(item=>item.name==='rdc_preview_open').length;ui.reopenPreview();ui.setHoldTools(false);await ui.refreshFrame(true);assert.equal(ui.nodes.get('frame').hidden,false);assert.equal(ui.tools.filter(item=>item.name==='rdc_preview_open').length,opens);}finally{await ui.cleanup();}
}else if(which==='dispose'){
  const old=fixture({holdTools:true});await old.connect();await settle();const pending=old.refreshFrame(true);await settle();old.dispose();old.toolReply(old.heldTools.shift());await pending;old.send({method:'ui/notifications/tool-result',params:toolResult(openData(SID2))});await settle();assert.equal(old.state.sessionId,SID);assert.equal(old.nodes.get('frame').hidden,true);await old.cleanup();
  const current=fixture({session:SID2});try{await current.connect();await settle();old.send({method:'ui/notifications/tool-result',params:toolResult(openData(SID))});await settle();assert.equal(current.state.sessionId,SID2);assert.equal(current.messageListeners.size,1);}finally{await current.cleanup();}
}else if(which==='pending'){
  const ui=fixture({initial:'pending'});try{await ui.connect();await settle();assert.equal(ui.state.pendingOpen.operation_id,'original-open-operation');const first=ui.refreshSessions(false);await settle();ui.hidePreview();await first;assert.equal(ui.state.pendingOpen.operation_id,'original-open-operation');ui.reopenPreview();const resumed=ui.refreshSessions(false);await settle();await ui.runDelay(500);await resumed;assert.equal(ui.state.pendingOpen,null);assert.equal(ui.tools.filter(item=>item.name==='rdc_preview_open').length,0);assert.equal(ui.tools.filter(item=>item.name==='rdc_operation_status').length,1);assert.equal(ui.tools[0].arguments.operation_id,'original-open-operation');}finally{await ui.cleanup();}
}else if(which==='late-context'){
  const ui=fixture();try{await ui.connect();await settle();ui.dispose();ui.send({method:'ui/notifications/host-context-changed',params:{displayMode:'fullscreen'}});await settle();assert.equal(ui.state.mode,'inline','Disposed view must ignore late host context');assert.equal(ui.timers.size,0);}finally{await ui.cleanup();}
}else if(which==='offline'||which==='busy'){
  const ui=fixture({initial:which});try{ui.state.sessionId=SID;if(which==='busy')ui.state.pendingOpen={operation_id:'prior-unknown-open',halted:true,sessionId:SID,deadline:120000};await ui.connect();await settle();assert.equal(ui.state.connected,true);assert.equal(ui.state.sessionId,SID);assert.equal(ui.nodes.get('frame').hidden,true);assert.ok(ui.nodes.get('preview-retry'),'Availability requires an explicit retry control');assert.equal(ui.nodes.get('preview-retry').hidden,false);assert.equal(ui.nodes.get('preview-retry').disabled,false);assert.equal(ui.nodes.get('connection-text').textContent,which==='offline'?'Device offline':'Gateway busy');assert.match(ui.nodes.get('empty-copy').textContent,/No new preview request was queued/);assert.equal(ui.tools.length,0);assert.equal(ui.timers.size,0);const retry=ui.click('preview-retry');if(which==='busy'){await settle();await ui.runDelay(500);}await retry;assert.equal(ui.tools.filter(item=>item.name==='rdc_preview_open').length,which==='offline'?1:0);if(which==='busy')assert.equal(ui.tools.find(item=>item.name==='rdc_operation_status').arguments.operation_id,'prior-unknown-open');assert.equal(ui.state.sessionId,SID);assert.equal(ui.nodes.get('preview-retry').hidden,true);}finally{await ui.cleanup();}
}else if(which==='offline-hidden'){
  const ui=fixture({initial:'none'});try{
    await ui.connect();await settle();
    ui.setDocumentHidden(true);
    ui.send({method:'ui/notifications/tool-result',params:toolResult({
      ok:true,preview_unavailable:true,preview_status:'device_offline',device_id:'fixture-device',
    })});
    await settle();
    assert.equal(ui.nodes.get('preview-retry').hidden,false);
    assert.equal(ui.nodes.get('preview-retry').disabled,true);
    assert.equal(ui.tools.length,0);
    ui.setDocumentHidden(false);
    assert.equal(ui.nodes.get('preview-retry').disabled,false,'Retry must be enabled on returning to the tab');
    await ui.click('preview-retry');
    assert.deepEqual(ui.tools.map(call=>[call.name,call.arguments.session_id]),[['rdc_preview_open',SID]]);
    assert.equal(ui.state.availability,null);
  }finally{await ui.cleanup();}
}else if(which==='stale-open'){
  for(const response of ['success','ended','error']){
    const ui=fixture({holdTools:true});try{await ui.connect();await settle();const inflight=ui.refreshSessions(true);await settle();const original=ui.heldTools.shift();ui.send({method:'ui/notifications/tool-result',params:toolResult({ok:true,preview_unavailable:true,preview_status:'device_offline',device_id:'fixture-device'})});await settle();assert.equal(ui.state.availability,'device_offline');assert.equal(ui.timers.size,0);if(response==='success')ui.send({id:original.id,result:toolResult(openData(SID2))});else if(response==='ended')ui.send({id:original.id,result:{isError:true,structuredContent:{ok:false,error:{code:'session_not_found',message:'Synthetic ended session'}},content:[]}});else ui.send({id:original.id,error:{code:-32000,message:'Synthetic stale request failure'}});await inflight;assert.equal(ui.state.availability,'device_offline','An older open cannot clear newer availability');assert.equal(ui.state.sessionId,SID);assert.equal(ui.nodes.get('preview-retry').hidden,false);assert.match(ui.nodes.get('empty-copy').textContent,/No new preview request was queued/);assert.equal(ui.timers.size,0);assert.equal(ui.tools.filter(item=>item.name==='rdc_preview_open').length,1,'Stale ended-session result cannot queue a fallback');ui.setHoldTools(false);await ui.click('preview-retry');assert.equal(ui.tools.filter(item=>item.name==='rdc_preview_open').length,2);assert.equal(ui.state.availability,null);}finally{await ui.cleanup();}
  }
}else if(which==='stale-pending'){
  const ui=fixture({initial:'pending',holdTools:true});try{ui.state.sessionId=SID;await ui.connect();await settle();const inflight=ui.refreshSessions(false);await settle();await ui.runDelay(500);const original=ui.heldTools.shift();assert.equal(original.params.name,'rdc_operation_status');ui.send({method:'ui/notifications/tool-result',params:toolResult({ok:true,preview_unavailable:true,preview_status:'device_offline',device_id:'fixture-device'})});await settle();ui.toolReply(original);await inflight;assert.equal(ui.state.availability,'device_offline');assert.equal(ui.state.pendingOpen?.operation_id,'original-open-operation','A stale status result must retain the original reference for inspection');assert.equal(ui.state.sessionId,SID);assert.equal(ui.nodes.get('preview-retry').hidden,false);assert.equal(ui.timers.size,0);assert.equal(ui.tools.filter(item=>item.name==='rdc_preview_open').length,0);ui.setHoldTools(false);const retry=ui.click('preview-retry');await settle();await ui.runDelay(500);await retry;assert.equal(ui.state.pendingOpen,null);assert.equal(ui.tools.filter(item=>item.name==='rdc_operation_status').length,2);assert.ok(ui.tools.every(item=>item.arguments.operation_id==='original-open-operation'));assert.equal(ui.state.availability,null);}finally{await ui.cleanup();}
}else if(which==='expired-open'){
  for(const shape of ['structured','wrapped','hint']){
    const ui=fixture({initial:'pending',holdTools:true});try{
      await ui.connect();await settle();const recovery=ui.refreshSessions();await settle();await ui.runDelay(500);
      const original=ui.heldTools.shift();assert.equal(original.params.arguments.operation_id,'original-open-operation');expiredReply(ui,original,shape);await settle();
      const fresh=ui.heldTools.shift();assert.equal(fresh?.params.name,'rdc_preview_open','Confirmed expiry must request a fresh read-only open');ui.toolReply(fresh);await recovery;
      assert.equal(ui.state.pendingOpen,null);assert.equal(ui.state.busy,false);assert.equal(ui.nodes.get('preview-retry').hidden,true);assert.doesNotMatch(ui.nodes.get('connection-text').textContent,/Recovering/);
      ui.send({method:'ui/notifications/tool-result',params:pendingResult('original-open-operation')});ui.send({method:'ui/notifications/tool-result',params:refreshRequired('original-open-operation','rdc_preview_open')});await settle();
      assert.equal(ui.state.pendingOpen,null,'Cached host notifications cannot resurrect a retired open');ui.send({method:'ui/notifications/tool-result',params:{...toolResult(openData(SID2)),_meta:{'rdc/operation_id':'original-open-operation'}}});await settle();assert.equal(ui.state.sessionId,SID,'Cached success with gateway metadata cannot replace the fresh view');assert.equal(ui.tools.filter(item=>item.name==='rdc_preview_open').length,1);
    }finally{await ui.cleanup();}
  }
}else if(which==='expired-unknown'){
  for(const variant of ['wrong-id','incomplete','opaque']){
    const ui=fixture({initial:'pending',holdTools:true});try{
      await ui.connect();await settle();const recovery=ui.refreshSessions();await settle();await ui.runDelay(500);const original=ui.heldTools.shift();
      if(variant==='opaque')ui.send({id:original.id,error:{code:-32603,message:'PRIVATE_HOST_DETAIL result_expired completed:true operation_id:original-open-operation'}});
      else expiredReply(ui,original,'wrapped',variant==='wrong-id'?{operation_id:'different-operation'}:{completed:false});
      await recovery;assert.equal(ui.state.pendingOpen?.operation_id,'original-open-operation');assert.equal(ui.state.pendingOpen.halted,true);assert.equal(ui.tools.filter(item=>item.name==='rdc_preview_open').length,0);assert.doesNotMatch(ui.nodes.get('empty-copy').textContent,/PRIVATE_HOST_DETAIL|RuntimeException|TextContent/);
      const manual=ui.refreshSessions(true);await settle();await ui.runDelay(500);const retry=ui.heldTools.shift();assert.equal(retry.params.name,'rdc_operation_status');assert.equal(retry.params.arguments.operation_id,'original-open-operation');ui.toolReply(retry);await manual;assert.equal(ui.state.pendingOpen,null);assert.equal(ui.tools.filter(item=>item.name==='rdc_preview_open').length,0);
    }finally{await ui.cleanup();}
  }
}else if(which==='expired-bounded'){
  const ui=fixture({initial:'pending',holdTools:true});try{
    await ui.connect();await settle();const recovery=ui.refreshSessions();await settle();await ui.runDelay(500);expiredReply(ui,ui.heldTools.shift(),'hint');await settle();
    const fresh=ui.heldTools.shift();assert.equal(fresh?.params.name,'rdc_preview_open');ui.send({id:fresh.id,result:pendingResult('replacement-open')});await settle();await ui.runDelay(500);expiredReply(ui,ui.heldTools.shift(),'wrapped');await recovery;
    assert.equal(ui.state.pendingOpen?.operation_id,'replacement-open');assert.equal(ui.state.pendingOpen.halted,true);assert.equal(ui.state.pendingOpen.terminal,true);assert.equal(ui.tools.filter(item=>item.name==='rdc_preview_open').length,1,'Repeated expiry must stop after one automatic replacement');assert.doesNotMatch(ui.nodes.get('connection-text').textContent,/Recovering/);
    await ui.refreshSessions();assert.equal(ui.tools.filter(item=>item.name==='rdc_preview_open').length,1);
    const manual=ui.refreshSessions(true);await settle();const replacement=ui.heldTools.shift();assert.equal(replacement?.params.name,'rdc_preview_open');ui.toolReply(replacement);await manual;assert.equal(ui.state.pendingOpen,null);assert.equal(ui.tools.filter(item=>item.name==='rdc_preview_open').length,2);
  }finally{await ui.cleanup();}
}else if(which==='expired-frame'){
  const ui=fixture({holdTools:true});try{
    await ui.connect();await settle();const recovery=ui.refreshFrame();await settle();const first=ui.heldTools.shift();ui.send({id:first.id,result:pendingResult('expired-frame')});await settle();await ui.runDelay(500);expiredReply(ui,ui.heldTools.shift(),'hint',{refresh_tool:'rdc_preview_frame'});await settle();
    const fresh=ui.heldTools.shift();assert.equal(fresh?.params.name,'rdc_preview_frame');assert.equal(fresh.params.arguments.session_id,SID);ui.toolReply(fresh);await recovery;assert.equal(ui.state.pendingFrames.size,0);assert.equal(ui.nodes.get('frame').hidden,false);assert.equal(ui.tools.filter(item=>item.name==='rdc_preview_frame').length,2);
  }finally{await ui.cleanup();}
}else if(which==='expired-hidden'){
  const ui=fixture({initial:'pending',holdTools:true});try{
    await ui.connect();await settle();const recovery=ui.refreshSessions();await settle();await ui.runDelay(500);const original=ui.heldTools.shift();ui.hidePreview();expiredReply(ui,original,'wrapped');await recovery;assert.equal(ui.state.pendingOpen?.operation_id,'original-open-operation');assert.equal(ui.tools.filter(item=>item.name==='rdc_preview_open').length,0);
    ui.reopenPreview();const resumed=ui.refreshSessions();await settle();await ui.runDelay(500);const same=ui.heldTools.shift();assert.equal(same.params.arguments.operation_id,'original-open-operation');expiredReply(ui,same,'hint');await settle();ui.toolReply(ui.heldTools.shift());await resumed;assert.equal(ui.state.pendingOpen,null);
  }finally{await ui.cleanup();}
}else if(which==='expired-bootstrap'){
  const ui=fixture({initial:'none',holdTools:true});try{
    await ui.connect();await settle();ui.send({method:'ui/notifications/tool-result',params:refreshRequired('expired-bootstrap','rdc_preview_open')});await settle();const recovery=ui.refreshSessions();await settle();const fresh=ui.heldTools.shift();assert.equal(fresh?.params.name,'rdc_preview_open');ui.toolReply(fresh);await recovery;assert.equal(ui.state.haveOpenResult,true);assert.equal(ui.state.pendingOpen,null);assert.equal(ui.nodes.get('preview-retry').hidden,true);
  }finally{await ui.cleanup();}
}else if(which==='expired-fresh-hidden'){
  const ui=fixture({initial:'pending',holdTools:true});try{
    await ui.connect();await settle();const recovery=ui.refreshSessions();await settle();await ui.runDelay(500);expiredReply(ui,ui.heldTools.shift(),'hint');await settle();const fresh=ui.heldTools.shift();ui.hidePreview();ui.send({id:fresh.id,result:pendingResult('fresh-while-hidden')});await recovery;
    assert.equal(ui.state.pendingOpen?.operation_id,'fresh-while-hidden');assert.equal(ui.tools.filter(item=>item.name==='rdc_preview_open').length,1);assert.equal(ui.nodes.get('panel').hidden,true);
    ui.reopenPreview();const resumed=ui.refreshSessions();await settle();await ui.runDelay(500);const same=ui.heldTools.shift();assert.equal(same.params.arguments.operation_id,'fresh-while-hidden');ui.toolReply(same);await resumed;assert.equal(ui.state.pendingOpen,null);assert.equal(ui.tools.filter(item=>item.name==='rdc_preview_open').length,1);
  }finally{await ui.cleanup();}
}else if(which==='expired-wrong-hint'){
  for(const changes of [{refresh_tool:'rdc_job_start'},{operation_id:'unrelated-operation'}]){
    const ui=fixture({initial:'pending',holdTools:true});try{
      await ui.connect();await settle();const recovery=ui.refreshSessions();await settle();await ui.runDelay(500);expiredReply(ui,ui.heldTools.shift(),'hint',changes);await recovery;
      assert.equal(ui.state.pendingOpen?.operation_id,'original-open-operation');assert.equal(ui.state.pendingOpen.halted,true);assert.equal(ui.tools.filter(item=>item.name==='rdc_preview_open').length,0);
    }finally{await ui.cleanup();}
  }
}else if(which==='ended-wrapped'){
  const ui=fixture({holdTools:true});try{
    await ui.connect();await settle();
    const recovery=ui.refreshSessions(true);await settle();const initial=ui.heldTools.shift();
    ui.send({id:initial.id,result:pendingResult('ended-wrapped')});await settle();await ui.runDelay(500);
    expiredReply(ui,ui.heldTools.shift(),'wrapped',{error:{code:'session_not_found',message:'PRIVATE_HOST_DETAIL ended session'}});
    await recovery;
    assert.equal(ui.state.pendingOpen,null);
    assert.equal(ui.state.sessionId,SID);
    assert.equal(ui.state.selectionLost,true);
    assert.equal(ui.tools.filter(item=>item.name==='rdc_preview_open').length,1);
    assert.equal(ui.tools[0].arguments.session_id,SID);
    assert.doesNotMatch(ui.nodes.get('empty-copy').textContent,/PRIVATE_HOST_DETAIL/);
    assert.equal(ui.timers.size,0);
  }finally{await ui.cleanup();}
}else if(which==='unbound'){
  const ui=fixture({initial:'none',includeInput:false});try{
    await ui.connect();await settle();
    // Legacy global focus and session lists do not establish an explicit source.
    const legacy=openData(SID2);delete legacy.viewer;
    ui.send({method:'ui/notifications/tool-result',params:toolResult(legacy)});await settle();
    assert.equal(ui.state.sessionId,null);
    assert.equal(ui.nodes.get('empty-title').textContent,'No visual source');
    assert.equal(ui.timers.size,0);
    ui.send({method:'ui/notifications/tool-result',params:refreshRequired('unbound-expired','rdc_preview_open')});await settle();
    await ui.refreshSessions();
    assert.equal(ui.state.pendingOpen,null);
    assert.equal(ui.tools.length,0);
  }finally{await ui.cleanup();}
}else if(which==='other-source'){
  const ui=fixture();try{
    await ui.connect();await settle();await ui.refreshFrame();
    assert.equal(ui.nodes.get('frame').hidden,false);
    ui.send({method:'ui/notifications/tool-result',params:toolResult(openData(SID2))});await settle();
    assert.equal(ui.state.sessionId,SID);
    assert.equal(ui.nodes.get('frame').hidden,true);
    assert.equal(ui.timers.size,0);
    assert.ok(ui.tools.every(item=>item.arguments.session_id===SID));
  }finally{await ui.cleanup();}
}else if(which==='missing-observation'){
  for(const wrapped of [false,true]){
    const ui=fixture({holdTools:true});try{
      await ui.connect();await settle();const recovery=ui.refreshFrame();await settle();
      const initial=ui.heldTools.shift(),id='missing-frame';
      ui.send({id:initial.id,result:pendingResult(id)});await settle();await ui.runDelay(500);
      const lookup=ui.heldTools.shift();assert.equal(lookup.params.arguments.operation_id,id);
      const rpc={code:-32002,message:'The operation was not found for this connection.',data:{code:'operation_not_found'}};
      ui.send({id:lookup.id,error:wrapped?{code:-32603,message:JSON.stringify({detail:rpc})}:rpc});await settle();
      const fresh=ui.heldTools.shift();assert.equal(fresh?.params.name,'rdc_preview_frame');
      assert.equal(fresh.params.arguments.session_id,SID);
      ui.send({id:fresh.id,result:frameResult(SID)});await recovery;
      assert.equal(ui.tools.filter(item=>item.name==='rdc_preview_frame').length,2);
      const retired=ui.state.retiredObservations.get(id);
      assert.equal(retired?.reason,'operation_not_found');assert.equal(retired?.tool,'rdc_preview_frame');
      assert.equal(Object.hasOwn(retired,'completed'),false,'Missing identity cannot claim prior work completed');
    }finally{await ui.cleanup();}
  }
}else if(which==='missing-unverified'){
  for(const rpc of [{code:-32603,message:'operation_not_found',data:{code:'operation_not_found'}},{code:-32002,message:'Unknown outcome',data:{code:'operation_unknown'}},{code:-32002,message:'Missing other operation',data:{code:'operation_not_found',operation_id:'different-id'}}]){
    const ui=fixture({holdTools:true});try{
      await ui.connect();await settle();const recovery=ui.refreshFrame();await settle();const initial=ui.heldTools.shift();ui.send({id:initial.id,result:pendingResult('uncertain-frame')});await settle();await ui.runDelay(500);const lookup=ui.heldTools.shift();ui.send({id:lookup.id,error:rpc});await recovery;
      assert.equal(ui.state.pendingFrames.get(SID)?.operation_id,'uncertain-frame');assert.equal(ui.state.pendingFrames.get(SID).halted,true);assert.equal(ui.tools.filter(item=>item.name==='rdc_preview_frame').length,1);assert.equal(ui.state.retiredObservations.size,0);
      const manual=ui.refreshFrame(true);await settle();await ui.runDelay(500);const same=ui.heldTools.shift();assert.equal(same.params.arguments.operation_id,'uncertain-frame');ui.send({id:same.id,result:frameResult(SID)});await manual;assert.equal(ui.tools.filter(item=>item.name==='rdc_preview_frame').length,1);
    }finally{await ui.cleanup();}
  }
}else throw new Error(`Unknown preview contract ${which}`);
console.log(`PASS ${which}: real pinned SDK and production source; synthetic host, no rendering claim`);
