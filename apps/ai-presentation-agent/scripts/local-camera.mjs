#!/usr/bin/env node
// Operator-started, local-only AVFoundation camera observation.
// Reads actual live camera frames, applies offline Apple Vision OCR, and sends
// matched visual cues through the authenticated local Presentation Agent API.
// This executable never opens a camera unless the operator supplies --device
// and the local API token. It does not change system camera permissions.
import {spawn} from 'node:child_process';
import {randomUUID} from 'node:crypto';
import {access} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {JpegFrameSplitter,makeObservation} from '../src/local-observer.mjs';
const argv=process.argv.slice(2);
if(argv.includes('--help')||argv.includes('-h')){
 process.stdout.write('Usage: PRESENTATION_API_TOKEN=<private token> node scripts/local-camera.mjs --device DEVICE_NUMBER [--role stage|speaker|room]\n');
 process.stdout.write('Uses AVFoundation camera and offline Apple Vision OCR. Microphone is not activated.\n');
 process.exit(0);
}
const token=process.env.PRESENTATION_API_TOKEN??'';
if(Buffer.byteLength(token)<16){
 process.stderr.write('PRESENTATION_API_TOKEN must be configured before local camera access.\n');
 process.exit(2);
}
const value=option=>{
 const i=argv.indexOf(option);
 if(i<0||i+1>=argv.length)return null;
 return argv[i+1];
};
const rawId=value('--device');
if(rawId===null||!/^(0|[1-9][0-9]?)$/.test(rawId)){
 process.stderr.write('Provide an explicit video input device number via --device 0, etc.\n');
 process.exit(2);
}
const cameraRole=value('--role')??'stage';
if(!['stage','speaker','room'].includes(cameraRole)){
 process.stderr.write('Camera role must be stage, speaker or room. Output capture cannot be used as a control source.\n');
 process.exit(2);
}
const port=Number(process.env.PRESENTATION_API_PORT??8789);
if(!Number.isInteger(port)||port<1024||port>65535)throw new Error('Invalid local API port.');
const base='http://127.0.0.1:'+port;
const executable=fileURLToPath(new URL('../native/macos/build/stage-ocr',import.meta.url));
if(process.platform!=='darwin')throw new Error('Apple Vision camera observer requires macOS.');
await access(executable);
const request=async(path,body=null)=>{
 const res=await fetch(base+path,{method:body?'POST':'GET',
  headers:{Authorization:'Bearer '+token,...(body?{'Content-Type':'application/json'}:{})},
  ...(body?{body:JSON.stringify(body)}:{}),
  signal:AbortSignal.timeout(1800)});
 if(!res.ok)throw new Error('Presentation API '+path+' returned '+res.status);
 return res.json();
};
await request('/v1/status'); // Fail before ever opening the physical camera.
const splitter=new JpegFrameSplitter({maxFrameBytes:1_500_000});
let pendingFrame=null,busy=false,stopping=false,lastState=null,lastStateAt=0,frameNumber=0;
const framePrefix='local-cam-'+randomUUID().slice(0,8)+'-';
async function recognize(jpeg){
 return await new Promise((resolve,reject)=>{
   const child=spawn(executable,['-'],{stdio:['pipe','pipe','pipe']});
   let stdout='',stderr='';
   child.stdout.on('data',b=>{if(stdout.length<10000)stdout+=String(b);});
   child.stderr.on('data',b=>{if(stderr.length<1000)stderr+=String(b);});
   const timeout=setTimeout(()=>child.kill('SIGKILL'),1300);
   child.once('error',error=>{clearTimeout(timeout);reject(error);});
   child.once('close',code=>{
     clearTimeout(timeout);
     if(code!==0)return reject(new Error('Apple Vision OCR failed: '+stderr.slice(0,100)));
     try{resolve(JSON.parse(stdout));}catch{reject(new Error('Invalid Apple Vision OCR result.'));}
   });
   child.stdin.end(jpeg);
 });
}
async function drain(){
 if(busy)return;
 busy=true;
 try{
   while(pendingFrame&&!stopping){
     const frame=pendingFrame;pendingFrame=null;
     try{
       const now=Date.now();
       if(now-lastStateAt>1500){
         lastState=await request('/v1/status');lastStateAt=now;
       }
       if(lastState?.mode!=='automatic'||lastState.held||!Array.isArray(lastState?.slides))continue;
       const result=await recognize(frame);
       if(!result.text)continue;
       const cue=makeObservation(result,lastState.slides,{
         cameraRole,frameId:framePrefix+String(++frameNumber),timestamp:now
       });
       if(cue.confidence>=.88)await request('/v1/watch',cue);
     }catch(error){
       process.stderr.write('One camera cue was skipped: '+String(error?.message??error).slice(0,120)+'\n');
     }
   }
 }finally{busy=false;}
}
const video=spawn('ffmpeg',[
 '-hide_banner','-nostdin','-loglevel','error',
 '-f','avfoundation','-framerate','30','-i',rawId+':none',
 '-vf','fps=2,scale=960:-1','-q:v','5','-vcodec','mjpeg',
 '-f','image2pipe','pipe:1'
],{stdio:['ignore','pipe','pipe']});
video.stdout.on('data',packet=>{
 for(const frame of splitter.feed(packet))pendingFrame=frame;
 if(pendingFrame)void drain();
});
let lastError='';
video.stderr.on('data',chunk=>{
 if(lastError.length<1600)lastError+=String(chunk).slice(0,600);
});
video.once('error',error=>{
 process.stderr.write('Unable to start camera capture: '+String(error.message)+'\n');
 process.exitCode=1;
});
video.once('close',code=>{
 stopping=true;
 if(code!==0&&!stopping)process.stderr.write('Camera ended with code '+String(code)+'\n');
 if(code!==0){
   process.stderr.write('Camera capture ended: '+lastError.slice(0,700)+'\n');
   process.exitCode=1;
 }
});
for(const signal of ['SIGINT','SIGTERM']){
 process.on(signal,()=>{stopping=true;video.kill('SIGTERM');});
}
process.stderr.write('Local stage camera observer started. Frames stay local and are not recorded.\n');
