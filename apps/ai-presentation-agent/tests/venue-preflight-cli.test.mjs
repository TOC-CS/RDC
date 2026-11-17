import test from 'node:test';
import assert from 'node:assert/strict';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
import {presentationPreflight} from '../src/preflight.mjs';
const exec=promisify(execFile);
const cli=fileURLToPath(new URL('../scripts/presentationctl.mjs',import.meta.url));

test('independent RDC viewer CLI provides a read-only connected display inventory command',async()=>{
 const {stdout}=await exec(process.execPath,[cli,'--help'],{timeout:2500});
 assert.match(stdout,/venue-readiness/);
});
test('preflight carries physical display state separately from software/browser capability',async()=>{
 const venue={
   schema:'toc.presentation.venue-output-readiness/v1',
   displays:[{id:'display-1',online:true,kind:'internal',primary:true,
     physicallyQualifiedAsAudienceProjector:false}],
   audienceOutputs:{softwareBrowserAvailable:true,physicalProjectorAccepted:false},
   stageOutputs:{privateConfidenceSoftwareAvailable:true,physicalStageMonitorAccepted:false},
   broadcastOutputs:{transparentBrowserOverlaySoftwareAvailable:true,realOBSProgramVerified:false}
 };
 const status=await presentationPreflight({
   readState:async()=>{throw Error('not running');},
   inspectDevice:async()=>({inspection:'read-only'}),
   inspectVenue:async()=>venue,
   inspectBandMates:async()=>{throw Error('not running');}
 });
 assert.deepEqual(status.checks.venue,venue);
 assert.equal(status.nativeProjectionAccepted,false);
 assert.equal(status.allLiveAcceptanceVerified,false);
});
test('real connected local venue inventory must not expose monitor serials, names or unlock physical outputs',async()=>{
 const {stdout}=await exec(process.execPath,[cli,'venue-readiness'],{timeout:12000,maxBuffer:65536});
 const report=JSON.parse(stdout);
 assert.equal(report.schema,'toc.presentation.venue-output-readiness/v1');
 assert.equal(report.externalHardwareWritesEnabled,false);
 assert.equal(report.audienceOutputs.physicalProjectorAccepted,false);
 assert.equal(report.stageOutputs.physicalStageMonitorAccepted,false);
 assert.ok(report.displays.length>=1);
 for(const value of report.displays){
   assert.equal('serial' in value,false);
   assert.equal('name' in value,false);
   assert.equal('edid' in value,false);
 }
});
