#!/usr/bin/env node
// Real Whisper.cpp inference across simulated FFmpeg 16-kHz PCM stream chunks.
// No live microphone, app focus, projector, network or media playback.
import {mkdtemp,readFile,writeFile,rm,access} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir,platform} from 'node:os';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {performance} from 'node:perf_hooks';
import {fileURLToPath} from 'node:url';
import {PcmSlidingWindowQueue,LocalVoiceCommandGate} from '../src/sliding-audio.mjs';
import {encodePcm16Wav} from '../src/audio-stream.mjs';
import {interpretVoice,transcribeLocalWav,VoiceInputRouter} from '../src/voice.mjs';
import {PresentationDirector} from '../src/director.mjs';
import {MemoryAdapter} from '../src/adapters.mjs';

const exec=promisify(execFile);
const model=fileURLToPath(new URL('../.tooling/models/ggml-tiny.en.bin',import.meta.url));
export async function verifyStreamVoice({modelPath=model}={}){
 if(platform()!=='darwin')throw new Error('Synthetic voice streaming rehearsal requires macOS.');
 await access(modelPath);
 const temp=await mkdtemp(join(tmpdir(),'toc-presentation-voice-stream-'));
 try{
   const aiff=join(temp,'phrase.aiff'),pcmFile=join(temp,'phrase.pcm');
   const wavPath=join(temp,'window.wav');
   const spoken='Presentation agent, next slide.';
   await exec('/usr/bin/say',['-v','Samantha','-o',aiff,spoken],{timeout:10000});
   await exec('ffmpeg',['-hide_banner','-nostdin','-loglevel','error','-y',
     '-i',aiff,'-ac','1','-ar','16000','-f','s16le',pcmFile],{timeout:10000});
   const raw=await readFile(pcmFile);
   const silence=sampleSeconds=>Buffer.alloc(Math.round(sampleSeconds*16000)*2);
   const stream=Buffer.concat([silence(0.8),raw,silence(3.4)]);
   const chunks=new PcmSlidingWindowQueue({
     framesPerWindow:51200,hopFrames:6400,maxBytes:320000});
   const audioWindows=[];
   for(let i=0;i<stream.length;i+=4096)
     audioWindows.push(...chunks.feed(stream.subarray(i,i+4096)));
   const gate=new LocalVoiceCommandGate();
   const director=new PresentationDirector({adapter:new MemoryAdapter()});
   director.load({slides:[{id:'opening'},{id:'welcome'}]});
   await director.start('manual');
   const voice=new VoiceInputRouter(director);
   const observations=[],start=performance.now();
   let fired=0;
   for(let i=0;i<audioWindows.length;i++){
     await writeFile(wavPath,encodePcm16Wav(audioWindows[i]));
     const decoded=await transcribeLocalWav(wavPath,{modelPath});
     const command=interpretVoice(decoded);
     const gateResult=gate.observe(command,3200+i*400);
     observations.push({window:i,transcript:decoded,recognizedAction:command?.action??null,
       confirmation:gateResult.reason});
     if(gateResult.confirmed){
       fired++;
       const result=await voice.receive({transcript:decoded,final:true,
         confidence:.9,source:'offline-audio-stream',
         eventId:'synthetic-window-'+i});
       if(!result.commandAccepted)throw new Error('Confirmed local wake command was not accepted.');
     }
   }
   if(fired!==1||director.snapshot().current.id!=='welcome')
     throw new Error('Streaming command must advance exactly one slide, observed '+
       fired+' confirmed commands and '+director.snapshot().current.id+' current slide.');
   return {schema:'toc.presentation.streaming-speech-rehearsal/v1',
     audioInput:'generated-spoken-file-as-synthetic-PCM-stream',
     rawPcmBytes:stream.length,decodedWindows:observations.length,
     confirmedCommands:fired,finalSlide:director.snapshot().current.id,
     elapsedInferenceAndControlMs:Number((performance.now()-start).toFixed(1)),
     microphoneCaptured:false,speakerOutput:false,usesCloud:false,
     realRoomLatencyVerified:false,observations};
 }finally{await rm(temp,{recursive:true,force:true});}
}
if(process.argv[1]&&import.meta.url===new URL('file://'+process.argv[1]).href){
 try{
   process.stdout.write(JSON.stringify(await verifyStreamVoice({
     modelPath:process.env.PRESENTATION_WHISPER_MODEL??model
   }),null,2)+'\n');
 }catch(error){
   process.stderr.write('Streaming speech rehearsal failed: '+String(error?.message??error)+'\n');
   process.exitCode=1;
 }
}
