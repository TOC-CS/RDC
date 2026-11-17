#!/usr/bin/env node
// Optional owner-only background service. No webcam, microphone, stream,
// native application automation or external-output grants are enabled.
import {access,readFile,writeFile,mkdir,unlink,lstat} from 'node:fs/promises';
import {homedir,platform} from 'node:os';
import {dirname,isAbsolute,join} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';

const run=promisify(execFile);
const label='com.toc.ai-presentation-agent';
const projectRoot=fileURLToPath(new URL('..',import.meta.url));
const nodePath='/opt/homebrew/opt/node@24/bin/node';
const xml=v=>String(v).replace(/[&<>"']/g,c=>({
 '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'
})[c]);
export function renderLaunchAgentPlist({projectRoot,home,nodePath}={}){
 if(![projectRoot,home,nodePath].every(v=>typeof v==='string'&&isAbsolute(v))||
   home==='/'||projectRoot===home||!projectRoot.startsWith(home+'/'))
   throw new Error('LaunchAgent requires absolute source, executable, and safe owner home paths.');
 const stdout=join(home,'Library','Logs','TOC-Presentation-Agent','managed.stdout.log');
 const stderr=join(home,'Library','Logs','TOC-Presentation-Agent','managed.stderr.log');
 const state=join(home,'.local','state','ai-presentation-agent');
 const pairs=Object.entries({
   Label:label,ProgramArguments:[nodePath,join(projectRoot,'scripts','managed-server.mjs')],
   WorkingDirectory:projectRoot,
   EnvironmentVariables:{PRESENTATION_AGENT_STATE_DIR:state,
     PATH:'/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin'},
   StandardOutPath:stdout,StandardErrorPath:stderr
 });
 const field=value=>{
   if(Array.isArray(value))return '<array>'+value.map(x=>'<string>'+xml(x)+'</string>').join('')+'</array>';
   if(value&&typeof value==='object')
     return '<dict>'+Object.entries(value).map(([key,val])=>'<key>'+xml(key)+'</key><string>'+xml(val)+'</string>').join('')+'</dict>';
   return '<string>'+xml(value)+'</string>';
 };
 return '<?xml version="1.0" encoding="UTF-8"?>\n'+
  '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'+
  '<plist version="1.0"><dict>'+
  pairs.map(([key,value])=>'<key>'+xml(key)+'</key>'+field(value)).join('')+
  '<key>ProcessType</key><string>Background</string>'+
  '<key>RunAtLoad</key><true/><key>KeepAlive</key><true/>'+
  '<key>ThrottleInterval</key><integer>30</integer>'+
  '</dict></plist>\n';
}
async function launchctl(args){
 try{return await run('/bin/launchctl',args,{timeout:7000,encoding:'utf8',maxBuffer:12000});}
 catch(error){throw new Error('LaunchAgent operation failed: '+String(error.stderr??error.message).slice(0,280));}
}
async function loaded(domain){
 try{await launchctl(['print',domain+'/'+label]);return true;}
 catch{return false;}
}
async function execute(){
 if(platform()!=='darwin')throw new Error('macOS LaunchAgent requires macOS.');
 const uid=process.getuid(),home=homedir();
 const args=process.argv.slice(2);
 const command=args[0]??'--status';
 if(args.length!==1||!['--install','--status','--uninstall','--render'].includes(command))
   throw new Error('Use --render, --status, --install or --uninstall.');
 const plist=renderLaunchAgentPlist({projectRoot,home,nodePath});
 const path=join(home,'Library','LaunchAgents',label+'.plist');
 const domain='gui/'+uid;
 if(command==='--render'){process.stdout.write(plist);return;}
 if(command==='--status'){
   process.stdout.write(JSON.stringify({label,
     installed:await access(path).then(()=>true,()=>false),
     loaded:await loaded(domain),
     localOnly:true,externalWritesDisarmedByDefault:true,
     inputCaptureOnStartup:false})+'\n');return;
 }
 if(command==='--install'){
   await access(nodePath);
   await access(join(projectRoot,'scripts','managed-server.mjs'));
   await mkdir(dirname(path),{recursive:true});
   await mkdir(join(home,'Library','Logs','TOC-Presentation-Agent'),
     {recursive:true,mode:0o700});
   let created=false;
   try{
     const existing=await readFile(path,'utf8').catch(error=>{
       if(error.code==='ENOENT')return null;throw error;
     });
     if(existing!==null&&existing!==plist)
       throw new Error('An existing Presentation Agent LaunchAgent differs; refusing overwrite.');
     if(existing===null){await writeFile(path,plist,{flag:'wx',mode:0o644});created=true;}
     if(!await loaded(domain))await launchctl(['bootstrap',domain,path]);
     if(!await loaded(domain))throw new Error('Background service was not registered.');
     process.stdout.write(JSON.stringify({installed:true,loaded:true,label,
       localOnly:true,externalWritesDisarmedByDefault:true,
       inputCaptureOnStartup:false})+'\n');
   }catch(error){
     if(created&&!await loaded(domain))await unlink(path).catch(()=>{});
     throw error;
   }
   return;
 }
 if(command==='--uninstall'){
   const st=await lstat(path).catch(error=>{
     if(error.code==='ENOENT')return null;throw error;
   });
   if(st?.isSymbolicLink())throw new Error('Unexpected LaunchAgent symlink; refuse automatic removal.');
   if(await loaded(domain))await launchctl(['bootout',domain+'/'+label]);
   if(st){
     const existing=await readFile(path,'utf8');
     if(existing!==plist)throw new Error('LaunchAgent was modified; refusing deletion.');
     await unlink(path);
   }
   process.stdout.write(JSON.stringify({uninstalled:true,label})+'\n');
 }
}
if(process.argv[1]&&pathToFileURL(process.argv[1]).href===import.meta.url){
 execute().catch(error=>{
   process.stderr.write('Presentation Agent service error: '+String(error.message)+'\n');
   process.exitCode=1;
 });
}
