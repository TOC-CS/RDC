import test from 'node:test';
import assert from 'node:assert/strict';
import {platform} from 'node:os';
import {access} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {verifyStreamVoice} from '../scripts/verify-microphone-stream.mjs';

const model=fileURLToPath(new URL('../.tooling/models/ggml-tiny.en.bin',import.meta.url));
test('synthetic streaming microphone PCM confirms one real Whisper command and blocks repeats',
 {timeout:30000},async t=>{
   if(platform()!=='darwin')return t.skip('macOS-only synthetic speech rehearsal');
   try{await access(model);}catch{return t.skip('Optional local Whisper model is not installed');}
   const result=await verifyStreamVoice({modelPath:model});
   assert.equal(result.confirmedCommands,1);
   assert.equal(result.finalSlide,'welcome');
   assert.equal(result.microphoneCaptured,false);
   assert.equal(result.speakerOutput,false);
   assert.equal(result.usesCloud,false);
   assert.ok(result.observations.some(o=>o.confirmation==='already_executed'));
 });
