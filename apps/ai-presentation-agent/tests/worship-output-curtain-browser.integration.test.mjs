import test from 'node:test';
import assert from 'node:assert/strict';
import {homedir,platform} from 'node:os';
import {access} from 'node:fs/promises';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';

const run=promisify(execFile);
const script=fileURLToPath(new URL('../scripts/verify-worship-output-curtain.py',import.meta.url));
const python=process.env.PRESENTATION_VISUAL_PYTHON??
 join(homedir(),'RDC-Development','rdc','.venv','bin','python');
test('Chromium and WebKit independently black audience HTML, clear broadcast and stage without native/OBS actions',
 {timeout:22000},async t=>{
  if(platform()!=='darwin')return t.skip('Mac browser runtime required.');
  try{await access(python);}catch{return t.skip('Optional local visual test engine unavailable.');}
  const {stdout}=await run(python,[script],{timeout:18000,maxBuffer:65536});
  const result=JSON.parse(stdout);
  assert.equal(result.passed,true);
  assert.equal(result.nativeProjectorBlanked,false);
  assert.equal(result.obsSceneOrStreamChanged,false);
  assert.deepEqual(result.engines.map(x=>x.engine),['chromium','webkit']);
  assert.ok(result.engines.every(x=>
    x.audienceOpaqueBlackVerified&&x.broadcastClearedWithoutAudienceChange&&
    x.stagePrivateDataClearedAndRestored&&
    x.privateInformationExcludedFromPublicOutputs&&x.recoveredWithoutMovingCue));
});
