import test from 'node:test';
import assert from 'node:assert/strict';
import {PresentationDirector} from '../src/director.mjs';
import {MemoryAdapter} from '../src/adapters.mjs';
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';
import {createCheckpointWriter,readRecoveryCheckpoint} from '../src/managed-recovery.mjs';
import {mkdtemp,rm} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';

const deck={slides:[{id:'one'},{id:'two'}]};
const rpc=(id,name,args={})=>({jsonrpc:'2.0',id,method:'tools/call',
 params:{name,arguments:args}});
test('unload requires stop, clears saved deck position, leaves external outputs disarmed',async()=>{
 const d=new PresentationDirector({adapter:new MemoryAdapter()});
 d.load(deck);await d.start('manual');
 await assert.rejects(async()=>d.unload(),/stop|running/i);
 assert.equal(d.snapshot().current.id,'one');
 await d.command({action:'stop'});
 const cleared=d.unload();
 assert.equal(cleared.started,false);
 assert.equal(cleared.armed,false);
 assert.equal(cleared.slides.length,0);
 assert.equal(cleared.current,null);
 assert.equal(cleared.title,null);
 d.load(deck);await d.start('manual');
 assert.equal(d.snapshot().current.id,'one');
});
test('unload clears private recovery checkpoint and never resurrects stale content',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'presentation-clear-test-'));
 const paths={dir,file:join(dir,'control.json')};
 try{
   const checkpoint=createCheckpointWriter(paths);
   await checkpoint.save({title:'Private lyrics',theme:'dark',index:1,slides:deck.slides});
   assert.equal((await readRecoveryCheckpoint(paths)).index,1);
   await checkpoint.clear();
   assert.equal(await readRecoveryCheckpoint(paths),null);
   await checkpoint.flush();
 }finally{await rm(dir,{recursive:true,force:true});}
});
test('MCP and authenticated HTTP provide a stopped-only unload endpoint',async()=>{
 const handler=createMcpHandler();
 const resp=await handler(rpc(1,'presentation_load',{deck}));
 assert.equal(resp.result.isError,undefined);
 const server=createHttpServer({handler,token:'unload-operator-only-2026'});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const url='http://127.0.0.1:'+server.address().port+'/v1/unload';
 const call=()=>fetch(url,{method:'POST',headers:{
   Authorization:'Bearer unload-operator-only-2026',
   'Content-Type':'application/json'},body:'{}'});
 try{
   await handler(rpc(2,'presentation_start',{mode:'automatic'}));
   assert.equal((await call()).status,422);
   await handler(rpc(3,'presentation_stop'));
   const cleared=await call();
   assert.equal(cleared.status,200);
   assert.equal((await cleared.json()).slides.length,0);
   assert.equal((await handler(rpc(4,'presentation_status'))).result.structuredContent.current,null);
 }finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});
