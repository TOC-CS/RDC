/**
 * RDC mandatory live speed acceptance.
 *
 * The source release can be green without the new RDC being fast. This
 * independent fail-closed gate is ONLY green with complete, correct live
 * measurement receipts for every owner-mandated performance target.
 * Baselines are historical figures, not newer measurements.
 */
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

export const MIN_LIVE_SAMPLES=30;
export const RDC_SPEED_GOALS=Object.freeze({
  live_terminal:Object.freeze({baselineMs:3400,maxMedianMs:800,referenceReductionPct:76.5,referenceSpeedup:4.25}),
  gateway_queue_pickup:Object.freeze({baselineMs:311,maxMedianMs:50,referenceReductionPct:83.9,referenceSpeedup:6.22}),
  claim_to_result:Object.freeze({baselineMs:678,maxMedianMs:150,referenceReductionPct:77.9,referenceSpeedup:4.52}),
  local_notification:Object.freeze({baselineMs:501.591,maxMedianMs:1,referenceReductionPct:99.8,referenceSpeedup:501.6}),
  coding_discovery_read:Object.freeze({baselineRequests:2,maxCloudRequests:1,maxMedianMs:800,referenceRequestReductionPct:50}),
});
const GOAL_NAMES=Object.keys(RDC_SPEED_GOALS);
function finitePositive(n){return typeof n==='number'&&Number.isFinite(n)&&n>0}
function nonempty(s){return typeof s==='string'&&s.trim().length>0}
function fixed(n,digits=2){return Number(n.toFixed(digits))}
export function percentile(values,p) {
  if(!values.length) return null;
  const sorted=[...values].sort((a,b)=>a-b);
  const rank=(sorted.length-1)*p,lo=Math.floor(rank),hi=Math.ceil(rank);
  return fixed(sorted[lo]+(sorted[hi]-sorted[lo])*(rank-lo),3);
}
export function evaluateRdcAcceptance(receipt) {
  const blockers=[],metrics={};
  const report={schemaVersion:1,complete:false,passedGoals:0,
    requiredGoals:GOAL_NAMES.length,metrics,blockers};
  const data=receipt&&typeof receipt==='object'&&!Array.isArray(receipt)?receipt:{};
  if(!receipt) blockers.push('No independently evidenced LIVE speed receipt supplied');
  if(data.schemaVersion!==1) blockers.push('Expected schemaVersion 1');
  if(Object.keys(data).some(key=>!['schemaVersion','environment','metrics'].includes(key))) {
    blockers.push('Unknown top-level acceptance receipt fields');
  }
  const env=data.environment&&typeof data.environment==='object'?data.environment:{};
  if(env.mode!=='production-live') blockers.push('Source simulations and local tests cannot establish deployed live speed');
  if(env.host!=='ChatGPT-connected-RDC') blockers.push('Measure the actual ChatGPT-connected RDC path');
  if(!nonempty(env.gitRevision)) blockers.push('Missing exact deployed git revision');
  if(!nonempty(env.siteVersion)) blockers.push('Missing actual private Site release readback');
  if(!nonempty(env.workerVersion)) blockers.push('Missing actual connected worker release readback');
  if(env.wakeBindingVerified!==true) blockers.push('Cloudflare wake binding was not verified on deployed Site');
  if(env.rollbackVerified!==true) blockers.push('Protected deployment rollback was not independently verified');
  const supplied=data.metrics&&typeof data.metrics==='object'&&!Array.isArray(data.metrics)?data.metrics:{};
  if(Object.keys(supplied).some(key=>!GOAL_NAMES.includes(key))) blockers.push('Unknown metric supplied');
  for(const [name,goal] of Object.entries(RDC_SPEED_GOALS)) {
    const metric=supplied[name],issues=[],times=[],ids=new Set();
    const outcome={
      passed:false,samples:0,baselineMs:goal.baselineMs??null,
      baselineRequests:goal.baselineRequests??null,maxMedianMs:goal.maxMedianMs,
      maxCloudRequests:goal.maxCloudRequests??null,
      medianMs:null,p95Ms:null,p99Ms:null,reductionPct:null,speedup:null,
      requestReductionPct:null,issues,
    };
    metrics[name]=outcome;
    if(!metric || !Array.isArray(metric.samples)) {
      issues.push('Missing individual live timed samples');
      continue;
    }
    outcome.samples=metric.samples.length;
    if(metric.samples.length<MIN_LIVE_SAMPLES) issues.push('Minimum of 30 actual live operations required');
    if(metric.origin!=='production-live') issues.push('Simulated or local-only measurements are inadmissible');
    if(!nonempty(metric.evidenceRef)) issues.push('Missing independent live telemetry reference');
    if(!nonempty(metric.measuredRevision)||metric.measuredRevision!==env.gitRevision) {
      issues.push('Measured source revision disagrees with deployed source');
    }
    for(const sample of metric.samples) {
      if(!sample || typeof sample!=='object'||Array.isArray(sample)) {
        issues.push('Invalid sample record');
        continue;
      }
      if(!nonempty(sample.requestId)||ids.has(sample.requestId)) {
        issues.push('Every operation requires a unique nonempty request ID');
      }
      ids.add(sample.requestId);
      if(!finitePositive(sample.latencyMs)) issues.push('Invalid or missing actual measured latency');
      else times.push(sample.latencyMs);
      if(sample.success!==true||sample.outputCorrect!==true||sample.gatewayBusy===true) {
        issues.push('Failed, incorrect, or gateway_busy operation is an acceptance failure');
      }
      if(name==='coding_discovery_read'&&sample.cloudRequests!==goal.maxCloudRequests) {
        issues.push('Coding search and selected file read MUST complete in exactly one cloud request');
      }
    }
    if(times.length===metric.samples.length && times.length) {
      outcome.medianMs=percentile(times,0.5);
      outcome.p95Ms=percentile(times,0.95);
      outcome.p99Ms=percentile(times,0.99);
      if(outcome.medianMs>goal.maxMedianMs) {
        issues.push('Live median exceeds mandatory '+goal.maxMedianMs+' ms target');
      }
      if(goal.baselineMs!==undefined) {
        outcome.reductionPct=fixed(100*(goal.baselineMs-outcome.medianMs)/goal.baselineMs,1);
        outcome.speedup=outcome.medianMs===0?null:fixed(goal.baselineMs/outcome.medianMs,name==="local_notification"?1:2);
      } else {
        outcome.requestReductionPct=fixed(100*(goal.baselineRequests-goal.maxCloudRequests)/goal.baselineRequests,1);
      }
    }
    outcome.passed=issues.length===0;
    if(outcome.passed) report.passedGoals++;
    else blockers.push(name+': '+[...new Set(issues)].join('; '));
  }
  report.complete=blockers.length===0&&report.passedGoals===GOAL_NAMES.length;
  return report;
}

if(process.argv[1] && pathToFileURL(resolve(process.argv[1])).href===import.meta.url) {
  let receipt=null;
  if(process.argv.length>2) {
    try {receipt=JSON.parse(readFileSync(process.argv[2],'utf8'))}
    catch(err){process.stderr.write('Cannot read acceptance receipt: '+err.message+'\n')}
  }
  const assessment=evaluateRdcAcceptance(receipt);
  process.stdout.write(JSON.stringify(assessment,null,2)+'\n');
  process.exitCode=assessment.complete?0:1;
}
