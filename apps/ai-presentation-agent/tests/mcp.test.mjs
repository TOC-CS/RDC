import test from 'node:test';
import assert from 'node:assert/strict';
import {createMcpHandler} from '../src/mcp.mjs';

const deck={title:'Training',slides:[{id:'hello',title:'Hello'},{id:'part',title:'Part Two',text:'A thoughtful discussion',cues:['a thoughtful discussion']}]};
const rpc=(method,params={},id=1)=>({jsonrpc:'2.0',id,method,params});
test('MCP exposes discovery and tool schemas to compatible AI hosts',async()=>{
 const bridge=createMcpHandler();
 const init=await bridge(rpc('initialize',{protocolVersion:'2025-06-18',capabilities:{},clientInfo:{name:'test',version:'1'}}));
 assert.equal(init.result.serverInfo.name,'ai-presentation-agent');
 const tools=await bridge(rpc('tools/list'));
 assert.ok(tools.result.tools.some(v=>v.name==='presentation_voice'));
 assert.ok(tools.result.tools.some(v=>v.name==='presentation_cue'));
 assert.ok(tools.result.tools.some(v=>v.name==='presentation_create'));
});
test('MCP lets host AI load, start, control, and speak without local STT',async()=>{
 const bridge=createMcpHandler();
 async function call(name,args){
   const out=await bridge(rpc('tools/call',{name,arguments:args}));
   assert.equal(out.result.isError,undefined,JSON.stringify(out));
   return out.result.structuredContent;
 }
 await call('presentation_load',{deck});
 await call('presentation_start',{mode:'assisted'});
 const r=await call('presentation_voice',{transcript:'presentation agent next slide',final:true,confidence:.99});
 assert.equal(r.accepted,true);
 assert.equal(r.speakByHost,true);
 const state=await call('presentation_status',{});
 assert.equal(state.current.id,'part');
});
test('MCP refuses to arm external app without out-of-band operator approval',async()=>{
 const bridge=createMcpHandler();
 const result=await bridge(rpc('tools/call',{name:'presentation_arm',arguments:{enabled:true}}));
 assert.equal(result.result.isError,true);
 assert.match(result.result.content[0].text,/external control|approval/i);
});
test('MCP rejects malformed JSON-RPC and invalid parameters without mutating state',async()=>{
 const bridge=createMcpHandler();
 const res=await bridge(rpc('tools/call',{name:'presentation_load',arguments:{deck:{slides:[]}}}));
 assert.equal(res.result.isError,true);
 const status=await bridge(rpc('tools/call',{name:'presentation_status',arguments:{}}));
 assert.equal(status.result.structuredContent.started,false);
});
