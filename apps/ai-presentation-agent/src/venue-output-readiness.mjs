import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {access} from 'node:fs/promises';
import {platform as systemPlatform} from 'node:os';

const exec=promisify(execFile);
const drivers={
 ndi:['/Library/Frameworks/NDI.framework',
      '/Library/Application Support/NewTek/NDI'],
 sdi:['/Library/Frameworks/DeckLinkAPI.framework',
      '/Applications/Blackmagic Desktop Video']
};
const safePixels=value=>{
 if(typeof value!=='string')return null;
 return /^\d{3,5} x \d{3,5}$/.test(value)?value:null;
};
export async function venueOutputReadiness({
 platform=systemPlatform(),
 getDisplayJson=async()=>{
   const {stdout}=await exec('/usr/sbin/system_profiler',['-json','SPDisplaysDataType'],{
     timeout:9000,maxBuffer:1024*1024,encoding:'utf8'
   });
   return JSON.parse(stdout);
 },
 exists=async(path)=>{try{await access(path);return true;}catch{return false;}},
}={}){
 const result={
   schema:'toc.presentation.venue-output-readiness/v1',
   platform,inspection:'read-only',
   displays:[],
   audienceOutputs:{softwareBrowserAvailable:true,physicalProjectorAccepted:false},
   stageOutputs:{privateConfidenceSoftwareAvailable:true,physicalStageMonitorAccepted:false},
   broadcastOutputs:{transparentBrowserOverlaySoftwareAvailable:true,realOBSProgramVerified:false},
   ndi:{driverCandidateFound:false,activeSourceVerified:false,qualified:false},
   sdi:{driverCandidateFound:false,connectedOutputVerified:false,qualified:false},
   externalHardwareWritesEnabled:false,
   operatorApprovalRequired:true,
   acceptance:'Hardware, cabling, output routing and independent video readback are required before qualifying a venue.'
 };
 if(platform!=='darwin')return result;
 let data;
 try{data=await getDisplayJson();}
 catch{
   return {...result,inventoryError:'display_inventory_unavailable'};
 }
 if(!Array.isArray(data?.SPDisplaysDataType))
   return {...result,inventoryError:'display_inventory_schema_invalid'};
 let sequence=0;
 for(const gpu of data.SPDisplaysDataType.slice(0,16)){
   for(const item of (Array.isArray(gpu?.spdisplays_ndrvs)?gpu.spdisplays_ndrvs:[]).slice(0,16)){
     sequence++;
     // Keep OS display serials, EDIDs and device fingerprints out of
     // public diagnostics. A visible display is not a verified projector.
     result.displays.push({
       id:'display-'+String(sequence),
       online:item?.spdisplays_online==='spdisplays_yes',
       kind:item?.spdisplays_connection_type==='spdisplays_internal'?'internal':'external_or_unknown',
       nativePixels:safePixels(item?._spdisplays_pixels),
       primary:item?.spdisplays_main==='spdisplays_yes',
       physicallyQualifiedAsAudienceProjector:false,
       physicallyQualifiedAsStageConfidence:false
     });
   }
 }
 const installed=async list=>{
   for(const candidate of list)if(await exists(candidate))return true;
   return false;
 };
 result.ndi.driverCandidateFound=await installed(drivers.ndi);
 result.sdi.driverCandidateFound=await installed(drivers.sdi);
 return result;
}
