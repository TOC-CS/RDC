const MAX_SLIDES=1000;
const MODES=new Set(['manual','assisted','automatic']);
const clean=text=>String(text??'').toLocaleLowerCase('en-US').normalize('NFKC').replace(/[^\p{L}\p{N}\s:]/gu,' ').replace(/\s+/g,' ').trim();
// BandMates calls its first verse 'verse', while lyric decks often label it 'Verse 1'.
// Preserve the distinct native 'verse-2' and every other section identity.
const canonicalSongSection=value=>{const section=clean(value);return section==='verse'?'verse 1':section;};
function validateDeck(input){
 if(!input||typeof input!=='object'||!Array.isArray(input.slides)||
    input.slides.length<1||input.slides.length>MAX_SLIDES)throw new Error('Deck must have 1 to 1000 slides.');
 const ids=new Set();
 const slides=input.slides.map((slide,i)=>{
   if(!slide||typeof slide!=='object'||typeof slide.id!=='string'||!/^[\w.-]{1,80}$/.test(slide.id))throw new Error('Every slide requires a safe id.');
   if(ids.has(slide.id))throw new Error('Unique slide ids required. Duplicate: '+slide.id);
   ids.add(slide.id);
   for(const key of ['text','title','song','section','kind','reference','scene','presentationId']){
     if(slide[key]!=null&&(typeof slide[key]!=='string'||slide[key].length>10000))throw new Error('Invalid slide '+key);
   }
   if(slide.cues!==undefined&&(!Array.isArray(slide.cues)||slide.cues.length>30||
      slide.cues.some(v=>typeof v!=='string'||v.length>600)))throw new Error('Invalid slide cues.');
   if(slide.occurrence!==undefined&&(!Number.isSafeInteger(slide.occurrence)||slide.occurrence<1))
     throw new Error('Slide occurrence must be a positive integer.');
   if(slide.targetIndex!==undefined&&(!Number.isSafeInteger(slide.targetIndex)||slide.targetIndex<0||slide.targetIndex>10000))
     throw new Error('Presentation targetIndex must be a zero-based integer from 0 to 10000.');
   return Object.freeze({...slide,cues:Object.freeze([...(slide.cues??[])]),position:i});
 });
 return Object.freeze({title:String(input.title??'Presentation').slice(0,200),theme:input.theme==='light'?'light':'dark',slides:Object.freeze(slides)});
}
function matchingSlide(event,slides,currentIndex){
 const search=[...slides.slice(currentIndex+1),...slides.slice(0,currentIndex+1)];
 if(event.type==='song.section'){
   const song=clean(event.song),section=canonicalSongSection(event.section);
   if(!song||!section)return null;
   const matches=search.filter(s=>clean(s.song)===song&&canonicalSongSection(s.section)===section);
   if(Number.isSafeInteger(event.occurrence)){
     const exact=matches.find(s=>s.occurrence===event.occurrence);
     if(exact)return exact;
     // A single legacy unnumbered section can denote its first occurrence.
     // Never substitute an earlier/later chorus when the performer explicitly
     // reports another occurrence that the current deck cannot identify.
     if(event.occurrence===1&&matches.length===1&&
        matches[0].occurrence===undefined)return matches[0];
     return null;
   }
   return matches[0]??null;
 }
 if(event.type==='scripture'){
   const reference=clean(event.reference);
   return reference?search.find(s=>clean(s.reference)===reference)??null:null;
 }
 if(event.type==='transcript'){
   if(event.final!==true||!Number.isFinite(event.confidence)||event.confidence<.83)return null;
   const utterance=clean(event.text);
   const words=utterance.split(' ').filter(Boolean);
   if(words.length<3||words.length>120)return null;
   let best=null,bestScore=0;
   for(const slide of search){
     for(const phrase of [...slide.cues,slide.text??'']){
       const target=clean(phrase),phrases=target.split(' ').filter(Boolean);
       if(phrases.length<3)continue;
       const a=new Set(words),b=new Set(phrases);
       let matching=0;for(const word of a)if(b.has(word))matching++;
       const score=target.includes(utterance)||utterance.includes(target)?1:
          matching/(a.size+b.size-matching);
       if(score>bestScore){bestScore=score;best=slide;}
     }
   }
   return bestScore>=.84?best:null;
 }
 return null;
}
function autoCueSignature(slide){
 if(slide.song&&slide.section)return 'song:'+clean(slide.song)+':'+canonicalSongSection(slide.section);
 if(slide.reference)return 'scripture:'+clean(slide.reference);
 return 'text:'+clean(slide.text??slide.title??slide.id).slice(0,500);
}
export class PresentationDirector{
 constructor({adapter,clock=()=>Date.now(),cooldownMs=350}={}){
   if(!adapter||typeof adapter.show!=='function')throw new TypeError('Presentation output adapter required.');
   this.adapter=adapter;this.clock=clock;this.cooldownMs=Math.max(0,cooldownMs);
   this.deck=null;this.mode='manual';this.started=false;this.held=false;this.armed=false;
   this.index=0;this.lastTransition=-Infinity;this.seenIds=new Set();this.listeners=new Set();
   this.history=[];this.pendingOperations=0;this.queued=Promise.resolve();
   this.lastAutoSignature=null;this.lastAutoOccurrence=0;
   this.outputFaulted=false;this.outputFaultReason=null;
   this.recoveryPreview=false;
 }
 // A single causal command lane: native UI calls and observations must never
 // race one another or the deck pointer. Failure does not poison later tasks.
 enqueue(action){
   if(this.pendingOperations>=64)throw new Error('Presentation command queue is full.');
   this.pendingOperations++;
   const current=this.queued.then(action);
   this.queued=current.then(()=>undefined,()=>undefined);
   return current.finally(()=>{this.pendingOperations--;});
 }
 get busy(){return this.pendingOperations>0;}
 load(raw){
   // A deck must not replace the source while the native adapter is mid-call.
   if(this.busy)throw new Error('Presentation operation in progress; load after it finishes.');
   const next=validateDeck(raw);
   // A new deck is a new output authorization scope, even after a clean show.
   this.deck=next;this.index=0;this.started=false;this.mode='manual';this.held=false;
   this.armed=false;this.outputFaulted=false;this.outputFaultReason=null;
   this.recoveryPreview=false;
   this.lastTransition=-Infinity;this.seenIds.clear();this.history.length=0;
   this.lastAutoSignature=null;this.lastAutoOccurrence=0;
   this.notify();return this.snapshot();
 }
 unload(){
   if(this.busy)throw new Error('Presentation command in progress; stop before unloading.');
   if(this.started||this.armed)
     throw new Error('Stop and disarm the presentation before unloading its deck.');
   this.deck=null;this.index=0;this.mode='manual';this.held=false;
   this.armed=false;this.outputFaulted=false;this.outputFaultReason=null;
   this.recoveryPreview=false;this.lastTransition=-Infinity;
   this.seenIds.clear();this.history.length=0;
   this.lastAutoSignature=null;this.lastAutoOccurrence=0;
   this.notify();return this.snapshot();
 }
 // A crash checkpoint is a preview only. External native show() must never
 // execute while reconstructing this state.
 restore(raw,{index=0}={}){
   const loaded=this.load(raw);
   if(!Number.isInteger(index)||index<0||index>=loaded.slides.length)
     throw new Error('Recovery slide index is outside the deck.');
   this.index=index;this.held=true;this.recoveryPreview=true;
   this.mode='manual';this.started=false;this.armed=false;
   this.notify();return this.snapshot();
 }
 subscribe(listener){this.listeners.add(listener);return ()=>this.listeners.delete(listener);}
 notify(){const state=this.snapshot();for(const listener of this.listeners){try{listener(state);}catch{}}}
 snapshot(){
   return {title:this.deck?.title??null,theme:this.deck?.theme??'dark',slides:this.deck?.slides??[],current:this.deck?.slides[this.index]??null,
     index:this.deck?this.index:null,mode:this.mode,started:this.started,held:this.held,armed:this.armed,
     outputFaulted:this.outputFaulted,outputFaultReason:this.outputFaultReason,
     recoveryPreview:this.recoveryPreview,
     dryRun:!!this.adapter.external&&!this.armed,adapter:this.adapter.name??'unnamed',
     history:this.history.slice(-12)};
 }
 async readback(){
   return this.enqueue(async()=>{
     const expectedDeckIndex=this.deck?.slides?this.index:null;
     const slide=this.deck?.slides?.[this.index]??null;
     const expectedIndex=slide?.targetIndex??expectedDeckIndex;
     const expectedSlideId=slide?.id??null;
     const expectedPresentationId=slide?.presentationId??
       this.adapter.presentationId??null;
     if(typeof this.adapter.readback!=='function')
       return {supported:false,confirmed:false,source:this.adapter.name??'unknown',
         reason:'native_readback_unavailable',expectedIndex,expectedDeckIndex,expectedSlideId};
     const observed=await this.adapter.readback({expectedIndex,expectedSlideId,expectedPresentationId});
     const running=this.started&&(!this.adapter.external||this.armed);
     return {...observed,confirmed:running&&observed.confirmed===true,
       reason:this.outputFaulted?'output_fault':!running?'output_not_running':observed.confirmed?'matched':'output_mismatch',
       expectedIndex,expectedDeckIndex,expectedSlideId};
   });
 }
 async arm(enabled){
   return this.enqueue(async()=>{
     if(typeof enabled!=='boolean')throw new Error('Arm must be true or false.');
     if(enabled&&this.outputFaulted)throw new Error('External output fault: reload the deck before rearming.');
     this.armed=enabled;this.notify();return this.snapshot();
   });
 }
 async start(mode='assisted'){
   return this.enqueue(async()=>{
     if(!MODES.has(mode))throw new Error('Unknown presentation mode.');
     if(this.outputFaulted)throw new Error('External output fault: reload the deck before restarting.');
     if(this.started){
       // A repeated start from another host must never rewind the live show.
       if(mode!==this.mode)throw new Error('Presentation already running; use the mode command to change modes.');
       return this.snapshot();
     }
     if(!this.deck)throw new Error('Load a deck before starting.');
     // The initial native write and its independent readback share one
     // fail-closed boundary. A thrown show() may have already changed the
     // physical projection before its acknowledgment timed out.
     if(!this.adapter.external||this.armed){
       try{
         const receipt=await this.adapter.show(0,this.deck.slides[0],{reason:'start'});
         await this.verifyOutputReceipt(receipt,0,this.deck.slides[0]);
       }catch(error){
         // Treat every attempted external start without a verified outcome
         // as an uncertain commit. Queued starts/rearms must not replay it
         // until an explicitly authorized operator reloads/resynchronizes.
         if(this.adapter.external){
           this.started=false;this.held=true;this.armed=false;
           this.outputFaulted=true;this.outputFaultReason='native_start_unverified';
           this.notify(); // Push fault to the read-only viewer with unchanged index.
         }
         throw error;
       }
     }
     this.mode=mode;this.started=true;this.held=false;this.index=0;
     this.recoveryPreview=false;
     this.lastTransition=-Infinity;
     this.lastAutoSignature=null;this.lastAutoOccurrence=0;
     this.notify();return this.snapshot();
   });
 }
 async verifyOutputReceipt(receipt,expectedIndex,slide=null){
   if(receipt?.ok===false)throw new Error('External presentation output rejected the command.');
   if(this.adapter.external&&this.adapter.requiresReadback===true){
     if(typeof this.adapter.readback!=='function')
       throw new Error('External output requires readback but no readback method exists.');
     const expectedPresentationId=slide?.presentationId??this.adapter.presentationId??null;
     const expectedTargetIndex=slide?.targetIndex??expectedIndex;
     const result=await this.adapter.readback({expectedIndex:expectedTargetIndex,expectedPresentationId});
     if(result?.confirmed!==true||result?.index!==expectedTargetIndex)
       throw new Error('External presentation readback mismatch; slide change was not verified.');
   }
 }
 async moveTo(index,options={}){
   return this.enqueue(()=>this.applyMove(index,options));
 }
 async applyMove(index,{reason='operator',operation='goto'}={}){
   if(!this.deck||!this.started)throw new Error('Start the presentation first.');
   if(this.outputFaulted&&this.adapter.external)
     throw new Error('External output fault: reload the deck before another slide command.');
   if(!Number.isInteger(index)||index<0||index>=this.deck.slides.length)throw new Error('Slide index out of range.');
   if(index===this.index)return {changed:false,reason:'unchanged',slide:this.deck.slides[index]};
   const slide=this.deck.slides[index];
   if(!this.adapter.external||this.armed){
     try{
       // Native next/previous preserve slide-build semantics. An imported
       // setlist with a mapped target index requires a precise native goto.
       let receipt;
       if(operation==='next'&&slide.targetIndex===undefined&&typeof this.adapter.next==='function')
         receipt=await this.adapter.next(slide);
       else if(operation==='previous'&&slide.targetIndex===undefined&&typeof this.adapter.previous==='function')
         receipt=await this.adapter.previous(slide);
       else receipt=await this.adapter.show(index,slide,{reason});
       await this.verifyOutputReceipt(receipt,index,slide);
     }catch(error){
       // An ambiguous native write or readback leaves the physical output
       // unknowable. Never automatically retry, simulate a successful slide
       // change, or send another write until the owner resets the session.
       if(this.adapter.external){
         this.held=true;this.armed=false;this.outputFaulted=true;
         this.outputFaultReason='native_output_unverified';this.notify();
       }
       throw error;
     }
   }
   this.index=index;this.lastTransition=this.clock();
   if(reason==='operator'){this.lastAutoSignature=null;this.lastAutoOccurrence=0;}
   this.history.push({at:this.lastTransition,slideId:slide.id,reason});
   if(this.history.length>64)this.history.shift();
   this.notify();return {changed:true,slide,reason};
 }
 async command(input){
   return this.enqueue(async()=>{
     if(!input||typeof input!=='object')throw new Error('Command object required.');
     const action=input.action;
     // External output arming is an operator-only boundary exposed separately by
     // the host. Never accept it through an untrusted presentation command.
     if(action==='arm')throw new Error('External output cannot be armed by presentation_command.');
     if(action==='status')return {changed:false,reason:'status',state:this.snapshot()};
     if(action==='stop'){
       // Control-plane stop makes no native projector write. The last physical
       // frame may still be visible until the venue operator blanks it.
       const changed=this.started;
       this.started=false;this.held=true;this.armed=false;this.mode='manual';
       this.notify();
       return {changed,reason:'stopped',state:this.snapshot()};
     }
     if(action==='mode'){
       if(!MODES.has(input.mode))throw new Error('Unknown mode.');
       this.mode=input.mode;this.notify();
       return {changed:false,reason:'mode',state:this.snapshot()};
     }
     if(!this.started)throw new Error('Presentation must be running.');
     if(action==='hold'){
       this.held=true;this.notify();return {changed:false,reason:'held',state:this.snapshot()};
     }
     if(action==='resume'){
       if(this.outputFaulted)throw new Error('External output fault: reload the deck before resuming.');
       this.held=false;this.notify();return {changed:false,reason:'resumed',state:this.snapshot()};
     }
     if(action==='next')return this.applyMove(
       Math.min(this.index+1,this.deck.slides.length-1),{reason:'operator',operation:'next'});
     if(action==='previous')return this.applyMove(
       Math.max(this.index-1,0),{reason:'operator',operation:'previous'});
     if(action==='goto'){
       const index=input.index??this.deck.slides.findIndex(s=>s.id===input.id);
       return this.applyMove(index,{reason:'operator'});
     }
     throw new Error('Unsupported presentation command.');
   });
 }
 async ingest(event){
   return this.enqueue(async()=>{
     if(!event||typeof event!=='object'||!this.started)return {changed:false,reason:'not_running'};
     if(this.outputFaulted)return {changed:false,reason:'output_fault'};
     if(event.occurrence!==undefined&&(!Number.isSafeInteger(event.occurrence)||event.occurrence<1))
       return {changed:false,reason:'invalid_occurrence'};
     if(event.eventId!==undefined){
       const id=String(event.source??'unknown')+':'+String(event.eventId);
       if(this.seenIds.has(id))return {changed:false,reason:'duplicate'};
       this.seenIds.add(id);
       if(this.seenIds.size>512)this.seenIds.delete(this.seenIds.values().next().value);
     }
     const now=this.clock();
     if(Number.isFinite(event.timestamp)&&(now-event.timestamp>5000||event.timestamp-now>30000))
       return {changed:false,reason:'stale'};
     if(this.mode!=='automatic')return {changed:false,reason:'assisted_mode'};
     if(this.held)return {changed:false,reason:'held'};
     if(now-this.lastTransition<this.cooldownMs)return {changed:false,reason:'cooldown'};
     const slide=matchingSlide(event,this.deck.slides,this.index);
     if(!slide)return {changed:false,reason:'no_confident_match'};
     const signature=autoCueSignature(slide),occurrence=event.occurrence??0;
     if(signature===this.lastAutoSignature&&occurrence<=this.lastAutoOccurrence)
       return {changed:false,reason:'same_cue_still_active'};
     const result=await this.applyMove(slide.position,
       {reason:'auto:'+String(event.source??event.type)});
     if(result.changed){
       this.lastAutoSignature=signature;
       this.lastAutoOccurrence=occurrence;
     }
     return result;
   });
 }
}
