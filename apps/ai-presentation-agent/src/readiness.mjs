import {access,readdir} from 'node:fs/promises';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {platform as hostPlatform,arch as hostArch} from 'node:os';

const execFileAsync=promisify(execFile);
const SAFE_APP_SPECS=Object.freeze([
 {id:'keynote',label:'Keynote',names:['Keynote.app'],processes:['Keynote']},
 {id:'powerpoint-macos',label:'PowerPoint for macOS',names:['Microsoft PowerPoint.app'],processes:['Microsoft PowerPoint']},
 {id:'obs',label:'OBS Studio',names:['OBS.app'],processes:['OBS','obs']},
 {id:'propresenter',label:'ProPresenter',names:['ProPresenter.app','ProPresenter 7.app','ProPresenter 8.app'],processes:['ProPresenter','ProPresenter 7','ProPresenter 8']}
]);
const cleanProcessName=raw=>String(raw).trim().split('/').at(-1)??'';
async function readProcesses(){
 try{
   const {stdout}=await execFileAsync('/bin/ps',['-axo','comm='],{encoding:'utf8',timeout:1500,maxBuffer:2_000_000});
   return stdout.split('\n').map(cleanProcessName).filter(Boolean);
 }catch{return null;}
}
async function availablePath(path){
 try{await access(path);return true;}catch{return false;}
}
async function installedExecutables(appFolder='/Applications'){
 try{return await readdir(appFolder);}catch{return [];}
}
async function binaryAvailable(binary){
 try{
   const {stdout}=await execFileAsync('/usr/bin/which',[binary],{encoding:'utf8',timeout:800});
   return !!stdout.trim();
 }catch{return false;}
}
export async function presentationReadiness({
 platform=hostPlatform(),arch=hostArch(),
 appFolder='/Applications',
 listApps=()=>installedExecutables(appFolder),
 processes=readProcesses,
 available=availablePath,
 binary=binaryAvailable,
 environment=process.env,
}={}){
 const result={schema:'toc.presentation.readiness/v1',
   platform,architecture:arch,
   inspection:'read-only-no-audio-or-video-capture',
   appReadiness:{},
   inputs:{
     microphone:{osPermission:'unverified',liveCapture:'unverified'},
     camera:{osPermission:'unverified',liveCapture:'unverified'},
     mainAiVoice:{sessionBridge:'unverified'},
     bandmates:{nativeSongEventBridge:'unverified'}
   },
   physicalProjection:'unverified',
   externalOutputsArmed:false,
   reminders:[
     'Installed apps are only discovered, not opened or controlled.',
     'Running is separate from receiving live output; a rehearsal with readback is required.',
     'No camera or microphone data was requested by this inspection.'
   ]
 };
 if(platform==='darwin'){
   const [entries,commands]=await Promise.all([listApps(),processes()]);
   const names=new Set(entries);
   const runningNames=commands===null?null:new Set(commands);
   for(const spec of SAFE_APP_SPECS){
     const installed=spec.names.some(name=>names.has(name));
     const running=runningNames===null?null:spec.processes.some(name=>runningNames.has(name));
     result.appReadiness[spec.id]={
       installed,running,liveControlQualified:false,reason:!installed?'not_installed':running===false?'not_running':'live_output_not_verified'};
   }
   const [ffmpeg,whisper,say,osascript]=await Promise.all([
     binary('ffmpeg'),binary('whisper-cli'),binary('say'),available('/usr/bin/osascript')
   ]);
   result.localTools={ffmpeg,whisperCli:whisper,macSpeech:say,appleScript:osascript};
 }else if(platform==='win32'){
   result.appReadiness['powerpoint-windows']={
     installed:null,running:null,liveControlQualified:false,
     reason:'Windows host COM slideshow query required'};
   result.localTools={};
 }else{
   result.appReadiness['generic-linux']={
     installed:null,running:null,liveControlQualified:false,
     reason:'application-specific connector or authorized RDC adapter required'};
   result.localTools={};
 }
 if(typeof environment.PRESENTATION_WHISPER_MODEL==='string'){
   const path=environment.PRESENTATION_WHISPER_MODEL;
   result.localSpeechModel={configured:true,readable:!!(path&&path.startsWith('/')&&await available(path)),
     liveInferenceQualified:false};
 }else result.localSpeechModel={configured:false,readable:false,liveInferenceQualified:false};
 return result;
}
