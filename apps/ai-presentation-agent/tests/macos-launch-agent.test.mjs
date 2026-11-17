import test from 'node:test';
import assert from 'node:assert/strict';
import {renderLaunchAgentPlist} from '../scripts/install-launch-agent.mjs';

test('persistent background service starts only local private managed server with all external outputs disarmed',()=>{
 const plist=renderLaunchAgentPlist({
  projectRoot:'/Users/example/RDC-Development/workspace/AI-Presentation-Agent',
  home:'/Users/example',nodePath:'/opt/homebrew/opt/node@24/bin/node'
 });
 assert.match(plist,/com\.toc\.ai-presentation-agent/);
 assert.match(plist,/KeepAlive/);
 assert.match(plist,/RunAtLoad/);
 assert.match(plist,/managed-server\.mjs/);
 assert.match(plist,/PRESENTATION_AGENT_STATE_DIR/);
 assert.doesNotMatch(plist,/PRESENTATION_ALLOW_EXTERNAL_CONTROL/);
 assert.doesNotMatch(plist,/local-microphone|local-camera|BandMates.*\.app/);
});
test('service XML escapes path characters so LaunchAgents cannot be corrupted by directory names',()=>{
 const plist=renderLaunchAgentPlist({
  projectRoot:'/Users/Test & More/AI <Agent>',
  home:'/Users/Test & More',
  nodePath:'/opt/homebrew/bin/node'
 });
 assert.ok(plist.includes('Test &amp; More'));
 assert.ok(plist.includes('AI &lt;Agent&gt;'));
 assert.ok(!plist.includes('AI <Agent>'));
});
test('service generator refuses relative paths and potentially dangerous launch labels',()=>{
 assert.throws(()=>renderLaunchAgentPlist({
  projectRoot:'./not-absolute',home:'/Users/example',nodePath:'/usr/bin/node'
 }),/absolute|path/i);
 assert.throws(()=>renderLaunchAgentPlist({
  projectRoot:'/Users/example/project',home:'/',nodePath:'/usr/bin/node'
 }),/home|unsafe/i);
});
