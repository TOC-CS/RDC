/**
 * Stage-only speaker, reader and singer prompt cursor.
 *
 * Never stores a public deck, requests microphone input, calls OBS, changes a
 * presentation slide or sends a BandMates MIDI/audio command. A separate
 * authenticated stage viewer supplies the actual operator boundary.
 */
const ROLES=new Set(['speaker','reader','singer']);
const EVENT_ID=/^[A-Za-z0-9._:-]{1,128}$/;
const clean=v=>String(v??'').normalize('NFKC').toLowerCase()
  .replace(/[^\p{L}\p{N}\s]/gu,' ').replace(/\s+/g,' ').trim();
const words=v=>new Set(clean(v).split(' ').filter(Boolean));
const matchScore=(a,b)=>{
 const x=words(a),y=words(b);
 if(x.size<3||y.size<3)return 0;
 if(clean(a).includes(clean(b))||clean(b).includes(clean(a)))return 1;
 const intersection=[...x].filter(w=>y.has(w)).length;
 return intersection/(x.size+y.size-intersection);
};
const contentLines=text=>String(text).split(/\r?\n/)
  .flatMap(row=>row.split(/(?<=[.!?])\s+(?=\p{Lu})/u))
  .map(line=>line.trim()).filter(Boolean).slice(0,240);

export class WorshipTeleprompter{
 constructor({clock=()=>Date.now()}={}){
  if(typeof clock!=='function')throw new TypeError('Private teleprompter clock required.');
  this.clock=clock;this.role='speaker';this.fontScale=1.3;
  this.scrollSpeed=1;this.mirrored=false;
  this.slideId=null;this.title='';this.section='';
  this.text='';this.notes='';this.lines=[];this.position=0;
  this.held=false;this.seen=new Map();
 }
 configure({role='speaker',fontScale=1.3,scrollSpeed=1,mirrored=false}={}){
  if(!ROLES.has(role))throw new Error('Invalid teleprompter role.');
  if(!Number.isFinite(fontScale)||fontScale<.8||fontScale>2.6)
   throw new Error('Invalid teleprompter font scale.');
  if(!Number.isFinite(scrollSpeed)||scrollSpeed<.25||scrollSpeed>3)
   throw new Error('Invalid teleprompter scroll speed.');
  if(typeof mirrored!=='boolean')throw new Error('Invalid teleprompter mirror setting.');
  if(this.role!==role){
   this.position=0;this.seen.clear();
  }
  this.role=role;this.fontScale=fontScale;
  this.scrollSpeed=scrollSpeed;this.mirrored=mirrored;
  this.lines=contentLines(this.role==='speaker'?(this.notes||this.text):this.text);
  return this.snapshot();
 }
 syncCue(cue){
  if(!cue||typeof cue!=='object'||Array.isArray(cue)||
   typeof cue.id!=='string'||!EVENT_ID.test(cue.id))
   throw new Error('Valid private stage cue ID required.');
  const text=cue.text??'',notes=cue.notes??'';
  if(typeof text!=='string'||typeof notes!=='string'||text.length>16000||notes.length>8000)
   throw new Error('Private teleprompter text is too long or invalid.');
  if(this.slideId!==cue.id){
   this.slideId=cue.id;this.position=0;this.seen.clear();
   this.held=false;
  }
  this.text=text;this.notes=notes;
  this.title=typeof cue.title==='string'?cue.title.slice(0,250):'';
  this.section=typeof cue.section==='string'?cue.section.slice(0,100):'';
  this.lines=contentLines(this.role==='speaker'?(notes||text):text);
  if(this.position>=this.lines.length)
   this.position=Math.max(0,this.lines.length-1);
  return this.snapshot();
 }
 follow({text,confidence,final,eventId,timestamp}={}){
  if(!this.slideId)return {changed:false,reason:'no_cue'};
  if(this.held)return {changed:false,reason:'held'};
  if(typeof text!=='string'||text.length>6000||!Number.isFinite(confidence)||
    confidence<.9||confidence>1||final!==true)
   return {changed:false,reason:'unconfirmed'};
  if(typeof eventId!=='string'||!EVENT_ID.test(eventId))
   return {changed:false,reason:'unverified_event_identity'};
  const now=this.clock();
  if(!Number.isFinite(now)||!Number.isFinite(timestamp)||
    timestamp<now-5000||timestamp>now+5000)
   return {changed:false,reason:'stale'};
  const signature=clean(text);
  const previous=this.seen.get(eventId);
  if(previous!==undefined){
   if(previous!==signature)throw new Error('Teleprompter speech event identity conflict.');
   return {changed:false,reason:'duplicate'};
  }
  if(this.seen.size>=512)this.seen.delete(this.seen.keys().next().value);
  this.seen.set(eventId,signature);
  let bestIndex=-1,bestScore=0;
  const end=Math.min(this.lines.length,this.position+4);
  for(let i=this.position;i<end;i++){
   const score=matchScore(text,this.lines[i]);
   if(score>bestScore){bestScore=score;bestIndex=i;}
  }
  if(bestIndex<0||bestScore<.84)return {changed:false,reason:'no_confident_match'};
  if(bestIndex<=this.position)return {changed:false,reason:'same_phrase'};
  this.position=bestIndex;
  return {changed:true,reason:'verified_phrase_follow',position:this.position};
 }
 next(){if(this.slideId&&this.lines.length)this.position=Math.min(this.position+1,this.lines.length-1);return this.snapshot();}
 previous(){if(this.slideId)this.position=Math.max(0,this.position-1);return this.snapshot();}
 hold(){this.held=true;return this.snapshot();}
 resume(){this.held=false;return this.snapshot();}
 clear(){
  this.slideId=null;this.title='';this.section='';this.text='';this.notes='';
  this.lines=[];this.position=0;this.held=false;this.seen.clear();
  return this.snapshot();
 }
 snapshot(){
  const loaded=this.slideId!==null;
  return Object.freeze({
   schema:'toc.worship.stage-teleprompt/v1',
   loaded,role:this.role,slideId:this.slideId,
   title:loaded?this.title:'',section:loaded?this.section:'',
   current:loaded?(this.lines[this.position]??''):'',
   next:loaded?(this.lines[this.position+1]??''):'',
   position:loaded?this.position:null,
   lineCount:loaded?this.lines.length:0,
   progress:loaded&&this.lines.length>1?
    Number((this.position/(this.lines.length-1)).toFixed(3)):0,
   held:this.held,mirrored:this.mirrored,fontScale:this.fontScale,
   scrollSpeed:this.scrollSpeed,automaticSlideAdvance:false,
   nativeOutputChanged:false
  });
 }
}
