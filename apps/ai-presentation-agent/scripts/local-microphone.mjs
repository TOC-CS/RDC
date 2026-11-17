#!/usr/bin/env node
// Optional operator-started, entirely local microphone listener.
// ffmpeg AVFoundation captures PCM in memory. Each temporary WAV segment is
// transcribed with a user-supplied local Whisper.cpp model then deleted.
// Public music/stream output is never changed by this capture script.
import {spawn} from 'node:child_process';
import {randomUUID} from 'node:crypto';
import {mkdtemp,writeFile,unlink,rm,access} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {PcmWindowQueue,encodePcm16Wav} from '../src/audio-stream.mjs';
import {PcmSlidingWindowQueue,LocalVoiceCommandGate} from '../src/sliding-audio.mjs';
import {findCueMatch} from '../src/local-observer.mjs';
import {interpretVoice,transcribeLocalWav} from '../src/voice.mjs';
import {listMacSpeechOutputs,verifyPrivateSpeechOutput,speakMacPrivate} from '../src/private-talkback.mjs';

const argv=process.argv.slice(2);
if(argv.includes('--list-outputs')){
 const devices=await listMacSpeechOutputs();
 process.stdout.write(JSON.stringify({captureStarted:false,speechPlayed:false,
   outputs:devices},null,2)+'\n');
 process.exit(0);
}
if(argv.includes('--help')||argv.includes('-h')){
 process.stdout.write('Usage: PRESENTATION_API_TOKEN=<private token> node scripts/local-microphone.mjs --device AUDIO_DEVICE_NUMBER --model ABSOLUTE_WHISPER_MODEL_PATH [--commands] [--speak --output-device DEVICE_ID --confirm-private-monitor]\n');
 process.stdout.write('Starts a permitted local AVFoundation microphone. Never captures without explicitly configured device/model/API token.\n');
 process.exit(0);
}
const token=process.env.PRESENTATION_API_TOKEN??'';
if(Buffer.byteLength(token)<16){
 process.stderr.write('PRESENTATION_API_TOKEN must be configured before local microphone capture.\n');
 process.exit(2);
}
const option=name=>{
 const i=argv.indexOf(name);return i>=0&&i+1<argv.length?argv[i+1]:null;
};
const audioId=option('--device'),modelPath=option('--model');
if(!audioId||!/^(0|[1-9][0-9]?)$/.test(audioId)||!modelPath||!modelPath.startsWith('/')){
 process.stderr.write('Explicit audio --device and absolute --model path required.\n');
 process.exit(2);
}
if(process.platform!=='darwin')throw new Error('Local microphone adapter requires macOS AVFoundation.');
await access(modelPath);
const port=Number(process.env.PRESENTATION_API_PORT??8789);
if(!Number.isInteger(port)||port<1024||port>65535)throw new Error('Invalid local API port.');
const base='http://127.0.0.1:'+port;
const speechEnabled=argv.includes('--commands'),speak=argv.includes('--speak');
const rawOutput=option('--output-device');
let privateOutput=null;
if(speak){
 if(!speechEnabled||!rawOutput||!/^\d{1,6}$/.test(rawOutput)||
   !argv.includes('--confirm-private-monitor')){
   process.stderr.write('Local speech requires --commands, an explicit --output-device ID and --confirm-private-monitor.\n');
   process.exit(2);
 }
 const deviceId=Number(rawOutput);
 const availableOutputs=await listMacSpeechOutputs();
 verifyPrivateSpeechOutput({deviceId,confirmed:true,availableOutputs});
 privateOutput={deviceId,availableOutputs};
}
const sessionPrefix='mic-'+randomUUID().slice(0,8)+'-';
async function call(path,data=null){
 const response=await fetch(base+path,{
   method:data?'POST':'GET',
   headers:{Authorization:'Bearer '+token,...(data?{'Content-Type':'application/json'}:{})},
   ...(data?{body:JSON.stringify(data)}:{}),
   signal:AbortSignal.timeout(1800)});
 if(!response.ok)throw new Error('Presentation API '+path+' returned '+response.status);
 return response.json();
}
await call('/v1/status'); // No physical microphone until API access succeeds.
const directory=await mkdtemp(join(tmpdir(),'ai-present-mic-'));
const wavPath=join(directory,'frame.wav');
// Spoken commands need full utterances to appear in two overlapping STT
// windows. The shorter default remains available for faster ordinary cue
// matching when hands-free command recognition is disabled.
const chunks=speechEnabled?
  new PcmSlidingWindowQueue({framesPerWindow:51200,hopFrames:6400,maxBytes:320000}):
  new PcmWindowQueue({framesPerWindow:24000,overlapFrames:8000,maxBytes:320000});
