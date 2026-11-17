import {BandMatesLiveLink} from '../integrations/bandmates-live.mjs';
import {presentationReadiness} from './readiness.mjs';
import {venueOutputReadiness} from './venue-output-readiness.mjs';
import {OBSReadOnlyMonitor} from './obs-monitor.mjs';
import {readPrivateState} from './managed-state.mjs';

/**
 * Safe readiness aggregator for RDC/AI hosts.
 * Never starts/stops a show, takes desktop focus, opens a microphone/camera,
 * sends MIDI, selects output, or arms a third-party presentation app.
 */
export async function presentationPreflight({
  inspectBandMates=()=>new BandMatesLiveLink().inspect(),
  inspectDevice=presentationReadiness,
  inspectVenue=venueOutputReadiness,
  inspectObs=()=>new OBSReadOnlyMonitor({
    url:process.env.OBS_WS_URL??'ws://127.0.0.1:4455/',
    password:process.env.OBS_WEBSOCKET_PASSWORD??'',
    timeoutMs:1500,includeProductionMetrics:true
  }).inspect(),
  readState=readPrivateState,
  fetcher=fetch,
}={}){
 const report={
   schema:'toc.presentation.preflight/v1',
   checks:{presentation:null,bandmates:null,device:null,venue:null,obs:null},
   canPerformLocalOfflineDeck:false,
   canFollowNativeBandMatesSongSections:false,
   nativeProjectionAccepted:false,
   simulatedEvidenceDoesNotQualifyHardware:true,
   allLiveAcceptanceVerified:false
 };
 // Failures are per independent component so an offline BandMates API does not
 // hide a healthy Presentation Agent and never trigger recovery writes.
 try{
   const state=await readState();
   const url='http://127.0.0.1:'+state.port;
   const request=async path=>{
     const response=await fetcher(url+path,{
       headers:{Authorization:'Bearer '+state.token},
       method:'GET',redirect:'error',signal:AbortSignal.timeout(2200)
     });
     if(!response.ok)throw new Error('Local Presentation Agent status '+response.status);
     return response.json();
   };
   const [snapshot,readiness]=await Promise.all([
     request('/v1/status'),request('/v1/readiness')
   ]);
   if(!snapshot||!readiness||typeof snapshot.started!=='boolean')
     throw new Error('Invalid Presentation Agent session response.');
   report.checks.presentation={
     connected:true,started:snapshot.started,mode:snapshot.mode??'manual',
     held:snapshot.held===true,armed:snapshot.armed===true,
     outputFaulted:snapshot.outputFaulted===true,
     adapter:snapshot.adapter??'unknown',
     slidesLoaded:Array.isArray(snapshot.slides)?snapshot.slides.length:0,
     slideIndex:Number.isSafeInteger(snapshot.index)?snapshot.index:null
   };
   report.canPerformLocalOfflineDeck=true;
   report.checks.device=readiness;
 }catch(error){
   report.checks.presentation={connected:false,reason:'local_agent_unreachable'};
   // Local device inventory is independent of the managed server.
   try{report.checks.device=await inspectDevice();}
   catch{report.checks.device={inspection:'unavailable'};}
 }
 try{
   const band=await inspectBandMates();
   report.checks.bandmates={
     connected:band.liveCompanionReachable===true,
     running:band.bandRunning===true,
     following:band.liveFollowingRunning===true,
     sectionSignalAvailable:band.nativeSectionSignalAvailable===true,
     cuePublished:band.presentationCueSent===true,
     reason:band.reason??null
   };
 }catch{report.checks.bandmates={connected:false,reason:'bandmates_unreachable'};}
 // Display and NDI/SDI inventory is independent of the managed control API.
 // A connected screen or installed driver never qualifies a physical projector.
 try{report.checks.venue=await inspectVenue();}
 catch{report.checks.venue={
   schema:'toc.presentation.venue-output-readiness/v1',
   inspection:'unavailable',inventoryError:'venue_inventory_unavailable',
   externalHardwareWritesEnabled:false,
   audienceOutputs:{physicalProjectorAccepted:false},
   stageOutputs:{physicalStageMonitorAccepted:false},
   broadcastOutputs:{realOBSProgramVerified:false}
 };}
 // OBS Program, Preview and stream/record status are an independent
 // read-only production system. A correct local scene is never provider proof.
 try{
   const obs=await inspectObs();
   if(!obs||obs.connected!==true)throw new Error('OBS status not verified.');
   report.checks.obs={
     connected:true,programScene:obs.programScene??null,
     previewScene:obs.previewScene??null,
     studioModeEnabled:obs.studioModeEnabled===true,
     programReadbackConfirmed:obs.programReadbackMatchesSceneList===true,
     streamingActive:obs.streamingActive===true,
     streamReconnecting:obs.streamReconnecting===true,
     recordingActive:obs.recordingActive===true,
     renderDropPercent:obs.statistics?.renderDropPercent??null,
     outputDropPercent:obs.statistics?.outputDropPercent??null,
     providerDeliveryVerified:false,
     streamingOrRecordingChangedByPreflight:false
   };
 }catch{
   report.checks.obs={
     connected:false,reason:'obs_unreachable',
     providerDeliveryVerified:false,
     streamingOrRecordingChangedByPreflight:false
   };
 }
 // Song-following requires an actual section feed, not just a connected app.
 report.canFollowNativeBandMatesSongSections=
   report.checks.presentation?.connected===true&&
   report.checks.bandmates?.connected===true&&
   report.checks.bandmates?.running===true&&
   report.checks.bandmates?.sectionSignalAvailable===true;
 return report;
}
