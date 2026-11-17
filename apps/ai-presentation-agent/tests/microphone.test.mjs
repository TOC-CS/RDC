import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {encodePcm16Wav,PcmWindowQueue} from '../src/audio-stream.mjs';
const script=fileURLToPath(new URL('../scripts/local-microphone.mjs',import.meta.url));
test('local microphone help can be read without opening any audio device',()=>{
 const r=spawnSync(process.execPath,[script,'--help'],{encoding:'utf8',timeout:3000,env:{PATH:process.env.PATH}});
 assert.equal(r.status,0,r.stderr);assert.match(r.stdout,/model/i);
});
test('microphone capture refuses launch without operator-provided credential and model',()=>{
 const r=spawnSync(process.execPath,[script,'--device','0'],{encoding:'utf8',timeout:3000,env:{PATH:process.env.PATH}});
 assert.notEqual(r.status,0);assert.match(r.stderr,/PRESENTATION_API_TOKEN/);
});
test('audio PCM format is a valid mono 16-bit 16000 Hz WAV',()=>{
 const pcm=Buffer.from([0,0,255,127,1,0]);
 const wav=encodePcm16Wav(pcm);
 assert.equal(wav.subarray(0,4).toString('ascii'),'RIFF');
 assert.equal(wav.subarray(8,12).toString('ascii'),'WAVE');
 assert.equal(wav.readUInt32LE(24),16000);
 assert.equal(wav.readUInt16LE(34),16);
 assert.equal(wav.readUInt32LE(40),6);
 assert.deepEqual(wav.subarray(44),pcm);
});
test('live microphone queue drops old audio and bounds buffered samples',()=>{
 const queue=new PcmWindowQueue({framesPerWindow:12,overlapFrames:4,maxBytes:96});
 const a=queue.feed(Buffer.alloc(36,1));
 assert.equal(a.length,1);
 assert.equal(a[0].length,24);
 const b=queue.feed(Buffer.alloc(60,2));
 assert.ok(b.every(v=>v.length<=32));
 assert.ok(queue.buffer.length<=96);
});
test('local microphone spoken talkback refuses default audio output before starting a capture',t=>{
 if(process.platform!=='darwin')return t.skip('macOS-only audio selection');
 const model=fileURLToPath(new URL('../.tooling/models/ggml-tiny.en.bin',import.meta.url));
 const env={...process.env,PRESENTATION_API_TOKEN:'test-microphone-token-2026'};
 const r=spawnSync(process.execPath,[script,'--device','0','--model',model,
   '--commands','--speak'],{encoding:'utf8',timeout:3000,env});
 assert.equal(r.status,2,r.stderr);
 assert.match(r.stderr,/output-device|private.monitor/i);
 assert.doesNotMatch(r.stderr,/microphone active/i);
});
test('macOS output device discovery lists speakers without opening a microphone or speaking',t=>{
 if(process.platform!=='darwin')return t.skip('macOS-only audio selection');
 const r=spawnSync(process.execPath,[script,'--list-outputs'],{
   encoding:'utf8',timeout:3000,env:{PATH:process.env.PATH}});
 assert.equal(r.status,0,r.stderr);
 const report=JSON.parse(r.stdout);
 assert.equal(report.captureStarted,false);
 assert.equal(report.speechPlayed,false);
 assert.ok(Array.isArray(report.outputs));
});
