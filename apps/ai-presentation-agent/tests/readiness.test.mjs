import test from 'node:test';
import assert from 'node:assert/strict';
import {presentationReadiness} from '../src/readiness.mjs';
test('read-only Mac readiness never opens apps or claims device permissions',async()=>{
 const observed=[];
 const result=await presentationReadiness({
   platform:'darwin',arch:'arm64',listApps:async()=>{observed.push('list');return ['Keynote.app','OBS.app'];},
   processes:async()=>{observed.push('ps');return ['OBS'];},
   available:async()=>{observed.push('access');return true;},
   binary:async name=>{observed.push('which:'+name);return name==='ffmpeg';},
   environment:{PRESENTATION_WHISPER_MODEL:'/private/available.bin'}
 });
 assert.equal(result.appReadiness.keynote.installed,true);
 assert.equal(result.appReadiness.keynote.running,false);
 assert.equal(result.appReadiness.obs.installed,true);
 assert.equal(result.appReadiness.obs.running,true);
 assert.equal(result.appReadiness.obs.liveControlQualified,false);
 assert.equal(result.appReadiness.propresenter.installed,false);
 assert.equal(result.inputs.microphone.liveCapture,'unverified');
 assert.equal(result.inputs.camera.osPermission,'unverified');
 assert.equal(result.localSpeechModel.configured,true);
 assert.equal(result.localSpeechModel.readable,true);
 assert.deepEqual(observed.sort(),['access','access','list','ps','which:ffmpeg','which:say','which:whisper-cli'].sort());
});
test('unknown process availability is reported unknown, never as a verified live app',async()=>{
 const result=await presentationReadiness({platform:'darwin',listApps:async()=>['Keynote.app'],
   processes:async()=>null,available:async()=>true,binary:async()=>false,environment:{}});
 assert.equal(result.appReadiness.keynote.running,null);
 assert.equal(result.appReadiness.keynote.liveControlQualified,false);
 assert.equal(result.localSpeechModel.configured,false);
});
test('Windows readiness leaves unsupported COM live claims unverified',async()=>{
 const result=await presentationReadiness({platform:'win32',environment:{}});
 assert.equal(result.appReadiness['powerpoint-windows'].liveControlQualified,false);
 assert.equal(result.inputs.camera.liveCapture,'unverified');
});
test('MCP and authenticated HTTP expose actual read-only readiness',async()=>{
 const {createMcpHandler}=await import('../src/mcp.mjs');
 const {createHttpServer}=await import('../src/http.mjs');
 const handler=createMcpHandler();
 const response=await handler({jsonrpc:'2.0',id:1,method:'tools/call',
   params:{name:'presentation_readiness',arguments:{}}});
 assert.equal(response.result.structuredContent.schema,'toc.presentation.readiness/v1');
 assert.equal(response.result.structuredContent.externalOutputsArmed,false);
 const server=createHttpServer({handler,token:'readiness-control-token-2026'});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 try{
   const url='http://127.0.0.1:'+server.address().port+'/v1/readiness';
   assert.equal((await fetch(url)).status,401);
   const authorized=await fetch(url,{headers:{Authorization:'Bearer readiness-control-token-2026'}});
   assert.equal(authorized.status,200);
   assert.equal((await authorized.json()).inputs.microphone.osPermission,'unverified');
 }finally{await new Promise(r=>server.close(r));}
});
