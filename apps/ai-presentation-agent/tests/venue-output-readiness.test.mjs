import test from 'node:test';
import assert from 'node:assert/strict';
import {venueOutputReadiness} from '../src/venue-output-readiness.mjs';

test('read-only macOS display report strips serial and vendor identifiers',async()=>{
 const result=await venueOutputReadiness({
   platform:'darwin',
   getDisplayJson:async()=>({SPDisplaysDataType:[{
     _name:'GPU PRIVATE',
     spdisplays_ndrvs:[{
       _name:'My Confidential Monitor',
       '_spdisplays_display-serial-number':'VERY_SECRET_SERIAL_NUMBER',
       _spdisplays_pixels:'3200 x 1800',
       spdisplays_connection_type:'spdisplays_internal',
       spdisplays_online:'spdisplays_yes',
       spdisplays_main:'spdisplays_yes'
     }]
   }]}),
   exists:async()=>false
 });
 assert.equal(result.displays.length,1);
 assert.equal(result.displays[0].kind,'internal');
 assert.equal(result.displays[0].nativePixels,'3200 x 1800');
 assert.equal(result.displays[0].physicallyQualifiedAsAudienceProjector,false);
 assert.ok(!JSON.stringify(result).includes('VERY_SECRET_SERIAL_NUMBER'));
 assert.ok(!JSON.stringify(result).includes('GPU PRIVATE'));
 assert.equal(result.ndi.qualified,false);
 assert.equal(result.sdi.qualified,false);
});
test('NDI/SDI driver file presence cannot be mistaken for active qualified video output',async()=>{
 const result=await venueOutputReadiness({
   platform:'darwin',
   getDisplayJson:async()=>({SPDisplaysDataType:[]}),
   exists:async()=>true
 });
 assert.equal(result.ndi.driverCandidateFound,true);
 assert.equal(result.sdi.driverCandidateFound,true);
 assert.equal(result.ndi.qualified,false);
 assert.equal(result.sdi.qualified,false);
 assert.equal(result.externalHardwareWritesEnabled,false);
});
test('no machine access or connected output still yields a safe unsupported/readiness report',async()=>{
 const noMac=await venueOutputReadiness({platform:'win32'});
 assert.equal(noMac.displays.length,0);
 assert.equal(noMac.ndi.qualified,false);
 const failed=await venueOutputReadiness({
   platform:'darwin',getDisplayJson:async()=>{throw Error('OS unreachable');}
 });
 assert.equal(failed.inventoryError,'display_inventory_unavailable');
 assert.equal(failed.audienceOutputs.physicalProjectorAccepted,false);
});
