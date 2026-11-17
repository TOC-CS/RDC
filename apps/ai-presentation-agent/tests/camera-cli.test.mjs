import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const script=fileURLToPath(new URL('../scripts/local-camera.mjs',import.meta.url));
test('camera observer help is usable without opening a physical camera',()=>{
 const r=spawnSync(process.execPath,[script,'--help'],{encoding:'utf8',timeout:3000,env:{PATH:process.env.PATH}});
 assert.equal(r.status,0,r.stderr);
 assert.match(r.stdout,/camera|device/i);
});
test('local camera observer never starts without local API credential',()=>{
 const r=spawnSync(process.execPath,[script,'--device','0'],{
  encoding:'utf8',timeout:3000,env:{PATH:process.env.PATH}});
 assert.notEqual(r.status,0);
 assert.match(r.stderr,/PRESENTATION_API_TOKEN/);
});
