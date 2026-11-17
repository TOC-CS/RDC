/**
 * Receives ONLY verified, non-real-time section events from BandMates.
 * Does not import BandMates audio engines, acquire MIDI, open microphones,
 * schedule music, or send anything without an injected downstream sink.
 *
 * A running BandMates companion API currently does not provide this feed.
 * Its native session owner must emit this schema from a separate control
 * thread when a current section is independently confirmed.
 */
const safeId=/^[A-Za-z0-9._:-]{1,128}$/;
const valid=(value,label,limit=128)=>{
 if(typeof value!=='string'||!value.trim()||value.length>limit)
   throw new Error('Invalid BandMates '+label+'.');
 return value.trim();
};
export class VerifiedBandMatesSectionRelay{
 constructor({sessionId,send,clock=()=>Date.now(),minConfidence=.9}={}){
   this.sessionId=valid(sessionId,'session ID');
   if(!safeId.test(this.sessionId))throw new Error('Invalid BandMates session ID.');
   if(typeof send!=='function')throw new TypeError('Non-real-time cue sender required.');
   if(typeof clock!=='function')throw new TypeError('Time source required.');
   if(!Number.isFinite(minConfidence)||minConfidence<.8||minConfidence>1)
     throw new Error('Invalid required confidence threshold.');
   this.send=send;this.clock=clock;this.minConfidence=minConfidence;
   this.receipts=new Map();
 }
 async accept(event){
   if(!event||typeof event!=='object'||Array.isArray(event))
     throw new Error('Verified BandMates section event object required.');
   if(event.schema!=='bandmates.performance-section/v1')
     throw new Error('Unsupported BandMates verified section schema.');
   if(event.sessionId!==this.sessionId)
     throw new Error('BandMates event belongs to another session.');
   if(typeof event.eventId!=='string'||!safeId.test(event.eventId))
     throw new Error('BandMates event requires a stable ID.');
   const song=valid(event.song,'song title',200),section=valid(event.section,'section',100);
   const occurrence=event.occurrence;
   if(!Number.isSafeInteger(occurrence)||occurrence<1||occurrence>10000)
     throw new Error('BandMates section occurrence must be positive.');
   const confidence=event.confidence;
   if(!Number.isFinite(confidence)||confidence<this.minConfidence||confidence>1)
     return {changed:false,reason:'unconfirmed_live_section'};
   if(event.stateKind!=='performed'&&event.stateKind!=='observed')
     return {changed:false,reason:'planned_section_requires_live_confirmation'};
   if(event.performanceConfirmed!==true)
     return {changed:false,reason:'performance_not_confirmed'};
   if(!Number.isFinite(event.timestamp))
     return {changed:false,reason:'missing_event_timestamp'};
   const now=this.clock();
   if(event.timestamp<now-5000||event.timestamp>now+5000)
     return {changed:false,reason:'stale_live_section'};
   const key=this.sessionId+':'+event.eventId;
   const signature=JSON.stringify({song,section,occurrence,timestamp:event.timestamp});
   const receipt=this.receipts.get(key);
   if(receipt){
     if(receipt.signature!==signature)
       throw new Error('BandMates live section event identity conflict.');
     // Unknown network outcomes must reuse the original unique event ID and
     // cannot be blindly posted again to a physical presentation output.
     return {...(await receipt.promise),reason:'duplicate_verified_section',changed:false};
   }
   if(this.receipts.size>=4096)
     throw new Error('BandMates section event receipt limit reached; begin a new session.');
   const cue={
     source:'bandmates',type:'song.section',song,section,occurrence,
     eventId:key,timestamp:event.timestamp
   };
   const promise=this.send(cue);
   this.receipts.set(key,{signature,promise});
   return promise;
 }
}
