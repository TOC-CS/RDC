import test from 'node:test';
import assert from 'node:assert/strict';
import {createMcpHandler} from '../src/mcp.mjs';
import {WorshipStageClock} from '../src/worship-timing.mjs';
import {validateWorshipLook} from '../src/worship-looks.mjs';

const token='private-stage-look-timer-2026';
const SECRET='PRIVATE_STAGE_TIMER_FOR_SERMON';
const plan={title:'Worship',items:[
 {id:'title',type:'announcement',title:'Welcome',text:'Welcome to worship'}
]};
const rpc=async(h,id,name,args={})=>{
 const r=await h({jsonrpc:'2.0',id,method:'tools/call',params:{name,arguments:args}});
 if(r.result?.isError)throw Error(r.result.content[0].text);
 return r.result.structuredContent;
};
test('private stage default Look includes timer while audience and broadcast Looks cannot expose timer',async()=>{
 assert.ok(validateWorshipLook('stage').layers.includes('timer'));
 for(const destination of ['audience','broadcast'])
   assert.throws(()=>validateWorshipLook(destination,{
     layout:destination==='audience'?'fullscreen':'lower-third',layers:['timer']
   }),/layer|not allowed/i);
});
test('optional private stage Look can hide timer without resetting actual owner stage-clock state',async()=>{
 let ms=10000;
 const clock=new WorshipStageClock({clock:()=>ms});
 const handler=createMcpHandler({stageGrant:token,
   allowWorshipLookChanges:true,allowStageClockControl:true,stageClock:clock});
 await rpc(handler,1,'presentation_load_worship',{plan});
 handler.updatePrivateStageClock(token,{
   action:'configure',label:SECRET,durationMs:100000
 });
 handler.updatePrivateStageClock(token,{action:'start'});
 ms+=5000;
 assert.equal(handler.getPrivateStageCue(token).clock.label,SECRET);
 const firstClock=handler.getPrivateStageClock(token);
 assert.equal(firstClock.remainingMs,95000);
 await rpc(handler,2,'presentation_worship_look_set',{
   destination:'stage',
   look:{layout:'confidence',layers:['title','text','next']}
 });
 assert.equal(handler.getPrivateStageCue(token).clock,null);
 assert.equal(handler.getPrivateStageClock(token).remainingMs,95000);
 assert.equal(JSON.stringify(handler.getBroadcastCue()).includes(SECRET),false);
 assert.equal(JSON.stringify(await rpc(handler,3,'presentation_status')).includes(SECRET),false);
 await rpc(handler,4,'presentation_worship_look_set',{
   destination:'stage',
   look:{layout:'confidence',layers:['title','text','timer']}
 });
 assert.equal(handler.getPrivateStageCue(token).clock.label,SECRET);
 assert.equal(handler.getPrivateStageCue(token).clock.remainingMs,95000);
});
