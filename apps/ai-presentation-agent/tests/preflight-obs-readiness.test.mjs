import test from 'node:test';
import assert from 'node:assert/strict';
import {presentationPreflight} from '../src/preflight.mjs';

const baseline={
 readState:async()=>{throw new Error('managed service offline');},
 inspectDevice:async()=>({inspection:'read-only'}),
 inspectVenue:async()=>({schema:'toc.presentation.venue-output-readiness/v1',
   displays:[],audienceOutputs:{physicalProjectorAccepted:false},
   stageOutputs:{physicalStageMonitorAccepted:false},
   broadcastOutputs:{realOBSProgramVerified:false}}),
 inspectBandMates:async()=>{throw new Error('BandMates unavailable');}
};
test('local read-only OBS stream and Program state are visible in preflight without implying native/provider acceptance',async()=>{
 let reads=0;
 const result=await presentationPreflight({...baseline,
   inspectObs:async()=>{
     reads++;
     return {connected:true,source:'OBS WebSocket 5',programScene:'Sermon Camera',
       previewScene:'Worship Camera',studioModeEnabled:true,
       streamingActive:true,recordingActive:false,
       programReadbackMatchesSceneList:true,
       outputWritesPerformed:false,streamOrRecordingChanged:false,
       liveHardwareOrProviderAccepted:false};
   }
 });
 assert.equal(reads,1);
 assert.equal(result.checks.obs.connected,true);
 assert.equal(result.checks.obs.programScene,'Sermon Camera');
 assert.equal(result.checks.obs.previewScene,'Worship Camera');
 assert.equal(result.checks.obs.streamingActive,true);
 assert.equal(result.checks.obs.providerDeliveryVerified,false);
 assert.equal(result.allLiveAcceptanceVerified,false);
 assert.equal(result.nativeProjectionAccepted,false);
});
test('offline OBS is reported independently from projector, BandMates and local deck readiness',async()=>{
 const result=await presentationPreflight({...baseline,
   inspectObs:async()=>{throw new Error('OBS not running');}
 });
 assert.equal(result.checks.obs.connected,false);
 assert.equal(result.checks.obs.reason,'obs_unreachable');
 assert.equal(result.checks.venue.audienceOutputs.physicalProjectorAccepted,false);
 assert.equal(result.allLiveAcceptanceVerified,false);
});
test('OBS status must never be promoted to verified broadcast delivery by untrusted adapter fields',async()=>{
 const result=await presentationPreflight({...baseline,
   inspectObs:async()=>({
     connected:true,programScene:'Camera',previewScene:'Next Camera',
     streamingActive:true,recordingActive:true,
     liveHardwareOrProviderAccepted:true,outputWritesPerformed:true
   })
 });
 assert.equal(result.checks.obs.providerDeliveryVerified,false);
 assert.equal(result.allLiveAcceptanceVerified,false);
});
