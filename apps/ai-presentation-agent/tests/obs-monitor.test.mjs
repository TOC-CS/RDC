import test from 'node:test';
import assert from 'node:assert/strict';
import {OBSReadOnlyMonitor} from '../src/obs-monitor.mjs';

const requested=[];
class MockReadOnlyOBS extends EventTarget{
 constructor(url){
   super();
   assert.equal(url,'ws://127.0.0.1:4455/');
   queueMicrotask(()=>this.receive({op:0,d:{obsWebSocketVersion:'5.2.0',rpcVersion:1}}));
 }
 receive(value){this.dispatchEvent(new MessageEvent('message',{data:JSON.stringify(value)}));}
 send(raw){
   const message=JSON.parse(raw);
   if(message.op===1){
     return queueMicrotask(()=>this.receive({op:2,d:{negotiatedRpcVersion:1}}));
   }
   assert.equal(message.op,6);
   requested.push(message.d.requestType);
   const responses={
     GetSceneList:{scenes:[{sceneName:'Camera Wide'},{sceneName:'Sermon Camera'}],
       currentProgramSceneName:'Camera Wide',currentPreviewSceneName:'Sermon Camera'},
     GetCurrentProgramScene:{sceneName:'Camera Wide'},
     GetStreamStatus:{outputActive:false,outputReconnecting:false},
     GetRecordStatus:{outputActive:true,outputPaused:false}
   };
   queueMicrotask(()=>this.receive({op:7,d:{
     requestType:message.d.requestType,
     requestId:message.d.requestId,
     requestStatus:{result:true,code:100},
     responseData:responses[message.d.requestType]
   }}));
 }
 close(){this.closed=true;}
}
test('OBS monitor only queries SceneList, Program, Stream and Record statuses',async()=>{
 requested.length=0;
 const monitor=new OBSReadOnlyMonitor({WebSocketCtor:MockReadOnlyOBS});
 const value=await monitor.inspect();
 assert.deepEqual(value.requestTypes,[
   'GetSceneList','GetCurrentProgramScene','GetStreamStatus','GetRecordStatus'
 ]);
 assert.deepEqual(requested,value.requestTypes);
 assert.equal(value.programScene,'Camera Wide');
 assert.equal(value.previewScene,'Sermon Camera');
 assert.equal(value.studioPreviewAvailable,true);
 assert.equal(value.streamingActive,false);
 assert.equal(value.recordingActive,true);
 assert.equal(value.outputWritesPerformed,false);
 assert.equal(value.streamOrRecordingChanged,false);
});
test('OBS monitor rejects nonlocal targets and embedded credentials',()=>{
 for(const url of ['ws://example.com:4455/','wss://127.0.0.1:4455/',
   'ws://user:pass@127.0.0.1:4455/','ws://127.0.0.1:4455/?token=s',
   'ws://127.0.0.1:4455/remote'])
   assert.throws(()=>new OBSReadOnlyMonitor({url}),/local WebSocket/i);
});
test('OBS monitor does not silently permit an unsupported streaming-control API',()=>{
 const monitor=new OBSReadOnlyMonitor({WebSocketCtor:MockReadOnlyOBS});
 assert.equal(typeof monitor.startStream,'undefined');
 assert.equal(typeof monitor.stopStream,'undefined');
 assert.equal(typeof monitor.startRecording,'undefined');
 assert.equal(typeof monitor.setProgramScene,'undefined');
});
