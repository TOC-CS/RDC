import test from 'node:test';
import assert from 'node:assert/strict';
import {createMcpHandler} from '../src/mcp.mjs';

const rpc=(id,name,args={})=>({jsonrpc:'2.0',id,method:'tools/call',
   params:{name,arguments:args}});

test('MCP session offers an in-process read-only subscription to immediate slide changes',async()=>{
 const handler=createMcpHandler();
 assert.equal(typeof handler.subscribe,'function');
 const states=[];
 const unsubscribe=handler.subscribe(state=>states.push(state.current?.id??null));
 assert.equal(typeof unsubscribe,'function');
 await handler(rpc(1,'presentation_load',{deck:{slides:[{id:'first'},{id:'second'}]}}));
 await handler(rpc(2,'presentation_start',{mode:'manual'}));
 await handler(rpc(3,'presentation_command',{action:'next'}));
 assert.ok(states.includes('second'));
 const count=states.length;unsubscribe();
 await handler(rpc(4,'presentation_command',{action:'previous'}));
 assert.equal(states.length,count,'Unsubscribed viewer must receive no more events.');
});
test('slide-change subscription follows replaced output adapter without leaking old notifications',async()=>{
 const handler=createMcpHandler();
 const ids=[];
 const stop=handler.subscribe(s=>ids.push(s.current?.id??null));
 await handler(rpc(1,'presentation_load',{deck:{slides:[{id:'a'},{id:'b'}]}}));
 const replace=await handler(rpc(2,'presentation_select_output',{kind:'web-deck'}));
 assert.equal(replace.result.isError,undefined);
 await handler(rpc(3,'presentation_start',{mode:'manual'}));
 await handler(rpc(4,'presentation_command',{action:'next'}));
 stop();
 assert.equal(ids.at(-1),'b');
});
