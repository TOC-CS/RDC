import test from 'node:test';
import assert from 'node:assert/strict';
import {FacebookLiveCommentsConnector} from '../integrations/facebook-live-comments.mjs';

const liveVideoId='112233445566';
test('Facebook Live comments can be read with Page OAuth and reverse chronological order',async()=>{
 const calls=[];
 const provider=new FacebookLiveCommentsConnector({
   liveVideoId,actorPageId:'owner-page-01',
   getAccessToken:async()=> 'page-access-token-12345',
   fetcher:async(url,options)=>{
     calls.push({url:String(url),options});
     return {ok:true,status:200,json:async()=>({
       data:[
         {id:'c1',message:'Hello from the audience',from:{id:'person-01',name:'Visitor'},created_time:'2026-11-16T20:00:00+0000'},
         {id:'c2',message:'Welcome',from:{id:'owner-page-01',name:'My Page'},created_time:'2026-11-16T20:00:02+0000'}
       ]
     })};
   }
 });
 const data=await provider.read({provider:'facebook',streamId:liveVideoId,limit:100});
 assert.equal(data.items.length,2);
 assert.equal(data.items[0].text,'Hello from the audience');
 assert.equal(data.items[1].isOwnMessage,true);
 assert.equal(calls.length,1);
 const uri=new URL(calls[0].url);
 assert.equal(uri.hostname,'graph.facebook.com');
 assert.match(uri.pathname,/^\/v27\.0\/112233445566\/comments$/);
 assert.equal(uri.searchParams.get('order'),'reverse_chronological');
 assert.equal(calls[0].options.headers.Authorization,'Bearer page-access-token-12345');
 assert.ok(!calls[0].url.includes('page-access-token-12345'));
 assert.equal(typeof provider.post,'undefined');
});
test('Facebook live read adapter refuses unrelated stream and missing page grants',async()=>{
 const provider=new FacebookLiveCommentsConnector({
   liveVideoId,getAccessToken:async()=>null,
   fetcher:async()=>{throw new Error('Network must not be called');}
 });
 await assert.rejects(()=>provider.read({provider:'facebook',streamId:'999999'}),/stream|identity/i);
 await assert.rejects(()=>provider.read({provider:'facebook',streamId:liveVideoId}),/token|authorization|OAuth/i);
});
test('Facebook live comment read failures do not expose Page tokens',async()=>{
 const provider=new FacebookLiveCommentsConnector({
  liveVideoId,getAccessToken:async()=> 'private-page-token-12345',
  fetcher:async()=>({ok:false,status:403})
 });
 await assert.rejects(()=>provider.read({provider:'facebook',streamId:liveVideoId}),error=>{
   assert.match(error.message,/403/);
   assert.ok(!error.message.includes('private-page-token-12345'));
   return true;
 });
});
