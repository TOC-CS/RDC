/* Microbenchmark of the optional local Durable Object wake behavior.
 * Never describe these times as real Cloudflare, RDC, ChatGPT or DC latency.
 */
import assert from 'node:assert/strict';
import {performance} from 'node:perf_hooks';
import {writeFileSync,mkdirSync} from 'node:fs';
import {dirname} from 'node:path';
import {RDCWakeSignal} from '../cloud-gateway/lib/rdc-wake.mjs';

const request=path=>new Request('https://rdc-wake.internal'+path,{method:'POST'});
function summary(values){
  const sorted=[...values].sort((a,b)=>a-b);
  const percentile=p=>sorted[Math.ceil(p*sorted.length)-1];
  const median=(sorted[14]+sorted[15])/2;
  return {n:values.length,p50_ms:Number(median.toFixed(3)),
    p95_ms:Number(percentile(.95).toFixed(3)),
    min_ms:Number(sorted[0].toFixed(3)),max_ms:Number(sorted.at(-1).toFixed(3))};
}
async function trial(mode){
  const channel=new RDCWakeSignal();
  const start=performance.now();
  const wait=channel.fetch(request('/wait?ms=500'));
  if(mode==='event'){
    await channel.fetch(request('/notify'));
  }
  const reply=await wait;
  assert.equal(reply.status,200);
  assert.equal((await reply.json()).signaled,mode==='event');
  assert.equal(channel.waiters.size,0);
  return performance.now()-start;
}
for(let i=0;i<2;i++){
  await trial('event'); await trial('fallback');
}
const samples={event:[],fallback:[]};
for(let i=0;i<30;i++){
  const order=i%2===0?['event','fallback']:['fallback','event'];
  for(const variant of order){samples[variant].push(await trial(variant));}
}
const report={
  timestamp_utc:new Date().toISOString(),
  scope:'local Node Durable Object class simulated with timer; no Cloudflare network, D1, RDC worker, ChatGPT host or DC included',
  correctness:'30/30 event signals and 30/30 timer fallbacks returned their expected distinct states',
  timer_ms:500,warmups_per_variant:2,trials_per_variant:30,balanced_order:true,
  summary:{event:summary(samples.event),fallback:summary(samples.fallback)},samples_ms:samples
};
const out=process.argv[2];
if(!out)throw new Error('Usage: node benchmarks/wake_latency_compare.mjs RESULT_JSON');
mkdirSync(dirname(out),{recursive:true});
writeFileSync(out,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({scope:report.scope,summary:report.summary,correctness:report.correctness},null,2));
