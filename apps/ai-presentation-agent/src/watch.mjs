/**
 * Interpreted vision observation gate. A camera or AI host produces bounded
 * metadata; this module deliberately cannot obtain an OS webcam or desktop
 * screen without explicit operator setup. It cannot treat its own projected
 * slides as evidence for the next cue.
 */
export class VisualObservationRouter{
 constructor(director,{clock=()=>Date.now(),holdMs=200,minimumConfidence=.88}={}){
   if(!director)throw new TypeError('PresentationDirector required.');
   this.director=director;this.clock=clock;this.holdMs=holdMs;
   this.minimumConfidence=minimumConfidence;
   this.frames=new Set();this.lastKey='';this.firstSeen=-Infinity;
   this.lastFiredKey='';this.firedGestures=new Set();
 }
 async receive(obs){
   const now=this.clock();
   if(!obs||typeof obs!=='object'||Array.isArray(obs))
     throw new Error('Visual observation object required.');
   const {frameId,cameraRole,confidence,final,timestamp}=obs;
   if(typeof frameId!=='string'||frameId.length===0||frameId.length>128)
     throw new Error('Visual frame ID must be 1 to 128 characters.');
   if(!['stage','speaker','room','presentation-output'].includes(cameraRole))
     throw new Error('Unknown camera role.');
   if(!Number.isFinite(confidence)||confidence<0||confidence>1||typeof final!=='boolean')
     throw new Error('Invalid visual confidence or final flag.');
   const keyId=cameraRole+':'+frameId;
   if(this.frames.has(keyId))return {changed:false,reason:'duplicate'};
   this.frames.add(keyId);
   if(this.frames.size>512)this.frames.delete(this.frames.values().next().value);
   if(cameraRole==='presentation-output')
     return {changed:false,reason:'feedback_source'};
   if(Number.isFinite(timestamp)&&
      (timestamp<now-5000||timestamp>now+30000))return {changed:false,reason:'stale'};
   if(!final||confidence<this.minimumConfidence)
     return {changed:false,reason:'uncertain'};
   const gesture=obs.gesture??'none';
   if(!['next','previous','hold','resume','none'].includes(gesture))
     throw new Error('Unknown visual gesture.');
   let key='',event=null,command=null;
   if(gesture!=='none'){
     key='gesture:'+cameraRole+':'+gesture;
     command=gesture;
   }else if(typeof obs.recognizedSong==='string'&&typeof obs.recognizedSection==='string'&&
     obs.recognizedSong.length>0&&obs.recognizedSection.length>0){
     key='song:'+obs.recognizedSong.trim().toLowerCase()+':'+obs.recognizedSection.trim().toLowerCase();
     event={source:'vision',type:'song.section',song:obs.recognizedSong,section:obs.recognizedSection};
   }else if(typeof obs.recognizedReference==='string'&&obs.recognizedReference.trim()){
     key='scripture:'+obs.recognizedReference.trim().toLowerCase();
     event={source:'vision',type:'scripture',reference:obs.recognizedReference};
   }else if(typeof obs.observedText==='string'&&obs.observedText.trim()){
     key='text:'+obs.observedText.trim().toLowerCase().slice(0,150);
     event={source:'vision',type:'transcript',text:obs.observedText,confidence,final:true};
   }else{
     this.lastKey='';
     this.lastFiredKey='';
     return {changed:false,reason:'no_observation'};
   }
   if(key!==this.lastKey){
     this.lastKey=key;this.firstSeen=now;
     // A different gesture or neutral frame resets an older one; continuous
     // held gestures cannot produce repeating next-slide commands.
     if(command&&this.lastFiredKey!==key)this.lastFiredKey='';
     return {changed:false,reason:'confirming'};
   }
   if(now-this.firstSeen<this.holdMs)return {changed:false,reason:'confirming'};
   if(command){
     if(this.director.mode!=='automatic')return {changed:false,reason:'assisted_mode'};
     if(this.lastFiredKey===key)return {changed:false,reason:'already_fired'};
     if(this.director.held&&command!=='resume')return {changed:false,reason:'held'};
     // A secondary gate prevents successive gestures from overriding an
     // immediate slide change in a fast cue stream.
     if(now-this.director.lastTransition<this.director.cooldownMs)
       return {changed:false,reason:'cooldown'};
     const result=await this.director.command({action:command});
     this.lastFiredKey=key;
     return {changed:result.changed??false,reason:result.reason??'gesture',gesture:command};
   }
   // Independent source IDs and temporal matching allow repeated song choruses
   // while still preventing projection-feedback loops.
   return this.director.ingest({...event,eventId:frameId,timestamp:now});
 }
}
