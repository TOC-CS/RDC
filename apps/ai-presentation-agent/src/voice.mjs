import {spawn} from 'node:child_process';
import {speakMacPrivate} from './private-talkback.mjs';
const normalize=x=>String(x??'').trim().replace(/[.!?]+$/g,'').replace(/\s+/g,' ').toLowerCase();
export function interpretVoice(transcript,{pushToTalk=false,wakeWord='presentation agent'}={}){
 let value=normalize(transcript),wake=normalize(wakeWord);
 if(!pushToTalk){
   // Whisper and host ASR commonly add a comma, colon, or period after the
   // wake phrase. Accept that punctuation only at the exact wake boundary.
   if(!value.startsWith(wake))return null;
   const tail=value.slice(wake.length);
   if(tail&&!/^[\s,.:!?]/.test(tail))return null;
   value=tail.replace(/^[\s,.:!?]+/,'').trim();
 }
 // A single trailing polite request may be comma-separated. Keep sentence
 // punctuation inside the command so multiple instructions do not execute.
 value=value.replace(/,\s*(?=please$)/,' ').replace(/\s+/g,' ').trim();
 if(!value)return {action:'status'};
 if(/^(next|advance|next slide|advance slide|go forward|move forward)( please)?$/.test(value))return {action:'next'};
 if(/^(back|previous|previous slide|go back|go back one slide)( please)?$/.test(value))return {action:'previous'};
 if(/^(hold|pause|hold slides|pause slides|stop advancing|wait there)$/.test(value))return {action:'hold'};
 if(/^(resume|continue|resume slides|follow again|go automatic)$/.test(value))return {action:'resume'};
 if(/^(status|where are we|what slide|what slide are we on|what is showing|what is on screen)$/.test(value))return {action:'status'};
 const number=value.match(/^(?:show|go to|jump to) slide (\d{1,4})$/);
 if(number)return {action:'goto',index:Number(number[1])-1};
 const name=value.match(/^(?:show|go to|jump to) (?:the )?([a-z0-9 :._-]{2,80})$/);
 if(name)return {action:'goto_name',name:name[1]};
 return null;
}
export class VoiceChat{
 constructor(director,{speak=null,onChat=null,wakeWord='presentation agent'}={}){
   this.director=director;this.speak=speak;this.onChat=onChat;this.wakeWord=wakeWord;
 }
 async handle(transcript,{pushToTalk=false,respondAloud=false,source='operator'}={}){
   const command=interpretVoice(transcript,{pushToTalk,wakeWord:this.wakeWord});
   if(!command){
     if(pushToTalk&&this.onChat){
       const reply=String(await this.onChat(transcript,{presentation:this.director.snapshot(),source}));
       if(respondAloud&&this.speak)await this.speak(reply);
       return {accepted:true,kind:'chat',reply};
     }
     return {accepted:false,kind:'ignored',reply:''};
   }
   let result;
   if(command.action==='goto_name'){
     const name=normalize(command.name),slides=this.director.snapshot().slides;
     const match=slides.find(s=>[s.id,s.title,s.section,s.reference].some(v=>normalize(v)===name));
     if(!match)return {accepted:false,kind:'command',reply:'I could not find that slide.'};
     result=await this.director.command({action:'goto',id:match.id});
   }else result=await this.director.command(command);
   const state=this.director.snapshot(),slide=state.current;
   let reply='';
   if(command.action==='status'){
     reply=slide?'Slide '+String(state.index+1)+': '+String(slide.title??slide.id)+
       (slide.section?' ('+slide.section+')':'')+'.':'No presentation is loaded.';
   }else if(command.action==='hold')reply='Holding the current slide.';
   else if(command.action==='resume')reply='Automatic following can resume.';
   else if(slide)reply='Showing '+String(slide.title??slide.id)+(slide.section?' ('+slide.section+')':'')+'.';
   else reply='Presentation ready.';
   if(respondAloud&&this.speak)await this.speak(reply);
   return {accepted:true,kind:'command',command,result,reply};
 }
}
export async function speakMac(text,{outputDevice=null,privateMonitorConfirmed=false}={}){
 // In a venue, the system default output can be the mixer or livestream.
 // Require a freshly selected owner-approved private monitor instead.
 return speakMacPrivate(text,{
   deviceId:outputDevice,confirmed:privateMonitorConfirmed
 });
}
/**
 * The user's main AI app handles speech input and speaking the returned reply
 * by default. Local microphone/STT and TTS are independently optional.
 */
