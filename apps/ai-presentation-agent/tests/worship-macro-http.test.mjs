import test from 'node:test';
import assert from 'node:assert/strict';
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';
const token='operator-safe-preview-token-2026';
const deck={slides:[{id:'opening'},{id:'sermon'}]};
const macro={name:'Sermon Start',steps:[
 {action:'hold'},
 {action:'show-slide',slideId:'sermon'},
 {action:'set-obs-preview',scene:'Pastor Camera'},
 {action:'set-obs-program',scene:'Sermon Camera'},
 {action:'stage-message',text:'PRIVATE_STAGE_TALKBACK_NOTE'},
 {action:'start-stream'}
]};
const call=async(h,id,name,args={})=>{
 const result=await h({jsonrpc:'2.0',id,method:'tools/call',
   params:{name,arguments:args}});
 assert.equal(result?.result?.isError,undefined,JSON.stringify(result));
 return result.result.structuredContent;
};
test('AI MCP can preview a worship macro without changing the director or projecting stage notes',async()=>{
 const h=createMcpHandler();
 await call(h,1,'presentation_load',{deck});
 const before=await call(h,2,'presentation_status');
 const result=await call(h,3,'presentation_worship_macro_preview',{macro});
 const after=await call(h,4,'presentation_status');
 assert.equal(result.executionAllowed,false);
 assert.equal(result.applied,false);
 assert.equal(JSON.stringify(result).includes('PRIVATE_STAGE'),false);
 assert.deepEqual(before,after);
});
test('authenticated HTTP macro preview does not launch stream, OBS, record or stage output',async()=>{
 const h=createMcpHandler();
 const server=createHttpServer({handler:h,token});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const base='http://127.0.0.1:'+server.address().port;
 const post=(path,payload,auth=null)=>fetch(base+path,{method:'POST',headers:{
   'Content-Type':'application/json',...(auth?{Authorization:'Bearer '+auth}:{})
 },body:JSON.stringify(payload)});
 try{
   assert.equal((await post('/v1/load',{deck},token)).status,200);
   assert.equal((await post('/v1/worship/macro/preview',{macro})).status,401);
   const result=await post('/v1/worship/macro/preview',{macro},token);
   assert.equal(result.status,200);
   const output=await result.json();
   assert.equal(output.executionAllowed,false);
   assert.equal(output.streamingOrRecordingChanged,false);
   assert.equal(JSON.stringify(output).includes('PRIVATE_STAGE'),false);
   const state=await call(h,3,'presentation_status');
   assert.equal(state.started,false);
   assert.equal(state.index,0);
 }finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});
