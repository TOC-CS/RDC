#!/usr/bin/env node
// Dedicated loopback test fixture. Never starts actual OBS, streams, devices,
// projectors or desktop apps. Tokens are TEST-ONLY constants.
import {readFile} from 'node:fs/promises';
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';
const root=new URL('../skills/ai-presentation-agent/worship/examples/sunday-service.json',import.meta.url);
const plan=JSON.parse(await readFile(root,'utf8'));
plan.items[0].notes='PRIVATE_STAGE_VISUAL_TEST_MARKER';
plan.items[2].sections[0].notes='PRIVATE_SONG_VISUAL_TEST_MARKER';
const creds={
 token:'visual-test-control-token-2026',
 viewerToken:'visual-test-audience-token-2026',
 stageToken:'visual-test-stage-token-2026',
 streamToken:'visual-test-stream-token-2026'
};
const handler=createMcpHandler({stageGrant:creds.stageToken,allowWorshipLookChanges:true,allowStageClockControl:true});
let serial=0;
const call=async(name,args={})=>{
 const output=await handler({jsonrpc:'2.0',id:++serial,method:'tools/call',params:{name,arguments:args}});
 if(output?.result?.isError)throw new Error(output.result.content[0].text);
 return output.result.structuredContent;
};
await call('presentation_load_worship',{plan});
await call('presentation_start',{mode:'manual'});
const server=createHttpServer({handler,...creds});
await new Promise((resolve,reject)=>{
 server.once('error',reject);
 server.listen(0,'127.0.0.1',resolve);
});
process.stdout.write(JSON.stringify({port:server.address().port})+'\n');
let pending='';
process.stdin.on('data',chunk=>{
 pending+=String(chunk);
 let n;
 while((n=pending.indexOf('\n'))>=0){
   const line=pending.slice(0,n);pending=pending.slice(n+1);
   (async()=>{
     try{
       const request=JSON.parse(line);
       const result=request.action==='timer-configure'?
         handler.updatePrivateStageClock(creds.stageToken,{
           action:'configure',label:'PRIVATE_TIMER_VISUAL_MARKER',durationMs:90000
         }):
         request.action==='timer-start'?
           handler.updatePrivateStageClock(creds.stageToken,{action:'start'}):
         request.action==='timer-pause'?
           handler.updatePrivateStageClock(creds.stageToken,{action:'pause'}):
         request.action==='timer-reset'?
           handler.updatePrivateStageClock(creds.stageToken,{action:'reset'}):
         request.action==='next'?
           await call('presentation_command',{action:'next'}):
         request.action==='look-broadcast-minimal'?
           await call('presentation_worship_look_set',{
             destination:'broadcast',
             look:{layout:'minimal',background:'transparent',layers:['text']}
           }):
         request.action==='look-audience-minimal'?
           await call('presentation_worship_look_set',{
             destination:'audience',
             look:{layout:'minimal',background:'dark',layers:['text']}
           }):
         request.action==='look-stage-no-notes'?
           await call('presentation_worship_look_set',{
             destination:'stage',
             look:{layout:'confidence',background:'dark',layers:['title','text','next']}
           }):
         request.action==='visibility-broadcast-clear'?
           await call('presentation_worship_visibility_set',{
             destination:'broadcast',mode:'clear'
           }):
         request.action==='visibility-audience-blank'?
           await call('presentation_worship_visibility_set',{
             destination:'audience',mode:'blank'
           }):
         request.action==='visibility-stage-clear'?
           await call('presentation_worship_visibility_set',{
             destination:'stage',mode:'clear'
           }):
         request.action==='visibility-broadcast-visible'?
           await call('presentation_worship_visibility_set',{
             destination:'broadcast',mode:'visible'
           }):
         request.action==='visibility-audience-visible'?
           await call('presentation_worship_visibility_set',{
             destination:'audience',mode:'visible'
           }):
         request.action==='visibility-stage-visible'?
           await call('presentation_worship_visibility_set',{
             destination:'stage',mode:'visible'
           }):
         request.action==='stop'?
           await call('presentation_stop'):
           request.action==='unload'?
             await call('presentation_unload'):null;
       if(!result)throw new Error('Unsupported visual test action.');
       process.stdout.write(JSON.stringify({ok:true,action:request.action})+'\n');
     }catch{process.stdout.write(JSON.stringify({ok:false})+'\n');}
   })();
 }
});
const close=()=>{server.closeAllConnections();server.close(()=>process.exit(0));};
process.on('SIGTERM',close);process.on('SIGINT',close);
