import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {ProPresenterAdapter} from '../src/adapters.mjs';
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';

const uuid='123e4567-e89b-12d3-a456-426614174000';
const deck={title:'Live Worship Rehearsal',slides:[
  {id:'welcome',title:'Welcome',presentationId:uuid},
  {id:'verse',title:'Song',song:'Original Song',section:'verse 1',text:'We gather here to sing',presentationId:uuid},
  {id:'chorus',title:'Song',song:'Original Song',section:'chorus',text:'Lift our voices up together',presentationId:uuid},
  {id:'reading',title:'Scripture',reference:'John 3:16',presentationId:uuid}
]};
async function listen(server){await new Promise(r=>server.listen(0,'127.0.0.1',r));return 'http://127.0.0.1:'+server.address().port;}
async function close(server){server.closeAllConnections();await new Promise(r=>server.close(r));}
test('live-band cue, host AI voice command, external adapter and venue readback form one coherent session',async()=>{
 let actual=0;const writes=[];
 const venue=http.createServer((req,res)=>{
   const uri=new URL(req.url,'http://localhost').pathname;
   const send=(status,body=null)=>{
     res.statusCode=status;
     if(body){res.setHeader('Content-Type','application/json');res.end(JSON.stringify(body));}
     else res.end();
   };
   if(uri==='/v1/presentation/slide_index'){
     return send(200,{presentation:{index:actual,presentation_id:{uuid}},announcements:null});
   }
   if(uri==='/v1/presentation/active/next/trigger'){
     actual=Math.min(actual+1,deck.slides.length-1);writes.push({method:'next',actual});
     return send(204);
   }
   const specific=uri.match(/^\/v1\/presentation\/([a-z0-9-]+)\/(\d+)\/trigger$/);
   if(specific&&specific[1]===uuid){
     actual=Number(specific[2]);writes.push({method:'goto',actual});return send(204);
   }
   return send(404);
 });
 const venueUrl=await listen(venue);
 const adapter=new ProPresenterAdapter({baseUrl:venueUrl,presentationId:uuid});
 const handler=createMcpHandler({adapter,allowExternalControl:true});
 const api=createHttpServer({handler,token:'venue-rehearsal-test-strong-token'});
 const base=await listen(api);
 const post=async(path,payload)=>{
   const r=await fetch(base+path,{method:'POST',
     headers:{'Authorization':'Bearer venue-rehearsal-test-strong-token','Content-Type':'application/json'},
     body:JSON.stringify(payload),signal:AbortSignal.timeout(2000)});
   if(r.status!==200)throw new Error(path+': HTTP '+r.status+', '+await r.text());
   return r.json();
 };
 const get=async(path)=>{
   const r=await fetch(base+path,{headers:{Authorization:'Bearer venue-rehearsal-test-strong-token'},signal:AbortSignal.timeout(2000)});
   assert.equal(r.status,200);return r.json();
 };
 try{
   await post('/v1/load',{deck});
   await post('/v1/arm',{enabled:true});
   const start=await post('/v1/start',{mode:'automatic'});
   assert.equal(start.current.id,'welcome');
   assert.equal(actual,0);
   const band=await post('/v1/cue',{source:'bandmates',type:'song.section',
     song:'Original Song',section:'verse 1',eventId:'section1'});
   assert.equal(band.changed,true);
   assert.equal(actual,1);
   const firstRead=await get('/v1/readback');
   assert.equal(firstRead.index,1);
   assert.equal(firstRead.confirmed,true);
   const voice=await post('/v1/voice',{transcript:'presentation agent next slide',confidence:.99,final:true});
   assert.equal(voice.commandAccepted,true);
   assert.equal(voice.speakByHost,true);
   assert.equal(actual,2);
   const secondRead=await get('/v1/readback');
   assert.equal(secondRead.confirmed,true);
   assert.equal(secondRead.expectedSlideId,'chorus');
   const held=await post('/v1/command',{action:'hold'});
   assert.equal(held.reason,'held');
   const automatic=await post('/v1/cue',{source:'bandmates',type:'song.section',
     song:'Original Song',section:'verse 1',eventId:'section2'});
   assert.equal(automatic.reason,'held');
   assert.equal(actual,2);
   assert.equal(writes.length,3);
 }finally{
   await close(api);await close(venue);
 }
});
