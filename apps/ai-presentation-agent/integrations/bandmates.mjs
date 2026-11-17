/**
 * Passive BandMates control-plane adapter.
 * Call observe() with the session controller's CURRENT snapshot (after a beat
 * is rendered), never from inside CoreAudio/real-time audio callbacks.
 * No file/network/device operations occur here. The caller injects the output
 * function (e.g. PresentationDirector.ingest or a loopback authenticated API).
 */
export class BandMatesPresentationBridge{
 constructor({song,ingest,clock=()=>Date.now()}={}){
   if(typeof song!=='string'||!song.trim()||song.length>200)throw new Error('BandMates bridge requires an actual current song title.');
   if(typeof ingest!=='function')throw new Error('A BandMates presentation cue recipient is required.');
   this.song=song.trim();this.ingest=ingest;this.clock=clock;
   this.lastKey=null;this.pendingKey=null;this.pendingEventId=null;this.retryCount=0;
 }
 setSong(song){
   if(typeof song!=='string'||!song.trim()||song.length>200)throw new Error('Current song title required.');
   this.song=song.trim();this.lastKey=null;this.pendingKey=null;this.pendingEventId=null;this.retryCount=0;
 }
 async observe(snapshot){
   if(!snapshot||typeof snapshot!=='object'||Array.isArray(snapshot))return {changed:false,reason:'no_section'};
   const dynamics=snapshot.songDynamics??snapshot.snapshot?.songDynamics??null;
   if(!dynamics||typeof dynamics.section!=='string'||!dynamics.section.trim())
      return {changed:false,reason:'no_section'};
   // A SongDynamics arrangement is scheduled accompaniment, not evidence
   // that a singer actually performed this section. Hold the public slide.
   if(dynamics.stateKind==='planned')
     return {changed:false,reason:'planned_section_requires_live_confirmation'};
   if(!['performed','observed'].includes(dynamics.stateKind)||
      dynamics.performanceConfirmed!==true||!Number.isFinite(dynamics.confidence)||
      dynamics.confidence<.9||dynamics.confidence>1)
     return {changed:false,reason:'unconfirmed_live_section'};
   const occurrence=dynamics.occurrence;
   if(!Number.isSafeInteger(occurrence)||occurrence<1||occurrence>10000)
     return {changed:false,reason:'invalid_occurrence'};
   const session=snapshot.sessionId;
   const eventId=dynamics.eventId;
   const validIdentity=/^[A-Za-z0-9._:-]{1,128}$/;
   if(typeof session!=='string'||!validIdentity.test(session)||
      typeof eventId!=='string'||!validIdentity.test(eventId))
     return {changed:false,reason:'unverified_event_identity'};
   const observedAt=dynamics.timestamp,now=this.clock();
   if(!Number.isFinite(observedAt)||observedAt<now-5000||observedAt>now+5000)
     return {changed:false,reason:'stale_live_section'};
   const key=[session,eventId].join(':');
   // A section's beat counter moves continuously; unchanged section/occurrence
   // must not re-emit at every tick.
   const sectionKey=[session,this.song,dynamics.section,occurrence].join(':');
   if(this.lastKey===sectionKey)return {changed:false,reason:'unchanged'};
   if(this.pendingKey!==sectionKey){
     this.pendingKey=sectionKey;this.pendingEventId=key;this.retryCount=0;
   }
   const event={source:'bandmates',type:'song.section',song:this.song,
      section:dynamics.section,occurrence,
      eventId:this.pendingEventId,timestamp:observedAt,
      evidence:'BandMates-verified-performed-section'};
   // Preserve this same event ID when transport outcome is unknown. An
   // uncertain retry must not generate another native slide advance.
   const result=await this.ingest(event);
   if(result?.changed===true||['unchanged','same_cue_still_active'].includes(result?.reason)){
     this.lastKey=sectionKey;this.pendingKey=null;this.pendingEventId=null;
   }else if(result&&['cooldown','held','assisted_mode','not_running','stale','no_confident_match'].includes(result.reason)){
     // These are definitive non-delivery decisions. Do not permanently
     // consume the section; a later safe control-plane poll may retry it.
     this.retryCount++;
     this.pendingEventId=key+':retry'+this.retryCount;
   }
   return result??{changed:false,reason:'delivery_unconfirmed'};
 }
}
