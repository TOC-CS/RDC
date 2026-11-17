import test from 'node:test';
import assert from 'node:assert/strict';
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';
import {createWorshipLibrary} from '../src/worship-library.mjs';

const PRIVATE='PRIVATE_STAGE_SPEAKER_NOTES_KEEP_OFF_STREAM';
const NOTICE='ROOM_ONLY_ANNOUNCEMENT_NEVER_STREAM';
const SCRIPTURE='OWNER_LICENSED_SCRIPTURE_FIXTURE_ROOM_ONLY';
const SONG='An original chorus line for testing';
const GRANT='owner-only-private-stage-grant';

function bundle(){
 const catalog={schema:'toc.worship-library/v1',
  songs:[{
   id:'original-song',revision:'r1',title:'Original Service Song',
   rights:{source:'original',displayAuthorized:true,streamAuthorized:true},
   notes:PRIVATE,sections:[{id:'ch',label:'chorus',
    lines:[SONG],notes:PRIVATE,chords:['C','G']}],
   arrangements:[{id:'service',sectionIds:['ch','ch']}]
  }],
  scriptures:[{
   id:'licensed-reading',revision:'r1',title:'Reference Reading',
   reference:'Psalm 100:1',translation:'NKJV',text:SCRIPTURE,
   scriptureRights:{source:'licensed',licenseId:'TEST_LOCAL_ONLY_GRANT',
    displayAuthorized:true,streamAuthorized:false},notes:PRIVATE
  }],
  segments:[{
   id:'room-message',revision:'r1',type:'announcement',
   title:'Room Announcement',text:NOTICE,
   publicAuthorized:true,streamAuthorized:false,notes:PRIVATE
  }]
 };
 const entries=createWorshipLibrary(catalog).listEntries();
 const byId=new Map(entries.map(item=>[item.id,item]));
 const ref=(id,sourceId,sourceType,arrangementId)=>({
   id,sourceId,sourceType,revision:byId.get(sourceId).revision,
   sha256:byId.get(sourceId).sha256,
   ...(arrangementId?{arrangementId}:{})
 });
 const plan={title:'Original Worship Service',theme:'dark',items:[
  ref('opening','original-song','song','service'),
  ref('opening-s1-p2','room-message','segment'),
  ref('scripture-slot','licensed-reading','scripture')
 ]};
 return {catalog,plan};
}
const rpc=(id,name,args={})=>({jsonrpc:'2.0',id,method:'tools/call',
 params:{name,arguments:args}});
async function attempt(h,id,name,args={}){
 const reply=await h(rpc(id,name,args));
 if(reply.error)throw new Error(reply.error.message);
 return reply.result;
}
async function call(h,id,name,args={}){
 const response=await attempt(h,id,name,args);
 if(response.isError)throw new Error(response.content[0].text);
 return response.structuredContent;
}

test('managed worship library loads one validated cue state with repeated song sections and isolated rights',async()=>{
 const h=createMcpHandler({stageGrant:GRANT});
 const loaded=await call(h,1,'presentation_load_worship_library',bundle());
 assert.equal(loaded.started,false);
 assert.equal(loaded.armed,false);
 assert.deepEqual(loaded.slides.map(s=>s.id),[
  'opening-s1-p1','opening-s2-p1','opening-s1-p2','scripture-slot'
 ]);
 assert.deepEqual(loaded.slides.slice(0,2).map(s=>s.occurrence),[1,2]);
 assert.equal(loaded.worship.stageAvailable,true);
 assert.equal(loaded.worship.rundown.length,3);
 assert.equal(JSON.stringify(loaded).includes(PRIVATE),false);
 assert.equal(h.getPrivateStageCue('incorrect'),null);
 const currentStage=h.getPrivateStageCue(GRANT);
 assert.equal(currentStage.current.notes,PRIVATE);
 assert.equal(currentStage.current.chords[0],'C');
 assert.equal(h.getBroadcastCue().current.text,SONG);
 await call(h,2,'presentation_start',{mode:'manual'});
 await call(h,3,'presentation_command',{action:'next'});
 assert.equal((await call(h,4,'presentation_worship_rundown')).current.occurrence,2);
 await call(h,5,'presentation_command',{action:'next'});
 assert.equal(h.getPrivateStageCue(GRANT).current.notes,PRIVATE);
 assert.equal(h.getBroadcastCue().current.text,'');
 assert.equal(h.getWorshipLook('broadcast').current.text,'');
 assert.equal(h.getWorshipLook('stage','incorrect'),null);
 const rundown=await call(h,6,'presentation_worship_rundown');
 for(const text of [PRIVATE,NOTICE,SCRIPTURE,SONG,GRANT])
  assert.equal(JSON.stringify(rundown).includes(text),false);
 await call(h,7,'presentation_command',{action:'next'});
 assert.equal(h.getBroadcastCue().current.text,'');
 assert.equal(h.getPrivateStageCue(GRANT).current.text,SCRIPTURE);
 assert.equal((await call(h,8,'presentation_status')).armed,false);
});

