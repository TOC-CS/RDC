import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const cli=fileURLToPath(new URL('../scripts/presentationctl.mjs',import.meta.url));
test('OBS status command is discovered without starting OBS or a Presentation Agent',()=>{
 const output=spawnSync(process.execPath,[cli,'--help'],{encoding:'utf8',timeout:3000});
 assert.equal(output.status,0,output.stderr);
 assert.match(output.stdout,/obs-status/);
});
test('OBS inspection rejects remote credentialed connection before any network request',()=>{
 const password='private-obs-test-password-do-not-print';
 const response=spawnSync(process.execPath,[cli,'obs-status'],{
   encoding:'utf8',timeout:3000,env:{
     ...process.env,OBS_WS_URL:'ws://example.com:4455/',
     OBS_WEBSOCKET_PASSWORD:password
   }});
 assert.notEqual(response.status,0);
 assert.match(response.stderr,/local WebSocket|status|OBS/i);
 assert.equal(response.stderr.includes(password),false);
 assert.equal(response.stdout.includes(password),false);
});
