// Execute production UI functions with a minimal DOM/transport fixture.
// These checks cover behavior and dispatch, not browser layout or host rendering.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const mobileId = 'mobile-87654321-4321-4321-4321-cba987654321';
const mobile = {session_id:mobileId,kind:'mobile',backend:'appium',platform:'Android',profile:'fixture-phone',
  title:'fixture-phone',width:390,height:844,input_notice:'Input is shared with the configured mobile device.'};
const browser = {session_id:'12345678-1234-1234-1234-123456789abc',browser:'chromium',width:800,height:600,url:'https://example.test/'};
const controls = [
  {handle:'1',tag:'android.widget.EditText',type:'text',role:'textbox',name:'Text field',editable:true,can_fill:true,can_tap:true,value:'[redacted]'},
  {handle:'2',tag:'android.widget.EditText',type:'password',role:'textbox',name:'Secure field',secure:true,sensitive:true,editable:true,can_fill:false,can_tap:false,value:'[redacted]'},
  {handle:'3',tag:'android.widget.Button',type:'button',name:'Continue',can_tap:true,can_fill:false},
];
const observation = {...mobile,observation_id:'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',controls,text:'Synthetic device'};
const ownerStatus = {ok:true,device_id:'fixture-worker',paused:false,settings:{desktop_mode:'disabled'},jobs:[],approvals:[],
  adapters:{browser:{backend:'playwright',available:true,sessions:[browser]},desktop:{mode:'disabled'},
    mobile:{available:true,profiles:[{profile:'fixture-phone',platform:'Android',automation:'UiAutomator2'}],sessions:[mobile]}}};

class Element {
  constructor(tag='div') {this.tagName=tag.toUpperCase();this.children=[];this.style={};this.dataset={};this.value='';this.hidden=false;this.disabled=false;this.checked=false;this.listeners={};this.attributes={};this._text='';this.clientWidth=800;this.clientHeight=600;
    this.classList={add(){},remove(){},toggle(){}};}
  set textContent(value){this._text=String(value??'');this.children=[];}
  get textContent(){return this._text+this.children.map(child=>typeof child==='string'?child:child.textContent).join('');}
  append(...children){this.children.push(...children);}
  prepend(...children){this.children.unshift(...children);}
  replaceChildren(...children){this._text='';this.children=children;}
  addEventListener(name,fn){(this.listeners[name]??=[]).push(fn);}
  setAttribute(name,value){this.attributes[name]=String(value);}
  removeAttribute(name){delete this.attributes[name];delete this[name];}
  getAttribute(name){return this.attributes[name]??null;}
  querySelectorAll(tag){return descendants(this).filter(node=>node.tagName===tag.toUpperCase());}
  reset(){}
  focus(){}
  close(){this.open=false;}
  showModal(){this.open=true;}
}
function descendants(node){return node.children.filter(child=>typeof child!=='string').flatMap(child=>[child,...descendants(child)]);}
function environment(html){
  const nodes=new Map();
  for(const match of html.matchAll(/<([a-z][a-z0-9]*)\b[^>]*\bid="([^"]+)"[^>]*>/g))nodes.set(match[2],new Element(match[1]));
  const document={getElementById:id=>nodes.get(id)||null,querySelectorAll:()=>[],createElement:tag=>new Element(tag),
    createTextNode:text=>({textContent:String(text),children:[]}),addEventListener(){},hidden:false,activeElement:null,
    documentElement:{clientWidth:800,dataset:{}}};
  const globals={document,window:{addEventListener(){},innerHeight:800,innerWidth:1000},URL,Map,Set,Date,Number,Promise,AbortController,
    crypto:{randomUUID:()=> 'fixture-id'},performance:{now:()=>0},setTimeout:()=>1,clearTimeout(){},console};
  return {nodes,globals};
}
async function trigger(element,name){assert.ok(element,`Missing ${name} control`);for(const fn of element.listeners[name]||[])await fn({target:element,preventDefault(){}});await new Promise(resolve=>setImmediate(resolve));}
function ownerFixture(captureError=null){
  const base=path.join(root,'rdc/web'),{nodes,globals}=environment(fs.readFileSync(path.join(base,'index.html'),'utf8'));
  const calls=[];
  globals.fetch=async (url,options)=>{
    const body=options.body?JSON.parse(options.body):undefined;calls.push({url,body});
    if(url.startsWith('/api/preview')&&captureError)return {ok:false,status:409,json:async()=>({ok:false,error:{code:captureError,message:'Synthetic capture refusal'}})};
    const data=url==='/api/status'?ownerStatus:body?.name?.endsWith('_observe')?observation:body?.name?.endsWith('_start')?mobile:{ok:true};
    return {ok:true,status:200,json:async()=>data};
  };
  const context=vm.createContext(globals);
  const source=fs.readFileSync(path.join(base,'app.js'),'utf8').replace(/\(\(\) => \{/,'').replace(/\}\)\(\);\s*$/,'');
  vm.runInContext(source+'\nglobalThis.ui={state,renderStatus,selectSession,renderObservation,tick,disconnect,renderCredentialAliases};',context);
  context.ui.state.token='synthetic-owner-token';context.ui.renderStatus(ownerStatus);context.ui.selectSession(mobileId);
  return {...context.ui,nodes,calls,context};
}
function embeddedFixture(captureError='screenshot_redaction_required'){
  const base=path.join(root,'rdc/embedded/src'),{nodes,globals}=environment(fs.readFileSync(path.join(base,'index.html'),'utf8'));
  const calls=[];
  globals.App=class {getHostCapabilities(){return {};} getHostContext(){return {};} async callServerTool(request){calls.push(request);return {isError:true,structuredContent:{ok:false,error:{code:captureError,message:'Synthetic capture refusal'}},content:[]};}};
  globals.PostMessageTransport=class {};
  const context=vm.createContext(globals);
  const source=fs.readFileSync(path.join(base,'app.js'),'utf8').replace(/^import .*?;\r?\n/,'').replace(/\nconnect\(\);\s*$/,'\n');
  vm.runInContext(source+'\nglobalThis.ui={state,acceptOpen,refreshFrame};',context);
  Object.assign(context.ui.state,{connected:true,bridgeReady:true});
  context.ui.acceptOpen({device_id:'fixture-worker',session_id:mobileId,sessions:[browser,mobile],active_jobs:1,pending_approvals:0});
  return {...context.ui,nodes,calls};
}

