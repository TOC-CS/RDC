#!/usr/bin/env node
// Local-only visual acceptance fixture for private stage teleprompt.
// No projector, OBS, camera, microphone, stream, or BandMates device access.
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';
const ids={
 token:'test-teleprompt-operator-bearer-2026',
 viewerToken:'test-teleprompt-audience-bearer-2026',
 stageToken:'test-teleprompt-stage-bearer-2026',
 streamToken:'test-teleprompt-broadcast-bearer-2026'
};
const plan={title:'Original stage teleprompt visual rehearsal',items:[{
 id:'sermon',type:'sermon',title:'Speaker title',text:'Welcome to our original service',
 notes:'PRIVATE_FIRST_LINE_OF_SERMON\nPRIVATE_SECOND_LINE_OF_SERMON'
}]};
const handler=createMcpHandler({stageGrant:ids.stageToken,
 allowTelepromptControl:true,allowWorshipLookChanges:true});
let serial=0;
const call=async(name,args={})=>{
 const response=await handler({jsonrpc:'2.0',id:++serial,method:'tools/call',
  params:{name,arguments:args}});
 if(response?.result?.isError)throw new Error(response.result.content?.[0]?.text??'Rejected');
 return response?.result?.structuredContent;
};
await call('presentation_load_worship',{plan});
await call('presentation_start',{mode:'manual'});
const server=createHttpServer({handler,...ids});
await new Promise((resolve,reject)=>{
 server.once('error',reject);
 server.listen(0,'127.0.0.1',resolve);
});
process.stdout.write(JSON.stringify({port:server.address().port})+'\n');
let pending='';
process.stdin.on('data',chunk=>{
 pending+=String(chunk);
 while(pending.includes('\n')){
  const at=pending.indexOf('\n');
  const line=pending.slice(0,at);
  pending=pending.slice(at+1);
  (async()=>{
   try{
    const command=JSON.parse(line);
    let result;
    if(command.action==='speaker')result=handler.updatePrivateTeleprompt(ids.stageToken,{
     action:'configure',role:'speaker',fontScale:1.5,scrollSpeed:1.2,mirrored:false});
    else if(command.action==='singer')result=handler.updatePrivateTeleprompt(ids.stageToken,{
     action:'configure',role:'singer',fontScale:1.6,scrollSpeed:1.25,mirrored:true});
    else if(command.action==='next')result=handler.updatePrivateTeleprompt(ids.stageToken,{action:'next'});
    else if(command.action==='hold')result=handler.updatePrivateTeleprompt(ids.stageToken,{action:'hold'});
    else if(command.action==='follow')result=handler.updatePrivateTeleprompt(ids.stageToken,{
     action:'follow',text:'PRIVATE_SECOND_LINE_OF_SERMON',
     confidence:.99,final:true,eventId:'verified-stage-speech-2',timestamp:Date.now()});
    else if(command.action==='stage-clear')result=await call('presentation_worship_visibility_set',{
     destination:'stage',mode:'clear'});
    else if(command.action==='stage-visible')result=await call('presentation_worship_visibility_set',{
     destination:'stage',mode:'visible'});
    else if(command.action==='stop')result=await call('presentation_stop');
    else if(command.action==='unload')result=await call('presentation_unload');
    else throw new Error('unsupported fixture action');
    if(!result)throw new Error('missing result');
    process.stdout.write(JSON.stringify({ok:true,action:command.action})+'\n');
   }catch{process.stdout.write(JSON.stringify({ok:false})+'\n');}
  })();
 }
});
const close=()=>{server.closeAllConnections();server.close(()=>process.exit(0));};
process.on('SIGINT',close);process.on('SIGTERM',close);
