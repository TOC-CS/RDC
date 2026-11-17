import test from 'node:test';
import assert from 'node:assert/strict';
import {createHttpServer} from '../src/http.mjs';
import {createMcpHandler} from '../src/mcp.mjs';
const AUTH='presentation-control-test-token-0001';
const VIEW='presentation-view-only-test-token-0002';
const deck={title:'Worship',slides:[
  {id:'start',title:'Welcome',text:'Please stand'},
  {id:'chorus',title:'Chorus',text:'We will sing and rejoice',song:'Sample Song',section:'chorus'}]};
async function scenario(fn){
 const handler=createMcpHandler();
 const server=createHttpServer({handler,token:AUTH,viewerToken:VIEW});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const base='http://127.0.0.1:'+server.address().port;
 const control=async(path,payload)=>{
  const res=await fetch(base+path,{method:'POST',headers:{
   Authorization:'Bearer '+AUTH,'Content-Type':'application/json'},body:JSON.stringify(payload)});
  if(res.status!==200)throw new Error('Control failed '+res.status+' '+await res.text());
  return res.json();
 };
 try{await fn({base,control});}finally{await new Promise(resolve=>server.close(resolve));}
}
test('viewer refuses unauthenticated access and controls remain private',()=>scenario(async({base,control})=>{
 await control('/v1/load',{deck});
 assert.equal((await fetch(base+'/v1/viewer')).status,401);
 assert.equal((await fetch(base+'/v1/viewer?key=invalid')).status,401);
 assert.equal((await fetch(base+'/v1/view-events?key=invalid')).status,401);
 const good=await fetch(base+'/v1/viewer?key='+VIEW);
 assert.equal(good.status,200);
 const html=await good.text();
 assert.match(html,/EventSource/);
 assert.match(html,/connect-src 'self'/);
 assert.match(html,/We will sing and rejoice/);
 assert.ok(!html.includes(AUTH));
 const controlBlocked=await fetch(base+'/v1/status');
 assert.equal(controlBlocked.status,401);
}));
test('live viewer stream receives current slide and real-time updates from independent controller',()=>scenario(async({base,control})=>{
 await control('/v1/load',{deck});
 await control('/v1/start',{mode:'automatic'});
 const controller=new AbortController();
 const response=await fetch(base+'/v1/view-events?key='+VIEW,{signal:controller.signal});
 assert.equal(response.status,200);
 assert.match(response.headers.get('content-type'),/text\/event-stream/);
 const reader=response.body.getReader();
 let pending='';
 async function getEvent(){
  for(let i=0;i<8;i++){
   const {done,value}=await Promise.race([
    reader.read(),
    new Promise((_,reject)=>setTimeout(()=>reject(new Error('Stream event timed out')),2000))
   ]);
   if(done)throw new Error('Event stream closed.');
   pending+=new TextDecoder().decode(value);
   const match=pending.match(/data: (.+)\n\n/);
   if(match){pending=pending.slice(match.index+match[0].length);return JSON.parse(match[1]);}
  }
  throw new Error('No event received.');
 }
 try{
  const start=await getEvent();
  assert.equal(start.index,0);
  await control('/v1/command',{action:'next'});
  const next=await getEvent();
  assert.equal(next.index,1);
  assert.equal(next.slideId,'chorus');
 }finally{controller.abort();}
}));
