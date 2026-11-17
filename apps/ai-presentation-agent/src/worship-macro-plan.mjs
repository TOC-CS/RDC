/**
 * Offline professional worship service transition rehearsal planner.
 *
 * This is deliberately a PREVIEW, never an executor. OBS Program/Preview,
 * stream/record, public graphics and private stage actions are independent
 * production privileges. Nothing is sent to a device, a plugin or a service.
 */
const ACTIONS=Object.freeze({
 hold:{target:'presentation',grant:null,critical:false,keys:[]},
 'show-slide':{target:'presentation',grant:null,critical:false,keys:['slideId']},
 'clear-broadcast-graphics':{target:'broadcast',grant:'broadcast.clear-graphics',critical:false,keys:[]},
 'set-obs-preview':{target:'obs-preview',grant:'obs.preview',critical:false,keys:['scene']},
 'set-obs-program':{target:'obs-program',grant:'obs.program',critical:true,keys:['scene']},
 'stage-message':{target:'stage-private',grant:'stage.message',critical:false,keys:['text']},
 'start-stream':{target:'obs-stream',grant:'obs.start-stream',critical:true,keys:[]},
 'stop-stream':{target:'obs-stream',grant:'obs.stop-stream',critical:true,keys:[]},
 'start-record':{target:'obs-record',grant:'obs.start-record',critical:true,keys:[]},
 'stop-record':{target:'obs-record',grant:'obs.stop-record',critical:true,keys:[]},
 'show-scripture-reference':{target:'presentation',grant:null,critical:false,keys:['reference','translation']}
});
const isPlain=v=>v&&typeof v==='object'&&!Array.isArray(v)&&
  [Object.prototype,null].includes(Object.getPrototypeOf(v));
const referencePattern=/^[1-3]?\s?[A-Za-z][A-Za-z ]+\s+\d{1,3}:\d{1,3}(?:-\d{1,3})?$/;
const checkText=(value,label,limit)=>{
 if(typeof value!=='string'||!value.trim()||value.length>limit||
   /[\u0000-\u001F]/.test(value))throw new Error('Invalid '+label+'.');
 return value.trim();
};
export function prepareWorshipMacro(macro,{deck}={}){
 if(!isPlain(macro)||!Object.keys(macro).every(k=>['name','steps'].includes(k)))
   throw new Error('Invalid worship macro object.');
 const name=checkText(macro.name,'macro name',120);
 if(!Array.isArray(macro.steps)||macro.steps.length<1||macro.steps.length>30)
   throw new Error('Worship macro requires 1 to 30 steps.');
 if(!deck||!Array.isArray(deck.slides)||deck.slides.length<1||deck.slides.length>1000)
   throw new Error('A loaded presentation deck is required for safe preview.');
 const slideIds=new Set(deck.slides.map(s=>s?.id).filter(s=>typeof s==='string'));
 const requiredGrants=new Set();
 const steps=macro.steps.map((step,index)=>{
   if(!isPlain(step)||typeof step.action!=='string'||!Object.hasOwn(ACTIONS,step.action))
     throw new Error('Unknown worship macro action.');
   const spec=ACTIONS[step.action];
   const allowed=new Set(['action',...spec.keys]);
   for(const key of Object.keys(step))if(!allowed.has(key))
     throw new Error('Unknown worship macro action field: '+key);
   const safe={sequence:index+1,action:step.action,target:spec.target,
     critical:spec.critical,previewOnly:true,
     operatorApprovalRequired:spec.grant!==null,
     ...spec.grant?{requiredGrant:spec.grant}:{}
   };
   if(spec.grant)requiredGrants.add(spec.grant);
   if(step.action==='show-slide'){
     const slideId=checkText(step.slideId,'slide ID',80);
     if(!slideIds.has(slideId))throw new Error('Unknown worship macro slide ID.');
     safe.slideId=slideId;
   }
   if(['set-obs-preview','set-obs-program'].includes(step.action))
     safe.scene=checkText(step.scene,'OBS scene name',140);
   if(step.action==='stage-message'){
     checkText(step.text,'private stage message',2000);
     // A public owner-run rehearsal plan must not carry the private body.
     safe.privatePayloadRequired=true;
   }
   if(step.action==='show-scripture-reference'){
     const reference=checkText(step.reference,'Scripture reference',130);
     if(!referencePattern.test(reference))throw new Error('Invalid Scripture reference.');
     if(step.translation!=='NKJV')throw new Error('Unsupported Scripture translation. Only NKJV reference-only previews are supported.');
     safe.reference=reference;safe.translation='NKJV';
     safe.authorizedVerseTextIncluded=false;
   }
   return Object.freeze(safe);
 });
 return Object.freeze({
   schema:'toc.worship.macro-preview/v1',
   name,
   steps:Object.freeze(steps),
   requiredGrants:Object.freeze([...requiredGrants]),
   executionAllowed:false,applied:false,
   nativeApplicationModified:false,streamingOrRecordingChanged:false,
   actualOutputAccepted:false
 });
}
