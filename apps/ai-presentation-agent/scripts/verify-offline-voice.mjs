#!/usr/bin/env node
// Local-only acceptance: produces synthetic spoken commands into temporary files
// using Apple's say -o (no system audio playback), transcribes with local
// Whisper.cpp and verifies slide commands. No microphone, camera, or cloud.
import {mkdtemp,rm,access} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir,platform} from 'node:os';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {performance} from 'node:perf_hooks';
import {fileURLToPath} from 'node:url';
import {PresentationDirector} from '../src/director.mjs';
import {MemoryAdapter} from '../src/adapters.mjs';
import {VoiceInputRouter,interpretVoice,transcribeLocalWav} from '../src/voice.mjs';

const exec=promisify(execFile);
const defaultModel=fileURLToPath(new URL('../.tooling/models/ggml-tiny.en.bin',import.meta.url));
const sentences=[
  {input:'Presentation agent, next slide.',expected:'next'},
  {input:'Presentation agent, hold slides.',expected:'hold'},
  {input:'Presentation agent, resume.',expected:'resume'},
  {input:'The next slide is important to our teaching.',expected:null},
  {input:'Presentation agent, what slide are we on?',expected:'status'}
];

export async function verifyOfflineVoice({modelPath=defaultModel}={}){
 if(platform()!=='darwin')throw new Error('Synthetic Apple voice rehearsal requires macOS.');
 if(typeof modelPath!=='string'||!modelPath.startsWith('/'))
   throw new Error('Select a local absolute Whisper.cpp model path.');
 await access(modelPath);
 const temp=await mkdtemp(join(tmpdir(),'toc-voice-rehearsal-'));
 const director=new PresentationDirector({adapter:new MemoryAdapter()});
 director.load({slides:[
   {id:'opening',title:'Opening'},
   {id:'welcome',title:'Welcome'},
   {id:'closing',title:'Closing'}
 ]});
 await director.start('manual');
 const router=new VoiceInputRouter(director);
 const samples=[];
 try{
   for(let i=0;i<sentences.length;i++){
     const {input,expected}=sentences[i];
     const file=join(temp,'sample-'+i),aiff=file+'.aiff',wav=file+'.wav';
     await exec('/usr/bin/say',['-v','Samantha','-o',aiff,input],
       {timeout:10_000,maxBuffer:32_768});
     await exec('ffmpeg',['-hide_banner','-loglevel','error','-nostdin','-y',
       '-i',aiff,'-ar','16000','-ac','1','-c:a','pcm_s16le',wav],
       {timeout:10_000,maxBuffer:32_768});
     const start=performance.now();
     const transcript=await transcribeLocalWav(wav,{modelPath});
     const modelMs=Number((performance.now()-start).toFixed(1));
     const command=interpretVoice(transcript);
     const action=command?.action??null;
     const receipt=await router.receive({transcript,confidence:1,final:true,
       eventId:'synthetic-local-'+i,source:'offline-rehearsal'});
     const match=action===expected;
     samples.push({input,transcript,expectedAction:expected,recognizedAction:action,
       matched:match,transcriptionMs:modelMs,
       commandAccepted:receipt.commandAccepted??false,
       currentSlide:director.snapshot().current?.id});
     if(!match)
       throw new Error('Offline speech command mismatch for synthetic phrase '+(i+1)+
         '. Expected '+JSON.stringify(expected)+', got '+JSON.stringify(action)+'.');
   }
   const state=director.snapshot();
   if(state.index!==1||state.held)
     throw new Error('Offline speech rehearsal finished with unexpected deck state.');
   return {
     schema:'toc.presentation.offline-speech-rehearsal/v1',
     engine:'local-whisper.cpp',
     generatedSpeech:'macOS say to temporary audio file',
     microphoneCaptured:false,audioPlayedToSpeakers:false,cloudSpeechServices:false,
     verified:samples.length,passed:samples.filter(s=>s.matched).length,
     finalSlide:state.current.id,finalHeld:state.held,
     notes:'The recognition results use synthetic speech. Actual microphone, room acoustics, feedback and streaming devices still require separate acceptance.',
     samples
   };
 }finally{await rm(temp,{recursive:true,force:true});}
}
if(process.argv[1]&&import.meta.url===new URL('file://'+process.argv[1]).href){
 try{
   const result=await verifyOfflineVoice({
     modelPath:process.env.PRESENTATION_WHISPER_MODEL??defaultModel
   });
   process.stdout.write(JSON.stringify(result,null,2)+'\n');
 }catch(error){
   process.stderr.write('Offline speech rehearsal failed: '+String(error?.message??error)+'\n');
   process.exitCode=1;
 }
}
