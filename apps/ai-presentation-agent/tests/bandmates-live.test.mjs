import test from 'node:test';
import assert from 'node:assert/strict';
import {BandMatesLiveLink} from '../integrations/bandmates-live.mjs';
const values={
 '/api/band/status':{running:false,generation:0,activity:'stopped'},
 '/api/live/status':{running:false,status:'idle',hardwareOutputVerified:false},
 '/api/state':{protocol:'bandmates.control.v1',bandTitle:'Original Band',
   channels:[],session:{status:'offline'}}
};
function testLink(overrides={}){
 const paths=[];
 let called=0;
 const fetcher=async(raw,options)=>{
   const url=new URL(raw);called++;
   assert.equal(url.origin,'http://127.0.0.1:8746');
   assert.equal(options.method,'GET');
   assert.equal(options.redirect,'error');
   assert.equal(options.headers.Accept,'application/json');
   paths.push(url.pathname);
   return {ok:true,status:200,json:async()=>overrides[url.pathname]??values[url.pathname]};
 };
 return {link:new BandMatesLiveLink({fetcher,clock:()=>10000}),paths,getCalled:()=>called};
}
test('live BandMates API inspection cannot start or modify any MIDI, audio or band operations',async()=>{
 const {link,paths,getCalled}=testLink();
 const output=await link.inspect();
 assert.deepEqual(paths,['/api/band/status','/api/live/status','/api/state']);
 assert.equal(getCalled(),3);
 assert.equal(output.liveCompanionReachable,true);
 assert.equal(output.bandRunning,false);
 assert.equal(output.liveFollowingRunning,false);
 assert.equal(output.currentSection,null);
 assert.equal(output.presentationCueSent,false);
 assert.equal(output.reason,'bandmates_idle');
});
test('a running band does not become evidence for a chorus or verse without current-section data',async()=>{
 const {link}=testLink({'/api/band/status':{
   running:true,generation:2,tempo:120,activity:'playing',
   chord:'C',songDynamics:{section:'chorus',occurrence:3,stateKind:'planned'}
 }});
 const output=await link.inspect();
 assert.equal(output.bandRunning,true);
 assert.equal(output.nativeSectionSignalAvailable,false);
 assert.equal(output.currentSection,null);
 assert.equal(output.reason,'no_authoritative_current_song_section');
});
test('the live BandMates adapter only accepts a loopback owner endpoint',()=>{
 for(const url of [
   'https://example.com','http://8.8.8.8:8746',
   'http://192.168.2.1:8746',
   'http://user:pass@localhost:8746',
   'http://localhost:8746/state',
   'http://localhost:8746/?token=x',
   'http://localhost:8746/#fragment'
 ])assert.throws(()=>new BandMatesLiveLink({baseUrl:url}),/loopback/i);
});
test('BandMates source mismatch refuses to guess missing performance state',async()=>{
 const {link}=testLink({'/api/live/status':{status:'offline'}});
 await assert.rejects(()=>link.inspect(),/schema/i);
 assert.equal(link.pollCount,0);
});
test('unreachable BandMates host reports failure without mutating presentation state',async()=>{
 const link=new BandMatesLiveLink({fetcher:async()=>{throw new Error('connection refused');}});
 await assert.rejects(()=>link.inspect(),/connection refused/);
 assert.equal(link.last,null);
});
