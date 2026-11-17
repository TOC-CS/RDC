import test from 'node:test';
import assert from 'node:assert/strict';
import {WorshipStageClock} from '../src/worship-timing.mjs';

test('private stage countdown uses supplied monotonic clock and never advances slides',()=>{
 let now=1000,commands=0;
 const timer=new WorshipStageClock({clock:()=>now});
 timer.configure({label:'Pastor sermon',durationMs:180000});
 assert.equal(timer.snapshot().remainingMs,180000);
 timer.start();
 now+=60000;
 const value=timer.snapshot();
 assert.equal(value.remainingMs,120000);
 assert.equal(value.elapsedMs,60000);
 assert.equal(value.running,true);
 now+=130000;
 assert.equal(timer.snapshot().remainingMs,0);
 assert.equal(timer.snapshot().overrunMs,10000);
 assert.equal(commands,0);
});
test('private stage countdown pause, resume, reset and zero duration are deterministic',()=>{
 let now=5000;
 const timer=new WorshipStageClock({clock:()=>now});
 timer.configure({label:'Pre-service countdown',durationMs:30000});
 timer.start();
 now+=12000;
 timer.pause();
 now+=50000;
 assert.equal(timer.snapshot().remainingMs,18000);
 timer.resume();
 now+=1000;
 assert.equal(timer.snapshot().remainingMs,17000);
 timer.reset();
 assert.equal(timer.snapshot().running,false);
 assert.equal(timer.snapshot().remainingMs,30000);
});
test('private timer tokens and arbitrary notes never enter its public-safe status',()=>{
 let now=0;
 const timer=new WorshipStageClock({clock:()=>now});
 timer.configure({label:'PRIVATE PASTOR PRAYER',durationMs:45000});
 timer.start();
 const publicStatus=timer.publicStatus();
 assert.equal(JSON.stringify(publicStatus).includes('PRIVATE'),false);
 assert.equal(Object.hasOwn(publicStatus,'label'),false);
 assert.equal(publicStatus.automaticAdvance,false);
});
test('duration, labels and monotonic clock rollback are validated',()=>{
 let now=2000;
 const timer=new WorshipStageClock({clock:()=>now});
 assert.throws(()=>timer.configure({durationMs:-1,label:'Invalid'}),/duration/i);
 assert.throws(()=>timer.configure({durationMs:86400001,label:'Invalid'}),/duration/i);
 assert.throws(()=>timer.configure({durationMs:1000,label:'a'.repeat(201)}),/label/i);
 timer.configure({label:'Service',durationMs:2000});
 timer.start();
 now=1000;
 assert.throws(()=>timer.snapshot(),/clock|monotonic/i);
});
test('privacy-sensitive clock remains independent from presentation mode',()=>{
 const timer=new WorshipStageClock();
 const keys=Object.keys(timer.snapshot());
 assert.ok(!keys.includes('slideIndex'));
 assert.ok(!keys.includes('nextSlide'));
 assert.ok(!keys.includes('action'));
});
