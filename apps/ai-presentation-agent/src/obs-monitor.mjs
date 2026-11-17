import {randomUUID} from 'node:crypto';
import {obsWebsocketAuth} from './adapters.mjs';

const READ_ONLY_REQUESTS=Object.freeze([
  'GetSceneList','GetCurrentProgramScene','GetStreamStatus','GetRecordStatus'
]);
const OBS_STUDIO_DIAGNOSTIC_REQUESTS=Object.freeze([
  'GetStudioModeEnabled','GetStats'
]);
function validateObsStatistics(value){
 if(!value||typeof value!=='object'||Array.isArray(value))
   throw new Error('OBS production statistics response is invalid.');
 const nonnegative=['cpuUsage','memoryUsage','availableDiskSpace','activeFps','averageFrameRenderTime'];
 const counters=['renderSkippedFrames','renderTotalFrames','outputSkippedFrames','outputTotalFrames'];
 for(const key of nonnegative){
   if(!Number.isFinite(value[key])||value[key]<0)
     throw new Error('OBS production statistics contain invalid '+key+'.');
 }
 for(const key of counters){
   if(!Number.isSafeInteger(value[key])||value[key]<0)
     throw new Error('OBS production statistics contain invalid '+key+'.');
 }
 if(value.renderSkippedFrames>value.renderTotalFrames||
    value.outputSkippedFrames>value.outputTotalFrames)
   throw new Error('OBS frame counters are inconsistent.');
 const percent=(skipped,total)=>total===0?null:
   Number((100*skipped/total).toFixed(2));
 return Object.freeze({
   cpuUsagePercent:value.cpuUsage,memoryMB:value.memoryUsage,
   recordingDiskSpaceMB:value.availableDiskSpace,
   activeFps:value.activeFps,averageFrameRenderMs:value.averageFrameRenderTime,
   renderSkippedFrames:value.renderSkippedFrames,
   renderTotalFrames:value.renderTotalFrames,
   renderDropPercent:percent(value.renderSkippedFrames,value.renderTotalFrames),
   outputSkippedFrames:value.outputSkippedFrames,
   outputTotalFrames:value.outputTotalFrames,
   outputDropPercent:percent(value.outputSkippedFrames,value.outputTotalFrames),
   localSoftwareMetricsOnly:true,remotePlatformPreviewVerified:false
 });
}

const checkLocalUrl=raw=>{
  const parsed=new URL(raw);
  if(parsed.protocol!=='ws:'||
    !['127.0.0.1','localhost','[::1]'].includes(parsed.hostname)||
    parsed.username||parsed.password||parsed.search||parsed.hash||parsed.pathname!=='/')
    throw new Error('OBS monitor requires an explicitly selected local WebSocket endpoint.');
  return parsed.href;
};
const sceneName=value=>typeof value==='string'&&value.length<=200?value:null;

