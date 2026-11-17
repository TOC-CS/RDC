/**
 * Presentation-only output curtains. One source cue continues underneath
 * independently hidden public overlays, audience blackout and stage clear.
 *
 * These flags affect ONLY the local HTML/SSE presentation outputs. Native
 * projector hardware, OBS Program, streaming and recording are not touched.
 */
const DESTINATIONS=Object.freeze(['audience','stage','broadcast']);
const MODES=Object.freeze({
 audience:new Set(['visible','clear','blank']),
 stage:new Set(['visible','clear']),
 broadcast:new Set(['visible','clear'])
});
export class WorshipOutputVisibility{
 constructor({onChange=()=>{}}={}){
   if(typeof onChange!=='function')
     throw new TypeError('Output state listener must be a function.');
   this.onChange=onChange;this.revision=0;
   this.visibility=Object.fromEntries(DESTINATIONS.map(d=>[d,'visible']));
 }
 get(destination){
   if(!DESTINATIONS.includes(destination))throw new Error('Unknown worship output destination.');
   return this.visibility[destination];
 }
 snapshot(){
   return Object.freeze({
     schema:'toc.worship.output-visibility/v1',
     revision:this.revision,
     outputs:Object.freeze(DESTINATIONS.map(d=>Object.freeze({
       destination:d,mode:this.get(d)
     }))),
     nativeDisplayWritesPerformed:false,
     obsSceneChanged:false,
     streamOrRecordChanged:false
   });
 }
 set(destination,mode){
   if(!DESTINATIONS.includes(destination))
     throw new Error('Unknown worship output destination.');
   if(!MODES[destination].has(mode))
     throw new Error('Visibility mode not allowed for '+destination+'.');
   if(this.visibility[destination]===mode)return this.snapshot();
   this.visibility[destination]=mode;this.revision++;
   const state=this.snapshot();
   try{this.onChange(state);}catch{}
   return state;
 }
 reset({restartRevision=false}={}){
   this.visibility=Object.fromEntries(DESTINATIONS.map(d=>[d,'visible']));
   this.revision=restartRevision?0:this.revision+1;
   const state=this.snapshot();
   try{this.onChange(state);}catch{}
   return state;
 }
}
