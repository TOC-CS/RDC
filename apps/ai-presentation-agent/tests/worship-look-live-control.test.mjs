import test from 'node:test';
import assert from 'node:assert/strict';
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';

const tokens={token:'controller-operator-secret-2026',viewerToken:'audience-only-secret-2026',stageToken:'stage-only-secret-2026',streamToken:'stream-only-secret-2026'};
const SECRET='PRIVATE_PASTOR_COORDINATOR_NOTE';
const CHORD='F#m7';
const ROOM='Original room lyric must not stream';
const plan={title:'Independent Looks',items:[
 {id:'welcome',title:'Welcome',type:'announcement',text:'Welcome to worship',notes:SECRET},
 {id:'original-song',title:'New Original Song',type:'song',rights:{source:'original',displayAuthorized:true,streamAuthorized:false},
   sections:[{label:'chorus',lines:[ROOM],chords:[CHORD],notes:SECRET}],order:['chorus']}
]};
const rpc=(id,name,args={})=>({jsonrpc:'2.0',id,method:'tools/call',params:{name,arguments:args}});
const call=async(handler,id,name,args={})=>{
 const output=await handler(rpc(id,name,args));
 if(output?.result?.isError)throw new Error(output.result.content?.[0]?.text);
 return output.result.structuredContent;
};

test('unprivileged hosts cannot change an output Look after loading a worship service',async()=>{
 const handler=createMcpHandler({stageGrant:tokens.stageToken});
 await call(handler,1,'presentation_load_worship',{plan});
 const first=await call(handler,2,'presentation_worship_looks');
 assert.equal(first.revision,0);
 const denied=await handler(rpc(3,'presentation_worship_look_set',{
   destination:'broadcast',look:{layout:'minimal',layers:['text']}
 }));
 assert.equal(denied.result.isError,true);
 assert.match(denied.result.content[0].text,/grant|permission|operator/i);
 assert.equal((await call(handler,4,'presentation_worship_looks')).revision,0);
});
test('authorized output Look selection changes only its destination, never an OBS scene or a slide index',async()=>{
 const handler=createMcpHandler({stageGrant:tokens.stageToken,allowWorshipLookChanges:true});
 await call(handler,1,'presentation_load_worship',{plan});
 const before=await call(handler,2,'presentation_status');
 const changed=await call(handler,3,'presentation_worship_look_set',{
   destination:'broadcast',look:{layout:'minimal',background:'transparent',layers:['text']}
 });
 assert.equal(changed.revision,1);
 const output=handler.getBroadcastCue();
 assert.equal(output.look.layout,'minimal');
 assert.equal(output.current.title,'');
 assert.equal(output.current.text,'Welcome to worship');
 assert.equal(output.obsSceneChanged,false);
 assert.equal(JSON.stringify(output).includes(SECRET),false);
 assert.deepEqual(await call(handler,4,'presentation_status'),before);
 const stage=handler.getPrivateStageCue(tokens.stageToken);
 assert.equal(stage.current.notes,SECRET);
 const audience=handler.getAudienceLook();
 assert.equal(audience.layout,'fullscreen');
});
test('auth-separated SSE and GET payloads react to local Look changes and mask private data',async()=>{
 const handler=createMcpHandler({stageGrant:tokens.stageToken,allowWorshipLookChanges:true});
 const server=createHttpServer({handler,...tokens});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const origin='http://127.0.0.1:'+server.address().port;
 const post=async(path,data)=>{
   const response=await fetch(origin+path,{method:'POST',
     headers:{'Content-Type':'application/json',Authorization:'Bearer '+tokens.token},
     body:JSON.stringify(data)});
   return {status:response.status,body:await response.json()};
 };
 try{
   assert.equal((await post('/v1/worship/load',{plan})).status,200);
   assert.equal((await post('/v1/worship/looks/broadcast',{
     look:{layout:'minimal',background:'transparent',layers:['text']}
   })).status,200);
   const broadcast=handler.getBroadcastCue();
   assert.equal(broadcast.current.title,'');
   assert.equal(broadcast.look.layout,'minimal');
   assert.equal(broadcast.look.revision,1);
   const overlay=await fetch(origin+'/v1/stream-overlay?key='+tokens.streamToken);
   assert.equal(overlay.status,200);
   const html=await overlay.text();
   assert.match(html,/data-look/);
   for(const secret of [SECRET,CHORD,tokens.stageToken])assert.equal(html.includes(secret),false);
   const status=await fetch(origin+'/v1/status',{headers:{Authorization:'Bearer '+tokens.token}});
   const statusText=await status.text();
   for(const secret of [SECRET,CHORD])assert.equal(statusText.includes(secret),false);
   assert.equal((await post('/v1/command',{action:'next'})).status,422);
 }finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});
test('load and unload clear stale customized Looks and never retain stage data',async()=>{
 const handler=createMcpHandler({stageGrant:tokens.stageToken,allowWorshipLookChanges:true});
 await call(handler,1,'presentation_load_worship',{plan});
 await call(handler,2,'presentation_worship_look_set',{destination:'stage',look:{layout:'confidence',layers:['title','text']}});
 assert.deepEqual(handler.getPrivateStageCue(tokens.stageToken).current.chords,[]);
 assert.equal(handler.getPrivateStageCue(tokens.stageToken).current.notes,'');
 await call(handler,3,'presentation_unload');
 assert.equal(handler.getPrivateStageCue(tokens.stageToken),null);
 await call(handler,4,'presentation_load_worship',{plan});
 assert.equal((await call(handler,5,'presentation_worship_looks')).destinations.find(x=>x.destination==='stage').layers.includes('notes'),true);
});