test('stale source references and attempted overrides reject before changing a previously loaded service',async()=>{
 const h=createMcpHandler({stageGrant:GRANT});
 await call(h,1,'presentation_load_worship_library',bundle());
 const status=await call(h,2,'presentation_status');
 const before=h.getPrivateStageCue(GRANT);
 const stale=bundle();
 stale.plan.items[0].sha256='f'.repeat(64);
 assert.match((await attempt(h,3,'presentation_load_worship_library',stale)).content[0].text,/sha|checksum|integrity/i);
 assert.deepEqual(await call(h,4,'presentation_status'),status);
 const injected=bundle();
 injected.plan.items[0].notes='PRIVATE_INJECTED_FROM_SERVICE_PLAN';
 assert.match((await attempt(h,5,'presentation_load_worship_library',injected)).content[0].text,/override|unexpected/i);
 assert.deepEqual(await call(h,6,'presentation_status'),status);
 assert.deepEqual(h.getPrivateStageCue(GRANT),before);
 assert.equal(h.getBroadcastCue().current.text,SONG);
});

test('library path does not create a stage grant or silently arm external output',async()=>{
 const h=createMcpHandler();
 const state=await call(h,1,'presentation_load_worship_library',bundle());
 assert.equal(state.armed,false);
 assert.equal(state.worship.stageAvailable,false);
 assert.equal(h.getPrivateStageCue(GRANT),null);
 assert.match((await attempt(h,2,'presentation_arm',{enabled:true})).content[0].text,/operator/i);
 assert.equal((await call(h,3,'presentation_status')).armed,false);
});

test('operator-only HTTP loads catalog and preserves independently authenticated public and private Looks',async()=>{
 const operator='operator-secret-for-local-test-2026';
 const viewer='viewer-secret-for-local-test-2026';
 const broadcast='broadcast-secret-for-local-test-2026';
 const h=createMcpHandler({stageGrant:GRANT});
 const server=createHttpServer({handler:h,token:operator,viewerToken:viewer,
  stageToken:GRANT,streamToken:broadcast});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const base='http://127.0.0.1:'+server.address().port;
 const endpoint=base+'/v1/worship/library/load';
 const send=(body,credential=operator)=>fetch(endpoint,{
  method:'POST',headers:{'Content-Type':'application/json',
    ...(credential?{'Authorization':'Bearer '+credential}:{})},
  body:JSON.stringify(body)
 });
 try{
  assert.equal((await send(bundle(),null)).status,401);
  assert.equal((await send(bundle(),viewer)).status,401);
  assert.equal((await send(bundle(),GRANT)).status,401);
  assert.equal((await send(bundle(),broadcast)).status,401);
  const loaded=await send(bundle());
  assert.equal(loaded.status,200);
  const status=await loaded.json();
  assert.equal(status.slides.length,4);
  assert.equal(status.armed,false);
  for(const hidden of [PRIVATE,GRANT])
   assert.equal(JSON.stringify(status).includes(hidden),false);
  const audience=await fetch(base+'/v1/look/audience?key='+viewer);
  const stage=await fetch(base+'/v1/look/stage?key='+encodeURIComponent(GRANT));
  const stream=await fetch(base+'/v1/look/broadcast?key='+broadcast);
  assert.equal(audience.status,200);
  assert.equal(stage.status,200);
  assert.equal(stream.status,200);
  assert.equal((await audience.json()).layers.text,SONG);
  assert.equal((await stage.json()).layers.notes,PRIVATE);
  assert.equal((await stream.json()).layers.text,SONG);
  await call(h,7,'presentation_start',{mode:'manual'});
  await call(h,8,'presentation_command',{action:'next'});
  await call(h,9,'presentation_command',{action:'next'});
  const denied=await fetch(base+'/v1/look/broadcast?key='+broadcast);
  assert.equal(denied.status,200);
  assert.equal((await denied.json()).layers.text,'');
  assert.equal((await fetch(base+'/v1/look/stage?key='+encodeURIComponent(GRANT))).status,200);
  const unchanged=await call(h,10,'presentation_status');
  const rejected=bundle();
  rejected.plan.items[0].sha256='0'.repeat(64);
  assert.equal((await send(rejected)).status,422);
  assert.deepEqual(await call(h,11,'presentation_status'),unchanged);
  assert.equal((await fetch(base+'/v1/look/broadcast?key='+viewer)).status,401);
 }finally{
  server.closeAllConnections();
  await new Promise(resolve=>server.close(resolve));
 }
});
