import test from 'node:test';
import assert from 'node:assert/strict';
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';

const token='operator-rundown-control-secret-2026',PRIVATE='PRIVATE_SERMON_STAGE_NOTES_DO_NOT_PUBLISH';
const source={title:'Church Service',items:[
 {id:'intro',type:'announcement',title:'Welcome',text:'Welcome',notes:PRIVATE},
 {id:'reading',type:'scripture',title:'Bible Reading',reference:'Psalm 100:1-2',translation:'NKJV',notes:PRIVATE},
 {id:'song',type:'song',title:'Original Hymn',
   rights:{source:'original',displayAuthorized:true,streamAuthorized:false},
   sections:[{label:'chorus',lines:['A protected original chorus'],notes:PRIVATE}],
   order:['chorus','chorus']}
]};
const rpc=(id,name,args={})=>({jsonrpc:'2.0',id,method:'tools/call',params:{name,arguments:args}});
const call=async(h,id,name,args={})=>{
 const result=await h(rpc(id,name,args));
 if(result.result?.isError)throw new Error(result.result.content[0].text);
 return result.result.structuredContent;
};
test('operator-only MCP rundown follows current slide and repeated song sections without private data',async()=>{
 const h=createMcpHandler({stageGrant:'stage-grant-not-in-rundown'});
 await call(h,1,'presentation_load_worship',{plan:source});
 const first=await call(h,2,'presentation_worship_rundown');
 assert.equal(first.current.id,'intro');
 assert.equal(first.next.id,'reading');
 assert.equal(first.items.length,3);
 assert.equal(first.privateStageDataIncluded,false);
 await call(h,3,'presentation_start',{mode:'manual'});
 await call(h,4,'presentation_command',{action:'next'});
 const next=await call(h,5,'presentation_worship_rundown');
 assert.equal(next.current.id,'reading');
 assert.equal(next.current.reference,'Psalm 100:1-2');
 assert.equal(JSON.stringify(next).includes(PRIVATE),false);
 assert.equal(JSON.stringify(next).includes('A protected original chorus'),false);
 assert.equal(JSON.stringify(next).includes('stage-grant'),false);
});
test('authenticated read-only HTTP rundown refuses all viewer credentials and has no stage data',async()=>{
 const h=createMcpHandler({stageGrant:'protected-stage-grant',allowWorshipLookChanges:true});
 const server=createHttpServer({handler:h,token,viewerToken:'public-viewer-token-for-test',
  stageToken:'protected-stage-grant',streamToken:'stream-only-token-for-test'});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const base='http://127.0.0.1:'+server.address().port;
 try{
   await call(h,1,'presentation_load_worship',{plan:source});
   assert.equal((await fetch(base+'/v1/worship/rundown')).status,401);
   assert.equal((await fetch(base+'/v1/worship/rundown?key=public-viewer-token-for-test')).status,401);
   const response=await fetch(base+'/v1/worship/rundown',{
     headers:{Authorization:'Bearer '+token}});
   assert.equal(response.status,200);
   const data=await response.json();
   assert.equal(data.current.id,'intro');
   for(const privateValue of [PRIVATE,'protected-stage-grant','A protected original chorus']){
     assert.equal(JSON.stringify(data).includes(privateValue),false);
   }
   await call(h,2,'presentation_unload');
   assert.equal((await fetch(base+'/v1/worship/rundown',{
     headers:{Authorization:'Bearer '+token}})).status,422);
 }finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});
test('operator rundown reflects output Look and curtain selection but never mutates those sources',async()=>{
 const h=createMcpHandler({stageGrant:'private-stage-token',allowWorshipLookChanges:true});
 await call(h,1,'presentation_load_worship',{plan:source});
 await call(h,2,'presentation_worship_look_set',{
   destination:'audience',look:{layout:'minimal',layers:['text']}
 });
 await call(h,3,'presentation_worship_visibility_set',{destination:'broadcast',mode:'clear'});
 const before=await call(h,4,'presentation_status');
 const rundown=await call(h,5,'presentation_worship_rundown');
 assert.equal(rundown.looks.find(x=>x.destination==='audience').layout,'minimal');
 assert.equal(rundown.visibility.find(x=>x.destination==='broadcast').mode,'clear');
 assert.equal(JSON.stringify(rundown).includes('PRIVATE'),false);
 assert.deepEqual(await call(h,6,'presentation_status'),before);
});