export function voiceCapabilities({localSttModel=null}={}){
 return {
   default:'host',modes:localSttModel?['host','local']:['host'],
   host:{transcriptInput:true,replyText:true,requiresHostVoiceSupport:true},
   local:{sttReady:!!localSttModel,ttsReady:process.platform==='darwin',
     requiresMicrophonePermission:true,sttEngine:'whisper.cpp',ttsEngine:'macOS say'},
   warning:'Voice capture and playback require support from the AI host or configured local engines.'
 };
}
export class VoiceInputRouter{
 constructor(director,{mode='host',speak=null,onChat=null,localSttModel=null}={}){
   if(!['host','local'].includes(mode))throw new Error('Unknown voice input mode.');
   if(mode==='local'&&!localSttModel)throw new Error('Local voice requires a configured speech model.');
   this.director=director;this.mode=mode;this.voice=new VoiceChat(director,{speak,onChat});
   this.receipts=new Map();
   this.deckRef=director.deck;
 }
 async receive({transcript,confidence=1,final=true,pushToTalk=false,respondAloud=false,
   eventId=null,timestamp=undefined,source='speech'}={}){
   if(typeof transcript!=='string'||transcript.length>6000)
     throw new Error('Voice transcript must be text under 6000 characters.');
   if(!Number.isFinite(confidence)||confidence<0||confidence>1||typeof final!=='boolean')
     throw new Error('Voice recognition metadata invalid.');
   if(eventId!==null&&(typeof eventId!=='string'||!/^[A-Za-z0-9._:-]{1,128}$/.test(eventId)))
     throw new Error('Voice event ID must contain 1 to 128 letters, digits, periods, underscores, colons or hyphens.');
   if(this.deckRef!==this.director.deck){
     this.receipts.clear();
     this.deckRef=this.director.deck;
   }
   if(!final||confidence<.82)
     return {accepted:false,commandAccepted:false,delivery:this.mode,speakByHost:false,reason:'unconfirmed'};
   const cmd=interpretVoice(transcript,{pushToTalk});
   if(cmd||pushToTalk){
     const perform=async()=>{
       const result=await this.voice.handle(transcript,{pushToTalk,
         respondAloud:this.mode==='local'&&respondAloud,source});
       return {...result,delivery:this.mode,
         speakByHost:this.mode==='host'&&result.accepted&&!!result.reply,
         commandAccepted:result.kind==='command'&&result.accepted};
     };
     if(eventId!==null){
       // Stable recognition IDs from the host or local microphone are retained
       // so retransmission cannot advance slides or speak the same reply twice.
       const key=String(source)+':'+eventId;
       const signature=normalize(transcript)+':'+String(Boolean(pushToTalk));
       const previous=this.receipts.get(key);
       if(previous){
         if(previous.signature!==signature)
           throw new Error('Voice event identity conflict: an event ID was reused for different speech.');
         const prior=await previous.promise;
         return {...prior,accepted:false,commandAccepted:false,
           speakByHost:false,reason:'duplicate_voice_command'};
       }
       if(this.receipts.size>=4096)
         throw new Error('Voice event receipt capacity reached; load a new presentation to begin another session.');
       const promise=perform();
       this.receipts.set(key,{signature,promise});
       return promise;
     }
     return perform();
   }
   const follow=await this.director.ingest({
     source,type:'transcript',text:transcript,confidence,final,eventId,timestamp
   });
   return {accepted:false,commandAccepted:false,delivery:this.mode,speakByHost:false,follow};
 }
}
export async function transcribeLocalWav(audioPath,{modelPath}={}){
 if(!modelPath||typeof modelPath!=='string')throw new Error('Explicit local Whisper model path required.');
 if(!audioPath||typeof audioPath!=='string')throw new Error('Audio WAV path required.');
 const {access}=await import('node:fs/promises');
 await access(modelPath);await access(audioPath);
 return new Promise((resolve,reject)=>{
   const args=['-m',modelPath,'-f',audioPath,'--no-prints','--no-timestamps'];
   const child=spawn('whisper-cli',args,{stdio:['ignore','pipe','pipe'],signal:AbortSignal.timeout(15000)});
   let stdout='',stderr='';
   child.stdout.on('data',chunk=>{if(stdout.length<20000)stdout+=String(chunk);});
   child.stderr.on('data',chunk=>{if(stderr.length<5000)stderr+=String(chunk);});
   child.once('error',reject);
   child.once('exit',code=>code===0?resolve(stdout.trim()):
     reject(new Error('Local transcription failed ('+code+'): '+stderr.slice(-700))));
 });
}
