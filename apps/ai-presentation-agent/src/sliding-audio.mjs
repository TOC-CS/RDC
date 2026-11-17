// Bounded, overlapping PCM speech-recognition windows. Feed accepts raw
// 16-bit mono PCM bytes; it does not open, record, or route an OS device.
export class PcmSlidingWindowQueue{
 constructor({framesPerWindow=51200,hopFrames=6400,maxBytes=320000}={}){
   if(!Number.isInteger(framesPerWindow)||framesPerWindow<4||
     !Number.isInteger(hopFrames)||hopFrames<1||hopFrames>=framesPerWindow||
     !Number.isInteger(maxBytes)||maxBytes<framesPerWindow*2||
     maxBytes>8_000_000)
       throw new Error('Invalid overlapping microphone window parameters.');
   this.windowBytes=framesPerWindow*2;
   this.hopBytes=hopFrames*2;
   this.maxBytes=maxBytes;this.buffer=Buffer.alloc(0);
 }
 feed(chunk){
   if(!Buffer.isBuffer(chunk))throw new TypeError('Speech stream chunk must be a Buffer.');
   this.buffer=Buffer.concat([this.buffer,chunk]);
   if(this.buffer.length>this.maxBytes){
     let trim=this.buffer.length-this.maxBytes;
     if(trim%2)trim++;
     this.buffer=this.buffer.subarray(trim);
   }
   const result=[];
   while(this.buffer.length>=this.windowBytes){
     result.push(Buffer.from(this.buffer.subarray(0,this.windowBytes)));
     this.buffer=this.buffer.subarray(this.hopBytes);
     // Never flood a downstream Whisper process after temporary capture lag.
     if(result.length>2)result.shift();
   }
   return result;
 }
}

// Confirm a single explicit wake command from two consecutive independent
// window transcriptions; latch it until the same utterance has cleared.
export class LocalVoiceCommandGate{
 constructor({confirmations=2,windowMs=8000,releaseQuietFrames=2,releaseHoldMs=800}={}){
   if(!Number.isInteger(confirmations)||confirmations<2||confirmations>4||
      !Number.isInteger(windowMs)||windowMs<500||windowMs>30000||
      !Number.isInteger(releaseQuietFrames)||releaseQuietFrames<1||releaseQuietFrames>10||
      !Number.isInteger(releaseHoldMs)||releaseHoldMs<0||releaseHoldMs>10000)
     throw new Error('Invalid speech confirmation limits.');
   this.confirmations=confirmations;this.windowMs=windowMs;
   this.releaseQuietFrames=releaseQuietFrames;this.releaseHoldMs=releaseHoldMs;
   this.candidate=null;this.blocked=null;this.lastFiredAt=-Infinity;this.quietFrames=0;
 }
 observe(command,now=Date.now()){
   if(!Number.isFinite(now))throw new Error('Invalid speech timestamp.');
   if(command===null){
     this.quietFrames++;
     this.candidate=null;
     if(this.quietFrames>=this.releaseQuietFrames&&now-this.lastFiredAt>=this.releaseHoldMs)
       this.blocked=null;
     return {confirmed:false,reason:'no_command'};
   }
   if(!command||typeof command.action!=='string')
     throw new Error('Recognized voice command object required.');
   const signature=JSON.stringify({action:command.action,index:command.index??null,name:command.name??null});
   this.quietFrames=0;
   if(signature===this.blocked)return {confirmed:false,reason:'already_executed'};
   if(this.candidate?.signature!==signature||now-this.candidate.startedAt>this.windowMs)
     this.candidate={signature,startedAt:now,matches:1};
   else this.candidate.matches++;
   if(this.candidate.matches<this.confirmations)return {confirmed:false,reason:'confirming'};
   this.blocked=signature;this.lastFiredAt=now;this.candidate=null;
   return {confirmed:true,reason:'confirmed',signature};
 }
}
