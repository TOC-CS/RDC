#!/usr/bin/env node
// Local, synthetic cue dispatch benchmark. Never touches audio, cameras,
// keyboards, presentation apps, networks or hardware.
import {performance} from 'node:perf_hooks';
import {writeFile,mkdir} from 'node:fs/promises';
import {PresentationDirector} from '../src/director.mjs';
import {MemoryAdapter} from '../src/adapters.mjs';

let timestamp=100000;
const slides=[{id:'intro',title:'Intro'}];
for(let i=1;i<=20;i++){
 slides.push({id:'part'+i,title:'Part '+i,song:'Benchmark',section:'part '+i,
   text:'Sample lyrics for part number '+i});
}
const adapter=new MemoryAdapter();
const director=new PresentationDirector({adapter,clock:()=>timestamp,cooldownMs:0});
director.load({title:'Synthetic session',slides});
await director.start('automatic');

const samples=[];
const trials=2000;
let changed=0,duplicates=0;
for(let i=0;i<trials;i++){
 timestamp+=1500;
 const section='part '+((i%20)+1);
 const started=performance.now();
 const result=await director.ingest({
   source:'bandmates',type:'song.section',song:'Benchmark',section,
   occurrence:Math.floor(i/20)+1,eventId:'bench:'+i,
   timestamp
 });
 samples.push(performance.now()-started);
 if(result.changed)changed++;
 else duplicates++;
}
const sorted=samples.sort((a,b)=>a-b);
const percentile=p=>sorted[Math.min(sorted.length-1,Math.floor(p*(sorted.length-1)))];
const summary={
 benchmark:'Synthetic in-process command-path only, not audio/video/device/network latency',
 trials,changed,notChanged:duplicates,
 p50Milliseconds:+percentile(.5).toFixed(4),
 p95Milliseconds:+percentile(.95).toFixed(4),
 p99Milliseconds:+percentile(.99).toFixed(4),
 maximumMilliseconds:+sorted.at(-1).toFixed(4),
 readbackVerified:false,physicalDevicesTested:false
};
await mkdir(new URL('../evidence/',import.meta.url),{recursive:true});
const target=new URL('../evidence/synthetic-cue-latency-20261116.json',import.meta.url);
await writeFile(target,JSON.stringify(summary,null,2));
console.log(JSON.stringify(summary,null,2));