const commandGate=new LocalVoiceCommandGate();
let latest=null,busy=false,stopping=false,lastText='',lastAt=0,sequence=0;
let state=null,lastStateAt=0;
async function speakMac(text){
 if(!speak||typeof text!=='string'||!text)return;
 return speakMacPrivate(text,{
   deviceId:privateOutput.deviceId,confirmed:true,
   availableOutputs:privateOutput.availableOutputs
 });
}
async function consume(){
 if(busy)return;
 busy=true;
 try{
   while(latest&&!stopping){
     const pcm=latest;latest=null;
     try{
       const now=Date.now();
       if(now-lastStateAt>1800){state=await call('/v1/status');lastStateAt=now;}
       if(!state?.slides?.length){
         if(speechEnabled)commandGate.observe(null,now);
         continue;
       }
       await writeFile(wavPath,encodePcm16Wav(pcm),{mode:0o600});
       const transcript=(await transcribeLocalWav(wavPath,{modelPath})).trim();
       await unlink(wavPath).catch(()=>{});
       if(!transcript||transcript.length<8){
         if(speechEnabled)commandGate.observe(null,Date.now());
         continue;
       }
       const text=transcript.replace(/\s+/g,' ').trim();
       const command=speechEnabled?interpretVoice(text):null;
       if(speechEnabled){
         const verification=commandGate.observe(command,Date.now());
         if(command){
           // Two independently decoded overlapping windows must agree about
           // the exact permitted action. One utterance fires at most once.
           if(verification.confirmed){
             const result=await call('/v1/voice',{
               transcript:text,final:true,confidence:.9,
               eventId:sessionPrefix+String(++sequence),source:'local-microphone'});
             if(speak)await speakMac(result.reply);
           }
           continue;
         }
         // A partial or malformed wake-word utterance must never become an
         // unrelated content cue just because it resembles deck text.
         if(/^presentation agent(?:[\s,.:!?]|$)/i.test(text))continue;
       }
       if(text===lastText&&Date.now()-lastAt<2500)continue;
       lastText=text;lastAt=Date.now();
       const cue=findCueMatch(text,state.slides);
       // This is a verified lexical agreement score with the known deck, not
       // a claim about model posterior recognition probability.
       if(cue.score>=.84&&state.mode==='automatic'&&!state.held)
         await call('/v1/cue',{
           source:'local-microphone',type:'transcript',text,confidence:cue.score,
           final:true,eventId:sessionPrefix+String(++sequence),timestamp:Date.now()});
     }catch(error){
       await unlink(wavPath).catch(()=>{});
       process.stderr.write('Microphone observation skipped: '+String(error.message??error).slice(0,120)+'\n');
     }
   }
 }finally{busy=false;}
}
const mic=spawn('ffmpeg',[
 '-hide_banner','-nostdin','-loglevel','error',
 '-f','avfoundation','-i',':'+audioId,
 '-ac','1','-ar','16000','-f','s16le','pipe:1'
],{stdio:['ignore','pipe','pipe']});
mic.stdout.on('data',buffer=>{
 for(const window of chunks.feed(buffer))latest=window; // Drop stale chunks, never block live audio.
 if(latest)void consume();
});
let errors='';
mic.stderr.on('data',b=>{if(errors.length<1000)errors+=String(b).slice(0,400);});
mic.once('error',e=>{process.stderr.write('Microphone start failed: '+String(e.message)+'\n');process.exitCode=1;});
mic.once('close',code=>{
 stopping=true;
 if(code!==0){process.stderr.write('Microphone stopped: '+errors.slice(0,700)+'\n');process.exitCode=1;}
 void rm(directory,{recursive:true,force:true});
});
for(const signal of ['SIGINT','SIGTERM']){
 process.on(signal,()=>{stopping=true;mic.kill('SIGTERM');});
}
process.stderr.write('Local microphone active. Captured audio is never stored permanently or uploaded remotely.\n');
