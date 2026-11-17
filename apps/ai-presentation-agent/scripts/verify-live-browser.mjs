#!/usr/bin/env node
// Isolated headless browser verification. The real desktop is untouched.
import {createHttpServer} from '../src/http.mjs';
import {createMcpHandler} from '../src/mcp.mjs';
import {spawn} from 'node:child_process';
import {mkdtemp,readFile,rm,writeFile,mkdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
const viewerToken='headless-test-view-only-token-v1',token='headless-test-control-token-v1';
const chrome='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const viewport=process.argv.includes('--tablet')?
 {kind:'tablet',width:1024,height:768,scale:2}:
 process.argv.includes('--mobile-landscape')?
 {kind:'phone-landscape',width:844,height:390,scale:2}:
 process.argv.includes('--mobile')?
 {kind:'phone-portrait',width:390,height:844,scale:2}:null;
const handler=createMcpHandler();
const bridge=async(name,args={})=>{
 const result=await handler({jsonrpc:'2.0',id:Date.now(),method:'tools/call',params:{name,arguments:args}});
 if(result?.result?.isError)throw new Error(result.result.content?.[0]?.text??'MCP failed');
 return result.result.structuredContent;
};
let tmp=null,server=null,chromeProcess=null,socket=null;
try{
 await bridge('presentation_load',{deck:{title:'Live Presentation Verification',theme:'dark',
   slides:[{id:'first',title:'Browser Start',text:'The first slide'},
           {id:'second',title:'Browser Updated',text:'The presentation operator advanced this slide'}]}});
 await bridge('presentation_start',{mode:'automatic'});
 server=createHttpServer({handler,token,viewerToken});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const base='http://127.0.0.1:'+server.address().port;
 tmp=await mkdtemp(join(tmpdir(),'ai-present-browser-'));
 const profile=join(tmp,'chrome-profile');
 chromeProcess=spawn(chrome,['--headless=new','--disable-gpu','--no-first-run',
  '--no-default-browser-check','--disable-background-networking','--disable-extensions',
  '--remote-debugging-port=0','--window-size=1280,720','--user-data-dir='+profile,'about:blank'],
  {stdio:['ignore','ignore','pipe']});
 let chromeError='';
 chromeProcess.stderr.on('data',x=>{if(chromeError.length<500)chromeError+=String(x).slice(0,120);});
 let devtools=null;
 for(let i=0;i<70;i++){
   try{devtools=(await readFile(join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0];break;}
   catch{await delay(100);}
 }
 if(!devtools)throw new Error('Headless Chrome CDP unavailable: '+chromeError.slice(0,300));
 const targets=await (await fetch('http://127.0.0.1:'+devtools+'/json/list')).json();
 const tab=targets.find(x=>x.type==='page');
 if(!tab)throw new Error('Headless Chrome page target missing.');
 socket=new WebSocket(tab.webSocketDebuggerUrl);
 await Promise.race([new Promise((resolve,reject)=>{
  socket.addEventListener('open',resolve,{once:true});
  socket.addEventListener('error',reject,{once:true});
 }),new Promise((_,reject)=>setTimeout(()=>reject(new Error('CDP connection timed out.')),3500))]);
 const pending=new Map();let serial=0;
 socket.addEventListener('message',event=>{
   const msg=JSON.parse(String(event.data));
   if(msg.id&&pending.has(msg.id)){
     const {resolve,reject}=pending.get(msg.id);pending.delete(msg.id);
     return msg.error?reject(new Error(msg.error.message)):resolve(msg.result);
   }
 });
 const rpc=(method,params={})=>new Promise((resolve,reject)=>{
   const id=++serial;pending.set(id,{resolve,reject});
   socket.send(JSON.stringify({id,method,params}));
   setTimeout(()=>{if(pending.has(id)){pending.delete(id);reject(new Error('CDP '+method+' timed out.'));}},2500).unref();
 });
 await rpc('Page.enable');await rpc('Runtime.enable');
 if(viewport)await rpc('Emulation.setDeviceMetricsOverride',{
   width:viewport.width,height:viewport.height,
   deviceScaleFactor:viewport.scale,mobile:true,
   screenWidth:viewport.width,screenHeight:viewport.height
 });
 const url=base+'/v1/viewer?key='+encodeURIComponent(viewerToken);
 await rpc('Page.navigate',{url});
 const evaluate=async expression=>{
   const result=await rpc('Runtime.evaluate',{expression,returnByValue:true});
   if(result.exceptionDetails)throw new Error(result.exceptionDetails.text??'Page JavaScript error.');
   return result.result?.value;
 };
 const current=()=>evaluate("({active:[...document.querySelectorAll('.slide')].findIndex(s=>!s.hidden),name:document.querySelector('.slide:not([hidden]) h1')?.textContent,connection:document.body?.dataset?.connection,status:document.getElementById('session-status')?.textContent,outputFaulted:document.body?.dataset?.outputFaulted})");
 const waitFor=async check=>{
   for(let i=0;i<45;i++){const value=await current();if(check(value))return value;await delay(80);}
   throw new Error('Browser failed to reflect director state: '+JSON.stringify(await current()));
 };
 const initial=await waitFor(v=>v.active===0&&v.connection==='connected'&&v.status==='LIVE'&&v.outputFaulted==='false');
 const locked=await evaluate("({previous:document.getElementById('prev')?.hidden,next:document.getElementById('next')?.hidden})");
 if(!locked.previous||!locked.next)throw new Error('Connected projection viewer still exposes local navigation controls.');
 await rpc('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowRight',code:'ArrowRight',
   windowsVirtualKeyCode:39,nativeVirtualKeyCode:124});
 await rpc('Input.dispatchKeyEvent',{type:'keyUp',key:'ArrowRight',code:'ArrowRight',
   windowsVirtualKeyCode:39,nativeVirtualKeyCode:124});
 await evaluate("document.getElementById('next').click();window.postMessage({type:'presentation.goto',index:1},location.origin)");
 await delay(100);
 const afterLocalInputs=await current();
 if(afterLocalInputs.active!==0)throw new Error('Local browser controls desynchronized the projected slide.');
 const update=await bridge('presentation_command',{action:'next'});
 if(!update.changed)throw new Error('Director did not advance the cue.');
 const final=await waitFor(v=>v.active===1&&v.name==='Browser Updated'&&v.status==='LIVE'&&v.outputFaulted==='false');
 if(viewport){
   const sizing=await evaluate("({width:innerWidth,visualWidth:visualViewport.width,scrollWidth:document.documentElement.scrollWidth,viewportHeight:innerHeight})");
   if(sizing.width!==viewport.width||Math.abs(sizing.visualWidth-viewport.width)>2||
      sizing.scrollWidth>viewport.width+2||sizing.viewportHeight<viewport.height-2)
     throw new Error('Mobile browser slide layout overflow: '+JSON.stringify(sizing));
 }
 const picture=await rpc('Page.captureScreenshot',{format:'png'});
 const screenshotNames={
   'phone-portrait':'headless-live-viewer-mobile.png',
   'phone-landscape':'headless-live-viewer-landscape.png',
   tablet:'headless-live-viewer-tablet.png'
 };
 const out=fileURLToPath(new URL('../evidence/'+(viewport?screenshotNames[viewport.kind]:'headless-live-viewer-updated.png'),import.meta.url));
 await mkdir(dirname(out),{recursive:true});
 await writeFile(out,Buffer.from(picture.data,'base64'));
 await bridge('presentation_stop');
 await bridge('presentation_unload');
 const cleared=await waitFor(v=>v.active===-1&&v.status==='PRESENTATION CLEARED');
 const remainingContent=await evaluate("document.querySelector('main')?.textContent??''");
 if(remainingContent)throw new Error('Private slide content remained in the live viewer DOM after unload.');
 console.log(JSON.stringify({ok:true,viewport:viewport?viewport.kind+'-'+viewport.width+'x'+viewport.height:'desktop-1280x720',initial,localInputsIgnored:true,afterLocalInputs,final,
   cleared:{status:cleared.status,active:cleared.active,privateSlideTextRemoved:true},screenshot:out},null,2));
}catch(error){console.error('Live browser acceptance failed: '+String(error.stack??error));process.exitCode=1;}
finally{
 try{socket?.close();}catch{}
 if(chromeProcess&&chromeProcess.exitCode===null){
   const exited=new Promise(resolve=>{
     const timeout=setTimeout(()=>{try{chromeProcess.kill('SIGKILL');}catch{}},1600);
     chromeProcess.once('close',()=>{clearTimeout(timeout);resolve();});
   });
   try{chromeProcess.kill('SIGTERM');}catch{}
   await exited;
 }
 if(server){server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
 if(tmp)await rm(tmp,{recursive:true,force:true,maxRetries:10,retryDelay:120});
}
