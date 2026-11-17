#!/usr/bin/env node
// Private loopback server for independent RDC and BandMates commands.
// State is owner-only and contains an ephemeral local bearer token.
import {randomBytes,randomUUID} from 'node:crypto';
import {writeFile,readFile,unlink} from 'node:fs/promises';
import {setupPrivateState,readPrivateState} from '../src/managed-state.mjs';
import {readRecoveryCheckpoint,createCheckpointWriter,clearVerifiedDeadControl} from '../src/managed-recovery.mjs';
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';

const usage='AI Presentation Agent managed session: node scripts/managed-server.mjs\n'+
  'Runs a private local presentation control API on 127.0.0.1; stop with SIGTERM.\n';
if(process.argv.includes('--help')||process.argv.includes('-h')){
 process.stdout.write(usage);process.exit(0);
}
async function run(){
 const paths=await setupPrivateState();
 const token=randomBytes(32).toString('hex');
 const viewerToken=randomBytes(32).toString('hex');
 const stageToken=randomBytes(32).toString('hex');
 const streamToken=randomBytes(32).toString('hex');
 const instanceId=randomUUID();
 let recoveredSession=null;
 try{recoveredSession=await readRecoveryCheckpoint(paths);}
 catch(error){
   process.stderr.write('Private crash checkpoint could not be restored. Manual load required.\n');
 }
 const coreHandler=createMcpHandler({
   allowExternalControl:process.env.PRESENTATION_ALLOW_EXTERNAL_CONTROL==='1',
   allowWorshipLookChanges:process.env.PRESENTATION_ALLOW_WORSHIP_LOOK_EDIT==='1',
   allowStageClockControl:process.env.PRESENTATION_ALLOW_STAGE_CLOCK==='1',
   allowTelepromptControl:process.env.PRESENTATION_ALLOW_TELEPROMPT==='1',
   recoveredSession,stageGrant:stageToken
 });
 const checkpoint=createCheckpointWriter(paths);
 const changingTools=new Set([
   'presentation_load','presentation_load_worship','presentation_load_worship_library',
   'presentation_create','presentation_start','presentation_command',
   'presentation_cue','presentation_voice','presentation_watch','presentation_select_output',
   'presentation_arm'
 ]);
 const handler=async request=>{
   const result=await coreHandler(request);
   if(request?.method==='tools/call'&&request?.params?.name==='presentation_unload'&&
      !result?.result?.isError&&!result?.error){
     try{await checkpoint.clear();}
     catch{
       process.stderr.write('Private checkpoint clearing needs owner review.\n');
       // Unload is idempotent, so a retry after storage repair is safe. Do not
       // claim that private deck content was removed until the disk agrees.
       return {...result,result:{isError:true,content:[{
         type:'text',text:'Private recovery checkpoint could not be cleared. Repair owner state storage and retry unload.'
       }]}};
     }
   }
   if(request?.method==='tools/call'&&changingTools.has(request?.params?.name)&&
      !result?.result?.isError&&!result?.error){
     try{
       const status=await coreHandler({jsonrpc:'2.0',id:'checkpoint',method:'tools/call',
         params:{name:'presentation_status',arguments:{}}});
       await checkpoint.save(status?.result?.structuredContent);
     }catch(error){
       // The physical operation may already have committed. Preserve its
       // original receipt rather than telling an AI host to blindly replay it.
       process.stderr.write('Private checkpoint write unavailable; control receipt preserved.\n');
     }
   }
   return result;
 };
 handler.subscribe=coreHandler.subscribe;
 handler.getPrivateStageCue=coreHandler.getPrivateStageCue;
 handler.getPrivateStageClock=coreHandler.getPrivateStageClock;
 handler.updatePrivateStageClock=coreHandler.updatePrivateStageClock;
 handler.getPrivateTeleprompt=coreHandler.getPrivateTeleprompt;
 handler.updatePrivateTeleprompt=coreHandler.updatePrivateTeleprompt;
 handler.getBroadcastCue=coreHandler.getBroadcastCue;
 const server=createHttpServer({handler,token,viewerToken,stageToken,streamToken});
 const address=await new Promise((resolve,reject)=>{
   const errored=error=>reject(error);
   server.once('error',errored);
   server.listen(0,'127.0.0.1',()=>{
     server.removeListener('error',errored);
     resolve(server.address());
   });
 });
 const state={instanceId,port:address.port,token,viewerToken,stageToken,streamToken,pid:process.pid,createdAt:Date.now()};
 try{
   // Exclusive write means another running owner session cannot be replaced.
   await writeFile(paths.file,JSON.stringify(state),{encoding:'utf8',mode:0o600,flag:'wx'});
 }catch(error){
   if(error.code==='EEXIST'){
     // A killed process may leave an owner-only bearer file. Never take it
     // over if the PID is still alive or its identity cannot be established.
     try{
       await clearVerifiedDeadControl(paths,{
         readCurrent:()=>readPrivateState({PRESENTATION_AGENT_STATE_DIR:paths.dir})
       });
       await writeFile(paths.file,JSON.stringify(state),{
         encoding:'utf8',mode:0o600,flag:'wx'
       });
     }catch(recoveryError){
       await new Promise(resolve=>server.close(resolve));
       throw recoveryError;
     }
   }else{
     await new Promise(resolve=>server.close(resolve));
     throw error;
   }
 }
 process.stderr.write('Presentation session ready on private loopback port '+state.port+'.\n');
 let closing=false;
 const close=async()=>{
   if(closing)return;
   closing=true;
   server.closeAllConnections();
   await new Promise(resolve=>server.close(resolve));
   try{await checkpoint.flush();}
   catch{process.stderr.write('Private checkpoint flush requires review.\n');}
   try{
     const onDisk=JSON.parse(await readFile(paths.file,'utf8'));
     if(onDisk.instanceId===instanceId)await unlink(paths.file);
   }catch(error){
     if(error.code!=='ENOENT')process.stderr.write('State cleanup needs review: '+error.message+'\n');
   }
 };
 for(const sig of ['SIGTERM','SIGINT']){
   process.once(sig,()=>{void close().then(()=>process.exit(0),error=>{
     process.stderr.write('Shutdown error: '+error.message+'\n');process.exit(1);
   });});
 }
}
run().catch(error=>{process.stderr.write('Managed session startup failed: '+error.message+'\n');process.exitCode=2;});