export class OBSReadOnlyMonitor{
 constructor({url='ws://127.0.0.1:4455/',password='',WebSocketCtor=globalThis.WebSocket,
    timeoutMs=3000,includeProductionMetrics=false}={}){
   this.url=checkLocalUrl(url);
   if(typeof password!=='string'||password.length>512)
     throw new Error('Invalid local OBS WebSocket password configuration.');
   if(typeof WebSocketCtor!=='function')
     throw new Error('A standards-compatible WebSocket constructor is required.');
   if(!Number.isInteger(timeoutMs)||timeoutMs<250||timeoutMs>10000)
     throw new Error('OBS read-only monitor timeout must be 250 to 10000 milliseconds.');
   if(typeof includeProductionMetrics!=='boolean')
     throw new Error('OBS production metrics option must be boolean.');
   this.password=password;this.WebSocketCtor=WebSocketCtor;this.timeoutMs=timeoutMs;
   this.includeProductionMetrics=includeProductionMetrics;
 }
 async inspect(){
   const connection=new this.WebSocketCtor(this.url);
   const requests=[...READ_ONLY_REQUESTS,
     ...(this.includeProductionMetrics?OBS_STUDIO_DIAGNOSTIC_REQUESTS:[])];
   return new Promise((resolve,reject)=>{
     let settled=false,identified=false,position=0,requestId=null;
     const responses={};
     const finish=(error,result)=>{
       if(settled)return;
       settled=true;clearTimeout(timer);
       try{connection.close();}catch{}
       return error?reject(error):resolve(result);
     };
     const timer=setTimeout(()=>finish(new Error('OBS read-only monitor timed out.')),this.timeoutMs);
     const next=()=>{
       if(position>=requests.length){
         const scenes=responses.GetSceneList;
         const program=responses.GetCurrentProgramScene;
         const streaming=responses.GetStreamStatus;
         const recording=responses.GetRecordStatus;
         if(!Array.isArray(scenes?.scenes)||scenes.scenes.length>300||
           typeof streaming?.outputActive!=='boolean'||
           typeof recording?.outputActive!=='boolean')
           return finish(new Error('OBS read-only status fields are incomplete.'));
         const items=scenes.scenes.map(item=>{
           const name=sceneName(item?.sceneName);
           if(!name)throw new Error('OBS scene list contains invalid scene identity.');
           return name;
         });
         const current=sceneName(program?.sceneName??program?.currentProgramSceneName);
         const listCurrent=sceneName(scenes.currentProgramSceneName);
         if(!current)return finish(new Error('OBS current Program scene is unavailable.'));
         const listPreview=sceneName(scenes.currentPreviewSceneName);
         const studio=this.includeProductionMetrics?
           responses.GetStudioModeEnabled?.studioModeEnabled:null;
         if(this.includeProductionMetrics&&typeof studio!=='boolean')
           return finish(new Error('OBS Studio Mode readback unavailable.'));
         const nativePreview=studio?
           sceneName(responses.GetCurrentPreviewScene?.sceneName??
           responses.GetCurrentPreviewScene?.currentPreviewSceneName):null;
         if(studio&&nativePreview===null)
           return finish(new Error('OBS independent Preview readback unavailable.'));
         let statistics=null;
         if(this.includeProductionMetrics){
           try{statistics=validateObsStatistics(responses.GetStats);}
           catch(error){return finish(error);}
         }
         const preview=this.includeProductionMetrics?nativePreview:listPreview;
         return finish(null,{
           schema:'toc.presentation.obs-readonly/v1',
           source:'OBS WebSocket 5',
           connected:true,requestTypes:[...requests],
           sceneNames:items,
           programScene:current,
           previewScene:preview,
           studioPreviewAvailable:preview!==null,
           ...(this.includeProductionMetrics?{
             studioModeEnabled:studio,
             previewReadbackMatchesSceneList:studio?
               (listPreview===null?null:listPreview===preview):null,
             statistics
           }:{}),
           programReadbackMatchesSceneList:listCurrent===null?null:listCurrent===current,
           streamingActive:streaming.outputActive,
           streamReconnecting:streaming.outputReconnecting===true,
           recordingActive:recording.outputActive,
           recordingPaused:recording.outputPaused===true,
           outputWritesPerformed:false,
           streamOrRecordingChanged:false,
           liveHardwareOrProviderAccepted:false
         });
       }
       requestId='readonly-'+randomUUID();
       connection.send(JSON.stringify({op:6,d:{
         requestType:requests[position],requestId
       }}));
     };
     connection.addEventListener('error',()=>finish(new Error('OBS WebSocket status connection failed.')));
     connection.addEventListener('close',()=>{if(!settled)finish(new Error('OBS status connection closed.'));});
     connection.addEventListener('message',event=>{
       let message;
       try{message=JSON.parse(String(event.data));}
       catch{return finish(new Error('Invalid OBS status JSON.'));}
       if(message.op===0){
         const data={rpcVersion:1};
         if(message.d?.authentication){
           if(!this.password)return finish(new Error('OBS authentication is required for status access.'));
           data.authentication=obsWebsocketAuth(
             this.password,message.d.authentication.salt,message.d.authentication.challenge);
         }
         connection.send(JSON.stringify({op:1,d:data}));
       }else if(message.op===2){
         if(message.d?.negotiatedRpcVersion!==1)
           return finish(new Error('Unsupported OBS WebSocket RPC version.'));
         identified=true;next();
       }else if(message.op===7&&identified){
         const expected=requests[position];
         if(message.d?.requestId!==requestId||message.d?.requestType!==expected)return;
         if(message.d?.requestStatus?.result!==true)
           return finish(new Error('OBS read-only request failed: '+expected));
         const data=message.d?.responseData;
         if(!data||typeof data!=='object'||Array.isArray(data))
           return finish(new Error('OBS read-only response missing status fields.'));
         responses[expected]=data;
         if(expected==='GetStudioModeEnabled'&&data.studioModeEnabled===true)
           requests.push('GetCurrentPreviewScene');
         position++;
         try{next();}catch(error){finish(error);}
       }
     });
   });
 }
}
