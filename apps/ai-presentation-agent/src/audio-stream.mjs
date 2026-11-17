export function encodePcm16Wav(pcm,{sampleRate=16000}={}){
 if(!Buffer.isBuffer(pcm)||pcm.length%2!==0||pcm.length>8_000_000||
    !Number.isInteger(sampleRate)||sampleRate<8000||sampleRate>96000)
   throw new Error('A bounded mono 16-bit PCM buffer is required.');
 const wav=Buffer.alloc(44+pcm.length);
 wav.write('RIFF',0,'ascii');wav.writeUInt32LE(36+pcm.length,4);
 wav.write('WAVE',8,'ascii');wav.write('fmt ',12,'ascii');
 wav.writeUInt32LE(16,16);wav.writeUInt16LE(1,20);wav.writeUInt16LE(1,22);
 wav.writeUInt32LE(sampleRate,24);wav.writeUInt32LE(sampleRate*2,28);
 wav.writeUInt16LE(2,32);wav.writeUInt16LE(16,34);
 wav.write('data',36,'ascii');wav.writeUInt32LE(pcm.length,40);
 pcm.copy(wav,44);
 return wav;
}
export class PcmWindowQueue{
 constructor({framesPerWindow=24000,overlapFrames=8000,maxBytes=640000}={}){
  if(!Number.isInteger(framesPerWindow)||framesPerWindow<2||
    !Number.isInteger(overlapFrames)||overlapFrames<0||overlapFrames>=framesPerWindow||
    !Number.isInteger(maxBytes)||maxBytes<framesPerWindow*2)
    throw new Error('Invalid microphone chunk and buffer limits.');
  this.windowBytes=framesPerWindow*2;
  this.overlapBytes=overlapFrames*2;
  this.maxBytes=maxBytes;this.buffer=Buffer.alloc(0);this.previousTail=Buffer.alloc(0);
 }
 feed(chunk){
  if(!Buffer.isBuffer(chunk))throw new TypeError('Audio input must be a Buffer.');
  this.buffer=Buffer.concat([this.buffer,chunk]);
  if(this.buffer.length>this.maxBytes){
    this.buffer=this.buffer.subarray(this.buffer.length-this.maxBytes);
    if(this.buffer.length%2)this.buffer=this.buffer.subarray(1);
  }
  const windows=[];
  while(this.buffer.length>=this.windowBytes){
    const part=this.buffer.subarray(0,this.windowBytes);
    const combined=Buffer.concat([this.previousTail,part]);
    this.previousTail=Buffer.from(part.subarray(part.length-this.overlapBytes));
    this.buffer=this.buffer.subarray(this.windowBytes);
    windows.push(combined);
    if(windows.length>2)windows.shift();
  }
  return windows;
 }
}
