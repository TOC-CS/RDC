import test from 'node:test';
import assert from 'node:assert/strict';
import {platform} from 'node:os';
import {verifyMacPresentationScripts} from '../scripts/verify-macos-app-scripts.mjs';

test('Mac presentation AppleScript compilation is reproducible without launching any app',async(t)=>{
 if(platform()!=='darwin')return t.skip('macOS only');
 const report=await verifyMacPresentationScripts();
 assert.equal(report.schema,'presentation.mac-script-check/v1');
 assert.equal(report.checked,8);
 assert.equal(report.passed,8);
 assert.equal(report.failed,0);
 assert.equal(report.liveAppExecutionVerified,false);
 assert.equal(report.visualOutputVerified,false);
});
test('Windows and Linux correctly report AppleScript compilation as not applicable',async()=>{
 const report=await verifyMacPresentationScripts({os:'win32'});
 assert.equal(report.checked,0);
 assert.equal(report.status,'not_applicable');
});
