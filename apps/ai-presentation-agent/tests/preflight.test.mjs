import test from 'node:test';
import assert from 'node:assert/strict';
import {presentationPreflight} from '../src/preflight.mjs';

test('preflight reports real local app vs BandMates section availability without claiming physical acceptance',async()=>{
 const calls=[];
 const report=await presentationPreflight({
   readState:async()=>({port:45222,token:'do-not-reveal-this-private-bearer'}),
   fetcher:async(url,opts)=>{
     calls.push({url,method:opts.method,authorization:opts.headers.Authorization});
     const isReadiness=url.endsWith('/v1/readiness');
     return {ok:true,json:async()=>isReadiness?
       {inspection:'read-only',appReadiness:{keynote:{installed:true,running:false}}}:
       {started:false,mode:'manual',held:false,armed:false,
        adapter:'memory',slides:[],index:null,outputFaulted:false}};
   },
   inspectBandMates:async()=>({
     liveCompanionReachable:true,bandRunning:false,liveFollowingRunning:false,
     nativeSectionSignalAvailable:false,reason:'bandmates_idle'
   })
 });
 assert.equal(report.checks.presentation.connected,true);
 assert.equal(report.checks.bandmates.connected,true);
 assert.equal(report.canFollowNativeBandMatesSongSections,false);
 assert.equal(report.nativeProjectionAccepted,false);
 assert.equal(report.allLiveAcceptanceVerified,false);
 assert.equal(JSON.stringify(report).includes('do-not-reveal'),false);
 assert.deepEqual(calls.map(c=>new URL(c.url).pathname).sort(),['/v1/readiness','/v1/status']);
 assert.ok(calls.every(c=>c.method==='GET'));
});
test('preflight preserves independent device and band status when managed agent is offline',async()=>{
 const report=await presentationPreflight({
   readState:async()=>{throw Error('not running');},
   inspectDevice:async()=>({inspection:'read-only'}),
   inspectBandMates:async()=>({
     liveCompanionReachable:true,bandRunning:true,liveFollowingRunning:false,
     nativeSectionSignalAvailable:false,reason:'no_authoritative_current_song_section'
   })
 });
 assert.equal(report.checks.presentation.connected,false);
 assert.equal(report.checks.device.inspection,'read-only');
 assert.equal(report.checks.bandmates.running,true);
 assert.equal(report.canPerformLocalOfflineDeck,false);
 assert.equal(report.canFollowNativeBandMatesSongSections,false);
});
test('preflight never treats a BandMates transport error as permission to alter live state',async()=>{
 const report=await presentationPreflight({
   readState:async()=>{throw Error('not running');},
   inspectDevice:async()=>({inspection:'read-only'}),
   inspectBandMates:async()=>{throw Error('network unreachable');}
 });
 assert.equal(report.checks.bandmates.connected,false);
 assert.equal(report.checks.bandmates.reason,'bandmates_unreachable');
 assert.equal(report.nativeProjectionAccepted,false);
});
