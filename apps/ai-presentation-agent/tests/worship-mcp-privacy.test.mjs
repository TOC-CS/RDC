import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';

const path=fileURLToPath(new URL('../skills/ai-presentation-agent/worship/examples/sunday-service.json',import.meta.url));
const source=JSON.parse(await readFile(path,'utf8'));
const PRIV='UNANNOUNCED_PRAYER_REQUEST_MUST_STAY_PRIVATE';
source.items[0].notes=PRIV;
source.items[2].sections[0].notes=PRIV;
const rpc=async(handler,id,name,args={})=>{
 const output=await handler({jsonrpc:'2.0',id,method:'tools/call',
  params:{name,arguments:args}});
 if(output.result?.isError)throw new Error(output.result.content[0]?.text);
 return output.result?.structuredContent;
};
test('presentation_load_worship creates only public-whitelisted deck and saves a private stage cue',async()=>{
 const handler=createMcpHandler({stageGrant:'stage-private-one'});
 const state=await rpc(handler,1,'presentation_load_worship',{plan:source});
 assert.ok(state.slides.length>8);
 assert.equal(JSON.stringify(state).includes(PRIV),false);
 assert.equal((await rpc(handler,2,'presentation_status')).slides.length,state.slides.length);
 assert.equal(JSON.stringify(await rpc(handler,3,'presentation_status')).includes(PRIV),false);
 assert.equal(handler.getPrivateStageCue('incorrect'),null);
 assert.equal(handler.getPrivateStageCue('stage-private-one')?.current?.notes,PRIV);
 assert.equal(JSON.stringify(handler.getBroadcastCue()).includes(PRIV),false);
 await rpc(handler,4,'presentation_start',{mode:'manual'});
 await rpc(handler,5,'presentation_command',{action:'next'});
 assert.equal(handler.getPrivateStageCue('stage-private-one')?.current?.id,'welcome');
});
test('public viewer/REST payload excludes stage notes even when the stage view has them',async()=>{
 const handler=createMcpHandler({stageGrant:'stage-private-one'});
 const server=createHttpServer({handler,token:'control-only-for-worship-fixture',
 viewerToken:'viewer-only-for-worship-fixture'});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const base='http://127.0.0.1:'+server.address().port;
 try{
   const body=await fetch(base+'/v1/worship/load',{method:'POST',
    headers:{Authorization:'Bearer control-only-for-worship-fixture','Content-Type':'application/json'},
    body:JSON.stringify({plan:source})});
   assert.equal(body.status,200);
   assert.equal((await body.text()).includes(PRIV),false);
   const stat=await fetch(base+'/v1/status',
    {headers:{Authorization:'Bearer control-only-for-worship-fixture'}});
   assert.equal((await stat.text()).includes(PRIV),false);
   const html=await fetch(base+'/v1/viewer?key=viewer-only-for-worship-fixture');
   assert.equal(html.status,200);
   assert.equal((await html.text()).includes(PRIV),false);
 }finally{server.closeAllConnections();await new Promise(r=>server.close(r));}
});
test('ordinary deck load and unload drop private worship stage data',async()=>{
 const handler=createMcpHandler({stageGrant:'stage-private-one'});
 await rpc(handler,1,'presentation_load_worship',{plan:source});
 assert.ok(handler.getPrivateStageCue('stage-private-one'));
 await rpc(handler,2,'presentation_load',{deck:{slides:[{id:'replacement'}]}});
 assert.equal(handler.getPrivateStageCue('stage-private-one'),null);
 await rpc(handler,3,'presentation_load_worship',{plan:source});
 await rpc(handler,4,'presentation_unload');
 assert.equal(handler.getPrivateStageCue('stage-private-one'),null);
});
