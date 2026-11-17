/**
 * Standalone rehearsal and stage-confidence timer. It is a pure control-plane
 * clock with no presentation, OBS, audio or MIDI side effects.
 *
 * The stage timeline deliberately cannot issue next-slide commands or
 * broadcast private timer labels in its public status.
 */
export class WorshipStageClock{
 constructor({clock=()=>performance.now()}={}){
  if(typeof clock!=='function')throw new TypeError('Monotonic clock function required.');
  this.clock=clock;
  this.label='';
  this.durationMs=0;
  this.started=false;
  this.paused=false;
  this.startAt=0;
  this.elapsedBeforePause=0;
  this.lastObserved=-Infinity;
 }
 now(){
  const time=this.clock();
  if(!Number.isFinite(time)||time<0||time<this.lastObserved)
   throw new Error('Monotonic timer clock moved backward or became invalid.');
  this.lastObserved=time;
  return time;
 }
 configure({label='',durationMs=0}={}){
  if(typeof label!=='string'||label.length>200)
   throw new Error('Invalid stage timer label.');
  if(!Number.isSafeInteger(durationMs)||durationMs<0||durationMs>86400000)
   throw new Error('Stage timer duration must be between zero and 24 hours.');
  this.label=label;
  this.durationMs=durationMs;
  this.started=false;
  this.paused=false;
  this.elapsedBeforePause=0;
  this.startAt=0;
  this.lastObserved=-Infinity;
  return this.snapshot();
 }
 start(){
  if(this.started&&!this.paused)return this.snapshot();
  if(this.paused)return this.resume();
  this.startAt=this.now();
  this.started=true;
  this.paused=false;
  this.elapsedBeforePause=0;
  return this.snapshot();
 }
 pause(){
  if(this.started&&!this.paused){
   const now=this.now();
   this.elapsedBeforePause+=now-this.startAt;
   this.paused=true;
  }
  return this.snapshot();
 }
 resume(){
  if(this.started&&this.paused){
   this.startAt=this.now();
   this.paused=false;
  }
  return this.snapshot();
 }
 reset(){
  this.started=false;this.paused=false;
  this.elapsedBeforePause=0;this.startAt=0;
  this.lastObserved=-Infinity;
  return this.snapshot();
 }
 snapshot(){
  const now=this.now();
  const elapsed=this.started?
   Math.max(0,this.elapsedBeforePause+(this.paused?0:now-this.startAt)):0;
  return Object.freeze({
   schema:'toc.worship-stage-clock/v1',
   label:this.label,
   durationMs:this.durationMs,
   elapsedMs:Math.round(elapsed),
   remainingMs:Math.max(0,Math.round(this.durationMs-elapsed)),
   overrunMs:Math.max(0,Math.round(elapsed-this.durationMs)),
   running:this.started&&!this.paused,
   paused:this.started&&this.paused,
   automaticAdvance:false
  });
 }
 publicStatus(){
  // Public status exposes no timing labels, stage notes or private instructions.
  return Object.freeze({timer:'private_stage_only',automaticAdvance:false});
 }
}
