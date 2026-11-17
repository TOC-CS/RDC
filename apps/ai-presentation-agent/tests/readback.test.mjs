import test from 'node:test';
import assert from 'node:assert/strict';
import {ProPresenterAdapter,MemoryAdapter} from '../src/adapters.mjs';
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';

const payload={presentation:{index:2,presentation_id:{uuid:'123e4567-e89b-12d3-a456-426614174000'}},announcements:null};
const newAdapter=(data=payload)=>new ProPresenterAdapter({
 baseUrl:'http://127.0.0.1:50001',
 fetcher:async url=>{
   assert.equal(new URL(url).pathname,'/v1/presentation/slide_index');
   return {ok:true,status:200,json:async()=>data};
 }
});
test('ProPresenter readback parses the real active presentation cue index',async()=>{
 const output=await newAdapter().readback({expectedIndex:2});
 assert.equal(output.supported,true);
 assert.equal(output.confirmed,true);
 assert.equal(output.index,2);
 assert.equal(output.presentationId,'123e4567-e89b-12d3-a456-426614174000');
 assert.equal(output.source,'propresenter-api');
});
test('ProPresenter reports a changed cue mismatch without inventing success',async()=>{
 const output=await newAdapter().readback({expectedIndex:1});
 assert.equal(output.confirmed,false);
 assert.equal(output.index,2);
});
test('ProPresenter malformed active-cue response cannot be reported as verified',async()=>{
 await assert.rejects(()=>newAdapter({presentation:{index:'two'}}).readback({expectedIndex:2}),/cue|index|invalid/i);
});
test('Presentation readback tool reports unavailable capability accurately',async()=>{
 const handler=createMcpHandler({adapter:new MemoryAdapter()});
 const out=await handler({jsonrpc:'2.0',id:1,method:'tools/call',
  params:{name:'presentation_readback',arguments:{}}});
 assert.equal(out.result.isError,undefined);
 assert.equal(out.result.structuredContent.supported,false);
 assert.equal(out.result.structuredContent.confirmed,false);
});
test('MCP readback checks external output without arming external writes',async()=>{
 const handler=createMcpHandler({adapter:newAdapter()});
 await handler({jsonrpc:'2.0',id:1,method:'tools/call',
  params:{name:'presentation_load',arguments:{deck:{slides:[{id:'a'},{id:'b'},{id:'c'}]}}}});
 const out=await handler({jsonrpc:'2.0',id:2,method:'tools/call',
  params:{name:'presentation_readback',arguments:{}}});
 assert.equal(out.result.structuredContent.confirmed,false);
 assert.equal(out.result.structuredContent.reason,'output_not_running');
 assert.equal(out.result.structuredContent.index,2);
 const status=await handler({jsonrpc:'2.0',id:3,method:'tools/call',
  params:{name:'presentation_status',arguments:{}}});
 assert.equal(status.result.structuredContent.armed,false);
});
test('HTTP readback requires the same bearer token as other API endpoints',async()=>{
 const token='local-readback-token-2026';
 const handler=createMcpHandler({adapter:newAdapter()});
 const server=createHttpServer({handler,token});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 try{
   const url='http://127.0.0.1:'+server.address().port+'/v1/readback';
   assert.equal((await fetch(url)).status,401);
   const reply=await fetch(url,{headers:{Authorization:'Bearer '+token}});
   assert.equal(reply.status,200);
   const data=await reply.json();
   assert.equal(data.supported,true);
 }finally{await new Promise(r=>server.close(r));}
});
test('ProPresenter identical slide indexes in a different presentation do not count as confirmed',async()=>{
 const readback=await newAdapter().readback({
   expectedIndex:2,expectedPresentationId:'AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE'
 });
 assert.equal(readback.index,2);
 assert.equal(readback.confirmed,false);
});
