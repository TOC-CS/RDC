import test from 'node:test';
import assert from 'node:assert/strict';
import {OBSReadOnlyMonitor} from '../src/obs-monitor.mjs';

class OBSStudioFixture extends EventTarget {
 static studio=true;
 static badStats=false;
 static requested=[];
 constructor(url){
  super();
  assert.match(url,/^ws:\/\/127\.0\.0\.1/);
  queueMicrotask(()=>this.incoming({op:0,d:{rpcVersion:1,obsWebSocketVersion:'5.2.0'}}));
 }
 incoming(message){this.dispatchEvent(new MessageEvent('message',{data:JSON.stringify(message)}));}
 send(raw){
  const req=JSON.parse(raw);
  if(req.op===1)return queueMicrotask(()=>this.incoming({op:2,d:{negotiatedRpcVersion:1}}));
  assert.equal(req.op,6);
  OBSStudioFixture.requested.push(req.d.requestType);
  const responses={
   GetSceneList:{scenes:[{sceneName:'Wide Camera'},{sceneName:'Pastor Camera'}],
     currentProgramSceneName:'Wide Camera',
     currentPreviewSceneName:OBSStudioFixture.studio?'Pastor Camera':null},
   GetCurrentProgramScene:{sceneName:'Wide Camera'},
   GetStreamStatus:{outputActive:false,outputReconnecting:false,
     outputSkippedFrames:3,outputTotalFrames:1000},
   GetRecordStatus:{outputActive:true,outputPaused:false},
   GetStudioModeEnabled:{studioModeEnabled:OBSStudioFixture.studio},
   GetCurrentPreviewScene:{sceneName:'Pastor Camera'},
   GetStats:{cpuUsage:8.2,memoryUsage:750,availableDiskSpace:120000,
     activeFps:30,averageFrameRenderTime:4.1,
     renderSkippedFrames:OBSStudioFixture.badStats?-1:12,
     renderTotalFrames:1200,outputSkippedFrames:3,outputTotalFrames:1200}
  };
  assert.ok(Object.hasOwn(responses,req.d.requestType),
   'Read-only monitor must not issue production write '+req.d.requestType);
  queueMicrotask(()=>this.incoming({op:7,d:{
    requestId:req.d.requestId,requestType:req.d.requestType,
    requestStatus:{result:true,code:100},responseData:responses[req.d.requestType]
  }}));
 }
 close(){this.closed=true;}
}
test('extended read-only OBS monitor separately checks Studio Mode, independent Preview and performance statistics',async()=>{
 OBSStudioFixture.studio=true;OBSStudioFixture.badStats=false;
 OBSStudioFixture.requested.length=0;
 const monitor=new OBSReadOnlyMonitor({WebSocketCtor:OBSStudioFixture,includeProductionMetrics:true});
 const report=await monitor.inspect();
 assert.equal(report.programScene,'Wide Camera');
 assert.equal(report.previewScene,'Pastor Camera');
 assert.equal(report.studioModeEnabled,true);
 assert.equal(report.previewReadbackMatchesSceneList,true);
 assert.equal(report.statistics.activeFps,30);
 assert.equal(report.statistics.renderDropPercent,1);
 assert.equal(report.statistics.outputDropPercent,.25);
 assert.equal(report.streamOrRecordingChanged,false);
 assert.deepEqual(report.requestTypes,OBSStudioFixture.requested);
 assert.deepEqual(OBSStudioFixture.requested,[
   'GetSceneList','GetCurrentProgramScene','GetStreamStatus','GetRecordStatus',
   'GetStudioModeEnabled','GetStats','GetCurrentPreviewScene'
 ]);
});
test('Studio Mode off does not request unavailable Preview scene',async()=>{
 OBSStudioFixture.studio=false;OBSStudioFixture.badStats=false;
 OBSStudioFixture.requested.length=0;
 const report=await new OBSReadOnlyMonitor({
   WebSocketCtor:OBSStudioFixture,includeProductionMetrics:true
 }).inspect();
 assert.equal(report.studioModeEnabled,false);
 assert.equal(report.previewScene,null);
 assert.equal(report.previewReadbackMatchesSceneList,null);
 assert.equal(OBSStudioFixture.requested.includes('GetCurrentPreviewScene'),false);
 assert.equal(report.statistics.renderDropPercent,1);
});
test('invalid OBS hardware metrics fail instead of reporting fabricated healthy stream',async()=>{
 OBSStudioFixture.studio=true;OBSStudioFixture.badStats=true;
 await assert.rejects(()=>new OBSReadOnlyMonitor({
   WebSocketCtor:OBSStudioFixture,includeProductionMetrics:true
 }).inspect(),/statistics|frame|invalid|metrics/i);
 OBSStudioFixture.badStats=false;
});
test('legacy OBS monitor retains its original four read-only requests',async()=>{
 OBSStudioFixture.studio=true;OBSStudioFixture.requested.length=0;
 const report=await new OBSReadOnlyMonitor({WebSocketCtor:OBSStudioFixture}).inspect();
 assert.equal(report.requestTypes.length,4);
 assert.equal(report.statistics,undefined);
 assert.equal(OBSStudioFixture.requested.includes('GetStudioModeEnabled'),false);
});
