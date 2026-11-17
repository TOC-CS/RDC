import test from 'node:test';
import assert from 'node:assert/strict';
import {platform,homedir} from 'node:os';
import {access} from 'node:fs/promises';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';

const exec=promisify(execFile);
const script=fileURLToPath(new URL('../scripts/verify-worship-live-looks.py',import.meta.url));
const python=process.env.PRESENTATION_VISUAL_PYTHON??
 join(homedir(),'RDC-Development','rdc','.venv','bin','python');
test('Chromium and WebKit honor independent live worship Looks and private stage isolation',
 {timeout:20000},async t=>{
   if(platform()!=='darwin')return t.skip('macOS browser acceptance environment required.');
   try{await access(python);}catch{return t.skip('Optional isolated browser runner not installed.');}
   const {stdout}=await exec(python,[script],{timeout:17000,maxBuffer:64000});
   const report=JSON.parse(stdout);
   assert.equal(report.passed,true);
   assert.deepEqual(report.engines.map(v=>v.engine),['chromium','webkit']);
   assert.equal(report.obsSceneChanges,0);
   assert.equal(report.streamOrRecordingStarted,false);
   assert.equal(report.physicalHardwareAccepted,false);
   assert.ok(report.engines.every(v=>
     v.outputSpecificLookSelection&&v.stagePrivacyAfterLookChanges&&
     v.sameCueAcrossOutputs&&v.unloadClearsDisplay));
 });
