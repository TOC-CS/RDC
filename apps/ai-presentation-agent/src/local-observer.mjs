const plain=v=>String(v??'').normalize('NFKC').toLowerCase().replace(/[^\p{L}\p{N} ]/gu,' ').replace(/\s+/g,' ').trim();
const words=v=>new Set(plain(v).split(' ').filter(Boolean));
function overlap(a,b){
 if(a.size<3||b.size<3)return 0;
 let shared=0;
 for(const word of a)if(b.has(word))shared++;
 return shared/(a.size+b.size-shared);
}
export function findCueMatch(text,slides){
 if(typeof text!=='string'||!Array.isArray(slides))throw new TypeError('Text and deck slides required.');
 const incoming=words(text);
 let best=null,bestScore=0;
 for(const slide of slides){
   if(!slide||typeof slide!=='object')continue;
   const phrases=[slide.text??'',...(Array.isArray(slide.cues)?slide.cues:[])];
   for(const phrase of phrases){
     const target=words(phrase);
     const score=overlap(incoming,target);
     if(score>bestScore){best=slide;bestScore=score;}
   }
 }
 return {slide:best,score:bestScore};
}
export function makeObservation(ocr,slides,{frameId,cameraRole='stage',timestamp=Date.now()}={}){
 if(!ocr||typeof ocr.text!=='string'||typeof frameId!=='string')
   throw new Error('Complete local OCR and frame metadata required.');
 const confidence=Number.isFinite(ocr.confidence)?Math.min(1,Math.max(0,ocr.confidence)):0;
 const {slide,score}=findCueMatch(ocr.text,slides);
 // The decision score measures verified overlap with known cue text, not a
 // statistical OCR probability. Repeated frames and output source filters are
 // enforced again by VisualObservationRouter.
 const reliableMatch=score>=.95&&confidence>=.35;
 const decision=reliableMatch?.91:score*.95*Math.sqrt(confidence);
 return {frameId,cameraRole,confidence:decision,ocrConfidence:confidence,
   matchScore:score,matchedSlideId:slide?.id??null,final:true,
   timestamp,observedText:ocr.text.slice(0,1000)};
}
export class JpegFrameSplitter{
 constructor({maxFrameBytes=2_097_152}={}){
   if(!Number.isInteger(maxFrameBytes)||maxFrameBytes<16)throw new Error('Frame limit must be >=16 bytes.');
   this.maxFrameBytes=maxFrameBytes;
   this.pending=Buffer.alloc(0);
 }
 feed(chunk){
   if(!Buffer.isBuffer(chunk))throw new TypeError('JPEG stream must deliver a Buffer.');
   this.pending=Buffer.concat([this.pending,chunk]);
   const frames=[];
   while(this.pending.length>0){
     const start=this.pending.indexOf(Buffer.from([255,216]));
     if(start<0){
       this.pending=this.pending.subarray(Math.max(0,this.pending.length-1));
       break;
     }
     if(start>0)this.pending=this.pending.subarray(start);
     const end=this.pending.indexOf(Buffer.from([255,217]),2);
     if(end<0){
       if(this.pending.length>this.maxFrameBytes)this.pending=this.pending.subarray(this.pending.length-1);
       break;
     }
     const size=end+2;
     if(size<=this.maxFrameBytes)frames.push(Buffer.from(this.pending.subarray(0,size)));
     this.pending=this.pending.subarray(size);
   }
   return frames;
 }
}