const which=process.argv[2];
if(which==='owner-credential-busy'){
  const ui=ownerFixture();
  const alias={credential_id:'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',label:'Synthetic login',origins:['https://example.test']};
  const request={id:'bbbbbbbb-cccc-dddd-eeee-ffffffffffff',credential_id:alias.credential_id,label:alias.label,origin:'https://example.test',status:'pending'};
  const status={...ownerStatus,credentials:{aliases:[alias],requests:[request],grants:[{id:'fixture-grant',credential_id:alias.credential_id,origin:'https://example.test'}]}};
  ui.renderStatus(status);
  assert.equal(ui.nodes.get('credential-dialog').open,true);
  const credentialButtons=()=>[...ui.nodes.get('credential-aliases').querySelectorAll('button'),
    ...ui.nodes.get('credential-grants').querySelectorAll('button'),
    ...['credential-once','credential-always','credential-deny'].map(id=>ui.nodes.get(id))];
  const updatedAlias={...alias,label:'Updated synthetic login'};
  const decidedStatus={...status,credentials:{...status.credentials,aliases:[updatedAlias],requests:[]}};
  let releaseRefresh,refreshStarted,holdRefresh=true,removeCalls=0,removed=false;
  const refreshPending=new Promise(resolve=>{refreshStarted=resolve;});
  const response=(data,ok=true)=>({ok,status:ok?200:503,json:async()=>data});
  ui.context.fetch=async (url,options)=>{
    const body=options.body?JSON.parse(options.body):undefined;ui.calls.push({url,body});
    if(url==='/api/credentials/decision'){
      assert.deepEqual(body,{request_id:request.id,decision:'once'});
      return response({ok:true});
    }
    if(url==='/api/status'){
      if(holdRefresh){holdRefresh=false;return new Promise(resolve=>{releaseRefresh=()=>resolve(response(decidedStatus));refreshStarted();});}
      return response({...decidedStatus,credentials:{...decidedStatus.credentials,aliases:removed?[]:[updatedAlias]}});
    }
    if(url==='/api/credentials/remove'){
      assert.deepEqual(body,{credential_id:alias.credential_id});removeCalls++;
      if(removeCalls===1)return response({ok:false,error:{code:'credential_removal_incomplete',message:'Synthetic cleanup failure. Retry removal.'}},false);
      removed=true;return response({ok:true});
    }
    assert.fail(`Unexpected credential fixture request: ${url}`);
  };
  const finishingAction=ui.nodes.get('credential-once').listeners.click[0]();
  await refreshPending;
  assert.equal(ui.nodes.get('credential-dialog').open,false,'Decision dialog closes while its status refresh remains pending');
  assert.ok(credentialButtons().every(button=>button.disabled),'Credential mutations must wait while an owner action is finishing');
  ui.renderCredentialAliases([updatedAlias]);
  assert.ok(ui.nodes.get('credential-aliases').querySelectorAll('button').every(button=>button.disabled),'Direct alias rendering must preserve busy state before another control update');
  ui.renderStatus(decidedStatus);
  assert.ok(credentialButtons().every(button=>button.disabled),'Status refresh must keep replacement controls disabled while busy');
  assert.equal(removeCalls,0);
  releaseRefresh();await finishingAction;
  assert.ok(credentialButtons().every(button=>!button.disabled),'Credential controls must become available after the action finishes');
  await trigger(ui.nodes.get('credential-aliases').querySelectorAll('button')[0],'click');
  assert.equal(removeCalls,1,'An available removal click dispatches once; a failed removal is never retried automatically');
  const retry=ui.nodes.get('credential-aliases').querySelectorAll('button')[0];
  assert.equal(retry.textContent,'Retry removal');assert.equal(retry.disabled,false);
  assert.equal(retry.getAttribute('aria-label'),'Retry removing Updated synthetic login mapping');
  assert.equal(ui.state.failedCredentialRemovals.size,1);
  await trigger(retry,'click');
  assert.equal(removeCalls,2,'Only an explicit retry dispatches the second removal');
  assert.equal(ui.state.failedCredentialRemovals.size,0);
  assert.equal(ui.nodes.get('credential-aliases').textContent,'No saved credential mappings.');
  ui.disconnect();
  ui.renderCredentialAliases([alias]);
  assert.ok(credentialButtons().every(button=>button.disabled),'Disconnected credential controls must stay unavailable');
}else if(which==='owner-profile'){
  const ui=ownerFixture();
  const profile=ui.nodes.get('mobile-profile');assert.ok(profile,'Configured mobile profile selector must exist');
  assert.match(profile.textContent,/Android.*fixture-phone/);
  assert.equal(ui.nodes.get('navigate-form').hidden,true);
  assert.equal(ui.nodes.get('keys-form').hidden,true);
  assert.equal(ui.nodes.get('takeover').disabled,true);
  assert.match(ui.nodes.get('input-note').textContent,/shared/i);
  profile.value='fixture-phone';await trigger(ui.nodes.get('mobile-start-form'),'submit');
  assert.ok(ui.calls.some(call=>call.body?.name==='rdc_mobile_start'&&JSON.stringify(call.body.arguments)==='{"profile":"fixture-phone"}'));
}else if(which==='owner-controls'){
  const ui=ownerFixture();ui.state.observation=observation;ui.renderObservation(observation);
  const nodes=descendants(ui.nodes.get('observation'));
  assert.equal(nodes.filter(node=>node.tagName==='SELECT').length,0,'Native controls must not offer saved browser credentials');
  const forms=nodes.filter(node=>node.tagName==='FORM');assert.equal(forms.length,1,'Only the ordinary editable field may have a fill form');
  const input=descendants(forms[0]).find(node=>node.tagName==='INPUT');assert.equal(input.value,'','Redaction marker must not become input text');
  input.value='Synthetic entry';await trigger(forms[0],'submit');
  assert.ok(ui.calls.some(call=>call.body?.name==='rdc_mobile_fill'&&call.body.arguments.text==='Synthetic entry'&&call.body.arguments.session_id===mobileId));
  assert.equal(ui.calls.filter(call=>call.body?.name==='rdc_browser_fill'||call.body?.name==='rdc_credentials_request').length,0);
}else if(which==='owner-privacy'){
  const ui=ownerFixture('screenshot_redaction_required');await ui.tick();
  assert.equal(ui.nodes.get('connection-status').textContent,'Connected');
  assert.equal(ui.nodes.get('preview').hidden,true);
  assert.match(ui.nodes.get('preview-state').textContent,/privacy/i);
  assert.equal(ui.calls.filter(call=>call.body?.name?.endsWith('_close')||call.body?.name?.endsWith('_start')).length,0);
}else if(which==='owner-capture-failed'){
  const ui=ownerFixture('screenshot_failed');ui.nodes.get('preview').hidden=false;ui.nodes.get('preview').src='synthetic-old-image';await ui.tick();
  assert.equal(ui.nodes.get('connection-status').textContent,'Connected');
  assert.equal(ui.nodes.get('preview').hidden,true);
  assert.equal(ui.nodes.get('preview').src,undefined);
  assert.match(ui.nodes.get('preview-state').textContent,/unavailable/i);
}else if(which==='owner-ended'){
  const ui=ownerFixture('mobile_session_gone');await ui.tick();await ui.tick();
  assert.equal(ui.nodes.get('connection-status').textContent,'Connected');
  assert.equal(ui.calls.filter(call=>call.url.startsWith('/api/preview')).length,1,'An ended native driver must not be polled again automatically');
  assert.match(ui.nodes.get('preview-detail').textContent,/close.*session/i);
  assert.equal(ui.nodes.get('close-session-button').disabled,false);
  assert.equal(ui.nodes.get('observe-button').disabled,true);
}else if(which==='owner-actions'){
  const ui=ownerFixture();ui.state.observation=observation;ui.renderObservation(observation);
  await trigger(ui.nodes.get('mobile-swipe-up'),'click');
  const swipe=ui.calls.find(call=>call.body?.name==='rdc_mobile_swipe');assert.ok(swipe);
  assert.deepEqual(swipe.body.arguments,{session_id:mobileId,observation_id:observation.observation_id,start_x:195,start_y:633,end_x:195,end_y:211,duration_ms:500});
  const tap=descendants(ui.nodes.get('observation')).find(node=>node.tagName==='BUTTON'&&node.textContent==='Continue');
  await trigger(tap,'click');
  assert.ok(ui.calls.some(call=>call.body?.name==='rdc_mobile_tap'&&call.body.arguments.handle==='3'&&call.body.arguments.session_id===mobileId));
  await trigger(ui.nodes.get('close-session-button'),'click');
  assert.ok(ui.calls.some(call=>call.body?.name==='rdc_mobile_close'&&call.body.arguments.session_id===mobileId));
  assert.equal(ui.calls.filter(call=>call.body?.name?.startsWith('rdc_browser_')).length,0);
}else if(which==='owner-disabled'){
  const ui=ownerFixture(),configured=structuredClone(ownerStatus);
  configured.adapters.mobile.sessions[0].setup_status='creation_unknown';ui.renderStatus(configured);
  assert.equal(ui.nodes.get('observe-button').disabled,true);
  assert.equal(ui.nodes.get('close-session-button').disabled,true);
  assert.match(ui.nodes.get('takeover-help').textContent,/inspect Appium/i);
  configured.adapters.mobile.sessions[0].setup_status='cleanup_required';ui.renderStatus(configured);
  assert.equal(ui.nodes.get('observe-button').disabled,true);
  assert.equal(ui.nodes.get('close-session-button').disabled,false);
  configured.adapters.mobile={available:false,profiles:[],sessions:[]};ui.renderStatus(configured);
  assert.equal(ui.nodes.get('mobile-start-button').disabled,true);
  assert.equal(ui.nodes.get('keys-form').hidden,false);
  ui.disconnect();
  assert.equal(ui.nodes.get('input-mode').textContent,'Awaiting worker');
  assert.equal(ui.nodes.get('mobile-profile').disabled,true);
}else if(which==='embedded-mobile'){
  const ui=embeddedFixture();
  assert.match(ui.nodes.get('session').textContent,/Android.*fixture-phone/);
  assert.match(ui.nodes.get('page-address').textContent,/Android.*fixture-phone/);
  assert.match(ui.nodes.get('work-state').textContent,/shared/i);
  assert.equal(ui.state.sessionId,mobileId);
  ui.acceptOpen({device_id:'fixture-worker',session_id:browser.session_id,sessions:[browser,mobile]},true);
  assert.equal(ui.state.sessionId,mobileId);
}else if(which==='embedded-privacy'){
  const ui=embeddedFixture();await ui.refreshFrame(true);
  assert.match(ui.nodes.get('connection-text').textContent,/privacy/i);
  assert.equal(ui.nodes.get('frame').hidden,true);
  assert.equal(ui.state.sessionId,mobileId);
  assert.equal(ui.state.activeJobs,1);
  assert.deepEqual(ui.calls.map(call=>call.name),['rdc_preview_frame']);
}else if(which==='embedded-capture-failed'){
  const ui=embeddedFixture('screenshot_failed');ui.nodes.get('frame').hidden=false;ui.nodes.get('frame').src='synthetic-old-image';await ui.refreshFrame(true);
  assert.match(ui.nodes.get('connection-text').textContent,/unavailable/i);
  assert.equal(ui.nodes.get('frame').hidden,true);
  assert.equal(ui.nodes.get('frame').src,undefined);
  assert.equal(ui.state.sessionId,mobileId);
  await ui.refreshFrame(true);
  assert.equal(ui.calls.length,2,'A recoverable capture failure still permits an explicit read-only retry');
}else if(which==='embedded-uncertain-creation'){
  const ui=embeddedFixture('mobile_cleanup_required');
  ui.acceptOpen({device_id:'fixture-worker',session_id:browser.session_id,
    sessions:[browser,{...mobile,setup_status:'creation_unknown'}]});
  assert.equal(ui.state.sessionId,browser.session_id,'Begin with the normal session selected');
  ui.nodes.get('frame').hidden=false;ui.nodes.get('frame').src='synthetic-old-image';
  const selector=ui.nodes.get('session');selector.value=mobileId;await trigger(selector,'change');
  const selectionGuidance=ui.nodes.get('empty-copy').textContent;
  await ui.refreshFrame(false);
  await trigger(ui.nodes.get('refresh'),'click');
  assert.equal(ui.calls.length,0,'Neither selecting an uncertain session nor Refresh may dispatch a frame');
  assert.match(selectionGuidance,/inspect Appium/i,'Selection must immediately explain the uncertain creation state');
  assert.match(ui.nodes.get('empty-copy').textContent,/inspect Appium/i,'Refresh must retain the inspection guidance');
  assert.equal(ui.state.sessionId,mobileId,'Retain the exact uncertain record for owner recovery');
  assert.equal(ui.nodes.get('frame').hidden,true);
  assert.equal(ui.nodes.get('frame').src,undefined);
  ui.acceptOpen({device_id:'fixture-worker',session_id:mobileId,
    sessions:[browser,{...mobile,setup_status:'cleanup_required'}]});
  await ui.refreshFrame(true);
  assert.equal(ui.calls.length,0,'Current cleanup metadata also prohibits frame dispatch');
  assert.match(ui.nodes.get('empty-copy').textContent,/close this exact session/i,'Current metadata takes precedence over an older blocked-frame label');
}else if(which==='embedded-ended'){
  const ui=embeddedFixture('mobile_session_gone');await ui.refreshFrame(true);await ui.refreshFrame(false);
  assert.match(ui.nodes.get('empty-copy').textContent,/owner panel/i);
  assert.equal(ui.nodes.get('frame').hidden,true);
  assert.equal(ui.state.sessionId,mobileId,'Retain the exact record identity for owner cleanup');
  assert.equal(ui.calls.length,1,'An ended native driver must not be polled again automatically');
  await ui.refreshFrame(true);
  assert.equal(ui.calls.length,2,'An explicit read-only retry remains available');
}else throw new Error(`Unknown contract ${which}`);
console.log(`PASS ${which}`);
