import test from 'node:test';
import assert from 'node:assert/strict';
import {access} from 'node:fs/promises';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {homedir,platform} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';

const run=promisify(execFile);
const script=fileURLToPath(new URL('../scripts/verify-worship-visual.py',import.meta.url));
const python=process.env.PRESENTATION_VISUAL_PYTHON??
  join(homedir(),'RDC-Development','rdc','.venv','bin','python');
test('isolated Chromium and WebKit renders verify private confidence separation and transparent OBS graphics',
 {timeout:18000},async t=>{
  if(platform()!=='darwin')return t.skip('Native installed macOS WebKit/Chrome acceptance fixture required.');
  try{await access(python);}catch{return t.skip('Optional isolated Playwright Python environment unavailable.');}
  const {stdout}=await run(python,[script],{timeout:14000,maxBuffer:64000});
  const report=JSON.parse(stdout);
  assert.equal(report.passed,true);
  assert.equal(report.results.length,2);
  assert.deepEqual(report.results.map(x=>x.engine),['chromium','webkit']);
  assert.ok(report.results.every(x=>
    x.privateStageVisible&&x.audiencePrivateDataExcluded&&
    x.broadcastPrivateDataExcluded&&x.streamTransparentCorner));
  assert.equal(report.actualOBSConnected,false);
  assert.equal(report.physicalVenueAccepted,false);
});
