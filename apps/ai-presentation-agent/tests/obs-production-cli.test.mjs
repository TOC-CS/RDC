import test from 'node:test';
import assert from 'node:assert/strict';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
const exec=promisify(execFile);
const cli=fileURLToPath(new URL('../scripts/presentationctl.mjs',import.meta.url));
test('owner RDC CLI advertises enhanced read-only OBS production diagnostics',async()=>{
 const {stdout}=await exec(process.execPath,[cli,'--help'],{timeout:2500});
 assert.match(stdout,/obs-production-status/);
});
test('unreachable OBS production monitor fails cleanly with no credentials or desktop UI activation',async()=>{
 const secret='PRIVATE_OBS_FIXTURE_NOT_FOR_OUTPUT';
 await assert.rejects(
   ()=>exec(process.execPath,[cli,'obs-production-status'],{
     timeout:4000,env:{...process.env,OBS_WS_URL:'ws://127.0.0.1:65431/',
       OBS_WEBSOCKET_PASSWORD:secret}
   }),
   error=>{
     assert.equal(error.code,2);
     assert.equal(String(error.stderr).includes(secret),false);
     assert.match(String(error.stderr),/OBS|connection|unavailable/i);
     return true;
   }
 );
});
