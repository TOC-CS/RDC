#!/usr/bin/env node
// Isolated local transport / SSE viewer benchmark. No physical audio/video,
// app launch, browser, camera, MIDI, projector, or external presentation writes.
import {performance} from 'node:perf_hooks';
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';
import {pathToFileURL} from 'node:url';

function percentile(values,p){
 if(!values.length)return null;
 const sorted=[...values].sort((a,b)=>a-b);
 return Number(sorted[Math.max(0,Math.ceil(sorted.length*p)-1)].toFixed(2));
}
export async function benchmarkPresentationControl({transitions=30}={}){
 if(!Number.isInteger(transitions)||transitions<1||transitions>100)
   throw new Error('Choose 1 to 100 benchmark transitions.');
 const token='control-plane-local-fixture-token',viewerToken='view-only-local-fixture-token';
 const handler=createMcpHandler();
 const server=createHttpServer({handler,token,viewerToken});
 let controller,reader,readLoop,lastIndex=null;
 const subscribers=new Set();
 let streamError=null,failed=false,sseBuffer='';
 const post=async(base,route,body)=>{
   const result=await fetch(base+route,{method:'POST',headers:{
     Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify(body)});
   if(!result.ok)throw new Error('Local control API returned '+result.status);
   return result.json();
 };
 try{
   await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
   const base='http://127.0.0.1:'+server.address().port;
   await post(base,'/v1/load',{deck:{title:'Isolated control benchmark',
     slides:[{id:'one',text:'One'},{id:'two',text:'Two'}]}});
   await post(base,'/v1/start',{mode:'manual'});
   controller=new AbortController();
   const response=await fetch(base+'/v1/view-events?key='+encodeURIComponent(viewerToken),
     {signal:controller.signal});
   if(response.status!==200)throw new Error('Local SSE viewer did not connect.');
   reader=response.body.getReader();
   readLoop=(async()=>{
     try{
       while(true){
         const packet=await reader.read();if(packet.done)break;
         sseBuffer+=new TextDecoder().decode(packet.value);
         let marker;
         while((marker=sseBuffer.indexOf('\n\n'))>=0){
           const event=sseBuffer.slice(0,marker);
           sseBuffer=sseBuffer.slice(marker+2);
           for(const row of event.split('\n')){
             if(!row.startsWith('data: '))continue;
             const data=JSON.parse(row.slice(6));
             if(!Number.isInteger(data.index))continue;
             lastIndex=data.index;
             for(const cb of subscribers)cb(lastIndex);
           }
         }
       }
     }catch(error){
       if(!controller.signal.aborted)streamError=String(error.message??error);
     }finally{
       failed=true;
       for(const cb of subscribers)cb(null);
     }
   })();
   const waitFor=target=>new Promise((resolve,reject)=>{
     if(lastIndex===target)return resolve();
     const timer=setTimeout(()=>{subscribers.delete(listener);
       reject(new Error('SSE viewer did not acknowledge slide '+target+' within 3 seconds.'));},3000);
     const listener=index=>{
       if(index!==target&&index!==null)return;
       clearTimeout(timer);subscribers.delete(listener);
       if(index===null)return reject(new Error('SSE stream ended unexpectedly.'));
       resolve();
     };
     subscribers.add(listener);
     if(failed||streamError)listener(null);
   });
   await waitFor(0);
   const samples=[];
   for(let i=0;i<transitions;i++){
     const target=i%2===0?1:0,action=i%2===0?'next':'previous';
     const start=performance.now();
     const change=await post(base,'/v1/command',{action});
     if(change.changed!==true)throw new Error('Slide failed to change during the synthetic benchmark.');
     await waitFor(target);
     samples.push(performance.now()-start);
   }
   return {
     schema:'toc.presentation.local-control-latency/v1',
     evidenceType:'isolated local HTTP+SSE control-plane benchmark',
     samples:transitions,medium:'loopback',viewer:'authenticated SSE',
     p50Ms:percentile(samples,.5),p95Ms:percentile(samples,.95),
     p99Ms:percentile(samples,.99),maxMs:Number(Math.max(...samples).toFixed(2)),
     physicalProjectionMeasured:false,cameraLatencyMeasured:false,
     microphoneLatencyMeasured:false,bandmatesAudioLatencyMeasured:false,
     note:'Local API-to-viewer delivery only. This excludes physical speakers, camera, live AI voice, stream encoding, third-party apps, and projection.'
   };
 }finally{
   controller?.abort();
   if(reader){try{await reader.cancel();}catch{}}
   if(readLoop){try{await readLoop;}catch{}}
   server.closeAllConnections();
   if(server.listening)await new Promise(resolve=>server.close(resolve));
 }
}
if(process.argv[1]&&pathToFileURL(process.argv[1]).href===import.meta.url){
 const report=await benchmarkPresentationControl({transitions:30});
 process.stdout.write(JSON.stringify(report,null,2)+'\n');
}
