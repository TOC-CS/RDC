import assert from 'node:assert/strict';
import {test} from 'node:test';
import {evaluateRdcAcceptance, RDC_SPEED_GOALS, MIN_LIVE_SAMPLES} from './rdc_speed_acceptance.mjs';

const revision = 'd3cb6fc-test-live-receipt';
const metrics = Object.keys({
  live_terminal:1, gateway_queue_pickup:1, claim_to_result:1,
  local_notification:1, coding_discovery_read:1,
});

function receipt(overrides={}) {
  const targets={live_terminal:800, gateway_queue_pickup:50,
    claim_to_result:150, local_notification:1, coding_discovery_read:800};
  const result={
    schemaVersion:1,
    environment:{mode:'production-live',host:'ChatGPT-connected-RDC',
      gitRevision:revision,siteVersion:'candidate-site-vtest',
      workerVersion:'candidate-worker-vtest',wakeBindingVerified:true,
      rollbackVerified:true},
    metrics:{},
  };
  for(const metric of metrics) {
    result.metrics[metric]={
      origin:'production-live',measuredRevision:revision,
      evidenceRef:'unittest-fixture-only://'+metric,
      samples:Array.from({length:30},(_,i)=>({
        requestId:metric+'-'+i,latencyMs:targets[metric],
        success:true,outputCorrect:true,gatewayBusy:false,
        ...(metric==='coding_discovery_read'?{cloudRequests:1}:{})
      })),
    };
  }
  if(overrides.environment) Object.assign(result.environment,overrides.environment);
  if(overrides.metrics) Object.assign(result.metrics,overrides.metrics);
  return result;
}
test('fixed owner targets have the five exact baseline and acceptance numbers',()=>{
  assert.equal(MIN_LIVE_SAMPLES,30);
  assert.deepEqual(
    Object.fromEntries(Object.entries(RDC_SPEED_GOALS).map(([k,v])=>[k,[v.baselineMs??v.baselineRequests,v.maxMedianMs,v.maxCloudRequests??null]])),
    {live_terminal:[3400,800,null],gateway_queue_pickup:[311,50,null],
     claim_to_result:[678,150,null],local_notification:[501.591,1,null],
     coding_discovery_read:[2,800,1]});
});
test('missing live data hard-fails, never reports performance complete',()=>{
  const report=evaluateRdcAcceptance();
  assert.equal(report.complete,false);
  assert.equal(report.passedGoals,0);
  assert.equal(report.requiredGoals,5);
});
test('simulated/local-only data cannot qualify real production',()=>{
  const input=receipt({environment:{mode:'source-simulation'}});
  input.metrics.live_terminal.origin='local-simulation';
  const report=evaluateRdcAcceptance(input);
  assert.equal(report.complete,false);
  assert.equal(report.metrics.live_terminal.passed,false);
});
test('under 900ms is insufficient when live terminal exceeds the owner 800ms target',()=>{
  const input=receipt();
  input.metrics.live_terminal.samples[0].latencyMs=850;
  for(const s of input.metrics.live_terminal.samples) s.latencyMs=850;
  const report=evaluateRdcAcceptance(input);
  assert.equal(report.complete,false);
  assert.equal(report.metrics.live_terminal.medianMs,850);
});
test('fewer than 30 calls, repeated IDs and incorrect outputs always fail',()=>{
  const input=receipt();
  input.metrics.gateway_queue_pickup.samples.pop();
  input.metrics.claim_to_result.samples[1].requestId=input.metrics.claim_to_result.samples[0].requestId;
  input.metrics.local_notification.samples[10].outputCorrect=false;
  const report=evaluateRdcAcceptance(input);
  for(const name of ['gateway_queue_pickup','claim_to_result','local_notification'])
    assert.equal(report.metrics[name].passed,false,name);
  assert.equal(report.complete,false);
});
test('any gateway_busy failure fails even if the median is excellent',()=>{
  const input=receipt();
  input.metrics.live_terminal.samples[2].gatewayBusy=true;
  assert.equal(evaluateRdcAcceptance(input).metrics.live_terminal.passed,false);
});
test('coding discovery must use ONE cloud request for EVERY accepted measurement',()=>{
  const input=receipt();
  input.metrics.coding_discovery_read.samples[3].cloudRequests=2;
  assert.equal(evaluateRdcAcceptance(input).metrics.coding_discovery_read.passed,false);
});
test('exactly-at-goal live receipt with complete revision and rollback proof passes policy',()=>{
  const report=evaluateRdcAcceptance(receipt());
  assert.equal(report.complete,true);
  assert.equal(report.passedGoals,5);
  assert.equal(report.metrics.live_terminal.medianMs,800);
  assert.equal(report.metrics.live_terminal.reductionPct,76.5);
  assert.equal(report.metrics.live_terminal.speedup,4.25);
  assert.equal(report.metrics.local_notification.reductionPct,99.8);
  assert.equal(report.metrics.local_notification.speedup,501.6);
  assert.equal(report.metrics.coding_discovery_read.requestReductionPct,50);
  assert.ok(Number.isFinite(report.metrics.live_terminal.p95Ms));
  assert.ok(Number.isFinite(report.metrics.live_terminal.p99Ms));
});
test('production source revision and rollback must match measured deployment',()=>{
  const input=receipt({environment:{rollbackVerified:false}});
  input.metrics.coding_discovery_read.measuredRevision='unknown';
  const report=evaluateRdcAcceptance(input);
  assert.equal(report.complete,false);
  assert.equal(report.metrics.coding_discovery_read.passed,false);
});
test('unknown goals and invalid latency samples do not create a passing receipt',()=>{
  const input=receipt();
  input.metrics.local_notification.samples[5].latencyMs='0.1';
  assert.equal(evaluateRdcAcceptance(input).complete,false);
  assert.equal(evaluateRdcAcceptance({...input,extra:'x'}).complete,false);
});
