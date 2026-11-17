#!/usr/bin/env node
// Operator-safe managed-session viewer check. Uses an isolated headless Chrome
// context and local synthetic slides, never the owner desktop or active browser.
import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {mkdtemp,readFile,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('../',import.meta.url));
const serverPath=fileURLToPath(new URL('./managed-server.mjs',import.meta.url));
const cliPath=fileURLToPath(new URL('./presentationctl.mjs',import.meta.url));
const chrome='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const ocr=fileURLToPath(new URL('../native/macos/build/stage-ocr',import.meta.url));
const exec=promisify(execFile),delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
let temp=null,server=null,browser=null,socket=null;
try{
 temp=await mkdtemp(join(tmpdir(),'managed-stage-browser-'));
 const env={...process.env,PRESENTATION_AGENT_STATE_DIR:temp};
 server=spawn(process.execPath,[serverPath],{cwd:root,env,stdio:['ignore','pipe','pipe']});
 let state=null;
 for(let i=0;i<90;i++){
   try{state=JSON.parse(await readFile(join(temp,'control.json'),'utf8'));break;}
   catch{await delay(30);}
 }
 if(!state)throw Error('Managed session did not start.');
 const deck=join(temp,'deck.json');
 await writeFile(deck,JSON.stringify({title:'Managed Stage Viewer',theme:'dark',
   slides:[{id:'start',title:'START REHEARSAL',text:'Prepared for live worship'},
           {id:'chorus',title:'SING TOGETHER',text:'Automatic presentation following'}]}));
 async function control(...args){
   const {stdout}=await exec(process.execPath,[cliPath,...args],{env,timeout:2500});
   if(stdout.includes(state.token)||stdout.includes(state.viewerToken))throw Error('Credentials escaped the local control file.');
   return JSON.parse(stdout);
 }
 await control('load','--file',deck);
 await control('start','automatic');
 const viewer=join(temp,'private-stage-view.html');
 await control('viewer-export','--file',viewer);
 const profile=join(temp,'headless-profile');
 browser=spawn(chrome,['--headless=new','--disable-gpu','--disable-background-networking',
  '--no-default-browser-check','--no-first-run','--disable-extensions',
  '--remote-debugging-port=0','--window-size=1280,720',
  '--user-data-dir='+profile,'about:blank'],{stdio:['ignore','ignore','pipe']});
 let browserError='';
 browser.stderr.on('data',data=>{
   if(browserError.length<500)browserError+=String(data).slice(0,80);
 });
 let debugPort=null;
 for(let i=0;i<90;i++){
   try{debugPort=(await readFile(join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0];break;}
   catch{await delay(100);}
 }
 if(!debugPort)throw Error('Isolated Chrome DevTools did not start: '+browserError);
 const list=await (await fetch('http://127.0.0.1:'+debugPort+'/json/list')).json();
 const tab=list.find(item=>item.type==='page');
 if(!tab)throw Error('Headless Chrome page missing.');
 socket=new WebSocket(tab.webSocketDebuggerUrl);
 await Promise.race([new Promise((resolve,reject)=>{
   socket.addEventListener('open',resolve,{once:true});
   socket.addEventListener('error',reject,{once:true});
 }),new Promise((_,reject)=>setTimeout(()=>reject(Error('DevTools connect timeout')),2500))]);
 let serial=0;
 const waiting=new Map();
 socket.addEventListener('message',event=>{
   const message=JSON.parse(String(event.data));
   const entry=waiting.get(message.id);
   if(!entry)return;
   waiting.delete(message.id);
   message.error?entry.reject(Error(message.error.message)):entry.resolve(message.result);
 });
 function rpc(method,params={}){
   return new Promise((resolve,reject)=>{
     const id=++serial;waiting.set(id,{resolve,reject});
     socket.send(JSON.stringify({id,method,params}));
     setTimeout(()=>{
       if(waiting.has(id)){waiting.delete(id);reject(Error('DevTools '+method+' timeout'));}
     },2500).unref();
   });
 }
 await rpc('Page.enable');await rpc('Runtime.enable');
 await rpc('Page.navigate',{url:'file://'+viewer});
 async function active(){
   const result=await rpc('Runtime.evaluate',{expression:
     "({title:document.querySelector('.slide:not([hidden]) h1')?.textContent??null,protocol:location.protocol,connection:document.body?.dataset?.connection??null})",
     returnByValue:true});
   if(result.exceptionDetails)throw Error('Page execution failed.');
   return result.result?.value;
 }
 async function until(expected){
   for(let attempt=0;attempt<80;attempt++){
     const current=await active();
     if(current.title===expected&&current.protocol==='http:'&&current.connection==='connected')return current;
     await delay(80);
   }
   throw Error('Managed viewer did not show '+expected+': '+JSON.stringify(await active()));
 }
 const first=await until('START REHEARSAL');
 const moved=await control('next');
 if(moved.changed!==true)throw Error('Presentation did not advance.');
 const second=await until('SING TOGETHER');
 await delay(450);
 const picture=await rpc('Page.captureScreenshot',{format:'png'});
 const screenshot=new URL('../evidence/managed-viewer-acceptance.png',import.meta.url);
 await writeFile(screenshot,Buffer.from(picture.data,'base64'));
 const {stdout:found}=await exec(ocr,[fileURLToPath(screenshot)],{timeout:3500});
 const recognized=JSON.parse(found);
 if(!recognized.text.replace(/\s+/g,'').includes('SINGTOGETHER'))
   throw Error('Offline OCR did not recognize updated managed slide: '+recognized.text.slice(0,200));
 console.log(JSON.stringify({verified:true,initial:first.title,advanced:second.title,
   bridge:'managed-session-http-and-browser-sse',renderedIn:'isolated headless Chrome',
   ocrRecognized:recognized.text,privateCredentialsInToolOutput:false},null,2));
}catch(error){
 console.error('Managed browser verification failed: '+String(error.message??error));
 process.exitCode=1;
}finally{
 try{socket?.close();}catch{}
 if(browser&&browser.exitCode===null){
   const stopped=new Promise(resolve=>{
     const timeout=setTimeout(()=>{try{browser.kill('SIGKILL');}catch{}},1500);
     browser.once('close',()=>{clearTimeout(timeout);resolve();});
   });
   browser.kill('SIGTERM');
   await stopped;
 }
 if(server&&server.exitCode===null){
   server.kill('SIGTERM');
   await Promise.race([new Promise(resolve=>server.once('close',resolve)),delay(1200)]);
 }
 if(temp)await rm(temp,{recursive:true,force:true,maxRetries:5,retryDelay:100});
}
