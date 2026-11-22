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
    comparison:{origin:'production-live',measuredRevision:revision,
      evidenceRef:'unittest-fixture-only://dc-comparison',workload:'terminal',
      samples:Array.from({length:30},(_,i)=>({
        requestId:'paired-terminal-'+i,rdcLatencyMs:800,dcLatencyMs:1600,
        rdcSuccess:true,dcSuccess:true,sameOutput:true,sameDevice:true
      }))},
    metrics:{},
  };
  for(const metric of metrics) {
    result.metrics[metric]={
      origin:'production-live',measuredRevision:revision,
      evidenceRef:'unittest-fixture-only://'+metric,
      samples:Array.from({length:30},(_,i)=>({
        requestId:metric+'-'+i,latencyMs:targets[metric],
        success:true,outputCorrect:true,gatewayBusy:false,timingStatus:'valid',
        ...(metric==='coding_discovery_read'?{cloudRequests:1}:{})
      })),
    };
  }
  if(overrides.environment) Object.assign(result.environment,overrides.environment);
  if(overrides.metrics) Object.assign(result.metrics,overrides.metrics);
  if(overrides.comparison) Object.assign(result.comparison,overrides.comparison);
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
  assert.equal(report.requiredGoals,6);
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
  assert.equal(report.passedGoals,6);
  assert.equal(report.comparison.passed,true);
  assert.equal(report.comparison.speedup,2);
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
  const reversed=receipt();
  reversed.metrics.gateway_queue_pickup.samples[0].timingStatus='invalid_clock_order';
  const rejected=evaluateRdcAcceptance(reversed);
  assert.equal(rejected.metrics.gateway_queue_pickup.passed,false,
    'an invalid wall-clock phase cannot qualify even with an otherwise good time');
  assert.ok(rejected.blockers.some(reason=>reason.includes('clock')));
  const input=receipt();
  input.metrics.local_notification.samples[5].latencyMs='0.1';
  assert.equal(evaluateRdcAcceptance(input).complete,false);
  assert.equal(evaluateRdcAcceptance({...input,extra:'x'}).complete,false);
});

test('matched 2x end-to-end advantage is required even if all five component goals pass',()=>{
  const input=receipt();
  for(const sample of input.comparison.samples)sample.dcLatencyMs=1400;
  const report=evaluateRdcAcceptance(input);
  assert.equal(report.complete,false);
  assert.equal(report.comparison.passed,false);
  assert.ok(report.blockers.some(reason=>reason.includes('2x')));
});
test('missing comparison and one fewer than 30 unique real pairs fail closed',()=>{
  const noComparison=receipt();delete noComparison.comparison;
  assert.equal(evaluateRdcAcceptance(noComparison).complete,false);
  const short=receipt();short.comparison.samples.pop();
  assert.equal(evaluateRdcAcceptance(short).complete,false);
  const duplicated=receipt();
  duplicated.comparison.samples[1].requestId=duplicated.comparison.samples[0].requestId;
  assert.equal(evaluateRdcAcceptance(duplicated).complete,false);
});
test('comparison rejects wrong device, mismatched original output and simulated evidence',()=>{
  const input=receipt();
  input.comparison.samples[0].sameDevice=false;
  input.comparison.samples[1].sameOutput=false;
  input.comparison.origin='source-simulation';
  input.comparison.measuredRevision='not-deployed';
  assert.equal(evaluateRdcAcceptance(input).complete,false);
});
test('standalone TLS owner gateway can qualify without a Cloudflare Site if fully verified',()=>{
  const input=receipt({environment:{transport:'owner-standalone',
    siteVersion:null,wakeBindingVerified:false,
    gatewayVersion:'actual-gateway-release',tlsVerified:true,
    pairingVerified:true,rollbackVerified:true}});
  assert.equal(evaluateRdcAcceptance(input).complete,true);
});
test('standalone release fails without public TLS, exact gateway ID, pairing and rollback',()=>{
  const input=receipt({environment:{transport:'owner-standalone',
    siteVersion:null,wakeBindingVerified:false,
    gatewayVersion:null,tlsVerified:false,pairingVerified:false,rollbackVerified:false}});
  const report=evaluateRdcAcceptance(input);
  assert.equal(report.complete,false);
  for(const term of ['gateway','TLS','pairing','rollback']) {
    assert.ok(report.blockers.some(reason=>reason.toLowerCase().includes(term.toLowerCase())),term);
  }
});
test('unrecognized transport cannot bypass verified private Site or standalone release checks',()=>{
  const input=receipt({environment:{transport:'untrusted-mode'}});
  assert.equal(evaluateRdcAcceptance(input).complete,false);
});

test('missing gateway busy and timing status evidence cannot pass',()=>{
  const a=receipt();
  delete a.metrics.live_terminal.samples[0].gatewayBusy;
  assert.equal(evaluateRdcAcceptance(a).complete,false);
  const b=receipt();
  delete b.metrics.claim_to_result.samples[0].timingStatus;
  assert.equal(evaluateRdcAcceptance(b).complete,false);
});
