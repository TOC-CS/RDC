/**
 * Three output-specific Looks on ONE authoritative service cue.
 *
 * In-memory presentation UI appearance only. Does not arm projector,
 * microphone, camera, stream, OBS, MIDI or native app controls.
 * All destination/layer validation delegates to the same allowlist used
 * by the already verified worship packet compiler.
 */
import {validateWorshipLook} from './worship-looks.mjs';

const DESTINATIONS=Object.freeze(['audience','stage','broadcast']);
const clone=look=>Object.freeze({
 destination:look.destination,layout:look.layout,background:look.background,
 layers:Object.freeze([...look.layers])
});
export class WorshipLookController{
 constructor({onChange=()=>{}}={}){
  if(typeof onChange!=='function')throw new TypeError('Look state listener must be a function.');
  this.onChange=onChange;
  this.revision=0;
  this.looks=Object.fromEntries(DESTINATIONS.map(name=>
   [name,clone(validateWorshipLook(name))]));
 }
 get(destination){
  if(!DESTINATIONS.includes(destination))throw new Error('Unknown worship Look destination.');
  return this.looks[destination];
 }
 snapshot(){
  return Object.freeze({
   schema:'toc.worship.output-looks/v1',
   revision:this.revision,
   destinations:Object.freeze(DESTINATIONS.map(name=>this.get(name))),
   externalActionsPerformed:false
  });
 }
 set(destination,look){
  const next=clone(validateWorshipLook(destination,look));
  this.looks[destination]=next;
  this.revision++;
  const state=this.snapshot();
  try{this.onChange(state);}catch{/* The owner callback cannot undo the validated state. */}
  return state;
 }
 reset({restartRevision=false}={}){
  this.looks=Object.fromEntries(DESTINATIONS.map(name=>
   [name,clone(validateWorshipLook(name))]));
  this.revision=restartRevision?0:this.revision+1;
  const state=this.snapshot();
  try{this.onChange(state);}catch{}
  return state;
 }
}
