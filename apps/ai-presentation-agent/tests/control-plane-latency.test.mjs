import test from 'node:test';
import assert from 'node:assert/strict';
import {benchmarkPresentationControl} from '../scripts/bench-control-plane.mjs';
test('real loopback HTTP and SSE viewer follow repeated slide changes in measured order',async()=>{
 const report=await benchmarkPresentationControl({transitions:4});
 assert.equal(report.samples,4);
 assert.ok(report.p50Ms>=0);
 assert.ok(report.p95Ms>=report.p50Ms);
 assert.ok(report.maxMs>=report.p95Ms);
 assert.equal(report.physicalProjectionMeasured,false);
 assert.equal(report.viewer,'authenticated SSE');
});
test('transport benchmark refuses unbounded transitions',async()=>{
 await assert.rejects(()=>benchmarkPresentationControl({transitions:10001}),/1 to 100/);
});
