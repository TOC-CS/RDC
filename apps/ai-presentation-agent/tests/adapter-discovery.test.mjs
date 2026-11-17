import test from 'node:test';
import assert from 'node:assert/strict';
import {createMcpHandler} from '../src/mcp.mjs';
import {registerPresentationAdapter} from '../src/adapters.mjs';

test('AI hosts can discover registered source-bound RDC presentation adapters',async()=>{
 const unregister=registerPresentationAdapter('rdc-owner-preview-check',()=>({
  name:'rdc-owner-preview-check',
  external:true,
  show:async()=>({ok:true})
 }));
 try{
   const handler=createMcpHandler();
   const out=await handler({jsonrpc:'2.0',id:1,method:'tools/call',params:{
     name:'presentation_capabilities',arguments:{}
   }});
   assert.equal(out.result.isError,undefined);
   const caps=out.result.structuredContent;
   assert.ok(caps.availableCustomAdapters.includes('rdc-owner-preview-check'));
   assert.ok(caps.exportFormats.includes('pptx'));
 }finally{unregister();}
});
test('unregistered adapters never appear as available to subsequent AI sessions',async()=>{
 const handler=createMcpHandler();
 const out=await handler({jsonrpc:'2.0',id:1,method:'tools/call',params:{
  name:'presentation_capabilities',arguments:{}
 }});
 assert.ok(!out.result.structuredContent.availableCustomAdapters.includes('rdc-owner-preview-check'));
});
