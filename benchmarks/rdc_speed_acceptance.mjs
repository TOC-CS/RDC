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
  // Five absolute speed ceilings plus a mandatory independent matched
  // 2x end-to-end Desktop Commander comparison are SIX release requirements.
  const report={schemaVersion:1,complete:false,passedGoals:0,
    requiredGoals:GOAL_NAMES.length+1,metrics,blockers,comparison:null};
  const data=receipt&&typeof receipt==='object'&&!Array.isArray(receipt)?receipt:{};
  if(!receipt) blockers.push('No independently evidenced LIVE speed receipt supplied');
  if(data.schemaVersion!==1) blockers.push('Expected schemaVersion 1');
  if(Object.keys(data).some(key=>!['schemaVersion','environment','metrics','comparison'].includes(key))) {
    blockers.push('Unknown top-level acceptance receipt fields');
  }
  const env=data.environment&&typeof data.environment==='object'?data.environment:{};
  if(env.mode!=='production-live') blockers.push('Source simulations and local tests cannot establish deployed live speed');
  if(env.host!=='ChatGPT-connected-RDC') blockers.push('Measure the actual ChatGPT-connected RDC path');
  if(!nonempty(env.gitRevision)) blockers.push('Missing exact deployed git revision');
  const transport=env.transport??'private-sites';
  if(transport==='private-sites') {
    if(!nonempty(env.siteVersion)) blockers.push('Missing actual private Site release readback');
    if(env.wakeBindingVerified!==true)
      blockers.push('Cloudflare wake binding was not verified on deployed Site');
  }else if(transport==='owner-standalone') {
    // Independent operator-hosted transport never requires or silently
    // inherits a Cloudflare binding. It MUST prove its own protected endpoint.
    if(!nonempty(env.gatewayVersion))
      blockers.push('Missing exact standalone gateway release readback');
    if(env.tlsVerified!==true)
      blockers.push('Standalone gateway public TLS/WSS was not verified');
    if(env.pairingVerified!==true)
      blockers.push('Standalone gateway owner/device pairing was not verified');
  }else blockers.push('Unknown gateway transport cannot bypass release verification');
  if(!nonempty(env.workerVersion)) blockers.push('Missing actual connected worker release readback');
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
      // Durable millisecond timestamps can run backwards after OS clock
      // correction. Never accept the resulting zero/negative phase as fast.
      if(sample.timingStatus!=='valid')
        issues.push('Missing or invalid clock/timing status: phase timing must be verified live');
      if(sample.success!==true||sample.outputCorrect!==true||sample.gatewayBusy!==false) {
        issues.push('Failed, incorrect, missing busy status, or gateway_busy operation is an acceptance failure');
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
  // Never infer a real-world comparison from a local Site simulation,
  // unrelated devices or different output. Each matched pair counts as TWO
  // operations; 50 pairs is the maximum under the 100-operation campaign cap.
  const match=data.comparison;
  const issues=[];
  const paired={passed:false,samples:0,minSamples:MIN_LIVE_SAMPLES,
    maxPairs:50,rdcMedianMs:null,dcMedianMs:null,speedup:null,issues};
  report.comparison=paired;
  if(!match||!Array.isArray(match.samples)) {
    issues.push('Missing independent matched RDC versus Desktop Commander live samples');
  }else{
    paired.samples=match.samples.length;
    if(match.samples.length<MIN_LIVE_SAMPLES)
      issues.push('Matched 2x DC comparison requires 30 actual live pairs');
    if(match.samples.length>50)
      issues.push('Matched comparison exceeds the 100-operation campaign maximum');
    if(match.origin!=='production-live')
      issues.push('Matched comparison may not use simulations or local-only measurements');
    if(match.workload!=='terminal')
      issues.push('Matched comparison must exercise the same real terminal workload');
    if(!nonempty(match.evidenceRef))
      issues.push('Missing independent matched terminal evidence reference');
    if(!nonempty(match.measuredRevision)||match.measuredRevision!==env.gitRevision)
      issues.push('Matched RDC revision disagrees with deployed source');
    const ids=new Set(),rdc=[],dc=[];
    for(const sample of match.samples){
      if(!sample||typeof sample!=='object'||Array.isArray(sample)){
        issues.push('Malformed matched terminal record');continue;
      }
      if(!nonempty(sample.requestId)||ids.has(sample.requestId))
        issues.push('Every matched terminal pair requires a unique request ID');
      ids.add(sample.requestId);
      if(!finitePositive(sample.rdcLatencyMs)||!finitePositive(sample.dcLatencyMs))
        issues.push('Matched end-to-end latencies must be positive finite milliseconds');
      else {rdc.push(sample.rdcLatencyMs);dc.push(sample.dcLatencyMs);}
      if(sample.rdcSuccess!==true||sample.dcSuccess!==true||sample.sameOutput!==true)
        issues.push('Both tools must finish successfully with identical original output');
      if(sample.sameDevice!==true)
        issues.push('Matched comparison must execute on the same authorized device');
    }
    if(rdc.length===match.samples.length&&rdc.length){
      paired.rdcMedianMs=percentile(rdc,0.5);
      paired.dcMedianMs=percentile(dc,0.5);
      const ratio=paired.dcMedianMs/paired.rdcMedianMs;
      paired.speedup=fixed(ratio,3);
      if(ratio<2)
        issues.push('Measured RDC end-to-end speed is below required 2x Desktop Commander advantage');
      if(paired.rdcMedianMs>RDC_SPEED_GOALS.live_terminal.maxMedianMs)
        issues.push('Matched live RDC terminal median exceeds 800ms goal');
    }
  }
  paired.passed=issues.length===0;
  if(paired.passed) report.passedGoals++;
  else blockers.push('matched_dc_speedup: '+[...new Set(issues)].join('; '));
  report.complete=blockers.length===0&&report.passedGoals===report.requiredGoals;
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
