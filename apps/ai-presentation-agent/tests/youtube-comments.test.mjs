import test from 'node:test';
import assert from 'node:assert/strict';
import {YouTubeLiveChatConnector} from '../integrations/youtube-live-chat.mjs';

const chatId='liveChat1234';
function response(json,status=200){
 return {ok:status>=200&&status<300,status,json:async()=>json};
}
test('YouTube connector reads live chat using OAuth header and normalizes author/message fields',async()=>{
 const calls=[];
 let now=1000;
 const connector=new YouTubeLiveChatConnector({
   liveChatId:chatId,
   actorChannelId:'my-channel',
   getAccessToken:async()=> 'private-test-token',
   clock:()=>now,
   fetcher:async(url,request)=>{
     calls.push({url:String(url),request});
     return response({
       items:[
        {id:'msg1',snippet:{displayMessage:'Hello everyone',publishedAt:'2026-11-16T20:01:00Z'},
          authorDetails:{channelId:'viewer1',displayName:'Friend'}},
        {id:'msg2',snippet:{displayMessage:'Welcome',publishedAt:'2026-11-16T20:01:01Z'},
          authorDetails:{channelId:'my-channel',displayName:'My Channel'}}
       ],
       nextPageToken:'page-2',
       pollingIntervalMillis:5000
     });
   }
 });
 const page=await connector.read({provider:'youtube',streamId:chatId,limit:200});
 assert.equal(page.items.length,2);
 assert.equal(page.items[0].text,'Hello everyone');
 assert.equal(page.items[0].isOwnMessage,false);
 assert.equal(page.items[1].isOwnMessage,true);
 assert.equal(page.nextPollAfterMs,5000);
 assert.equal(calls.length,1);
 assert.equal(new URL(calls[0].url).hostname,'www.googleapis.com');
 assert.equal(new URL(calls[0].url).searchParams.get('liveChatId'),chatId);
 assert.equal(calls[0].request.headers.Authorization,'Bearer private-test-token');
 assert.ok(!calls[0].url.includes('private-test-token'));
 const tooSoon=await connector.read({provider:'youtube',streamId:chatId,limit:200});
 assert.equal(tooSoon.items.length,0);
 assert.equal(calls.length,1);
 now=6100;
 await connector.read({provider:'youtube',streamId:chatId,limit:200});
 assert.equal(calls.length,2);
 assert.equal(new URL(calls[1].url).searchParams.get('pageToken'),'page-2');
});
test('YouTube connector posts a new chat message through official insert API without leaking OAuth',async()=>{
 const calls=[];
 const connector=new YouTubeLiveChatConnector({
  liveChatId:chatId,getAccessToken:async()=> 'secret-test-oauth',
  fetcher:async(url,options)=>{
    calls.push({url:String(url),options});
    return response({id:'posted-123'});
  }
 });
 const result=await connector.post({provider:'youtube',streamId:chatId,replyToId:'msg1',text:'Thanks for your question',requestId:'idempotency-1'});
 assert.equal(result.status,'sent');
 assert.equal(result.messageId,'posted-123');
 assert.equal(calls[0].options.method,'POST');
 assert.equal(calls[0].options.headers.Authorization,'Bearer secret-test-oauth');
 const body=JSON.parse(calls[0].options.body);
 assert.equal(body.snippet.liveChatId,chatId);
 assert.equal(body.snippet.type,'textMessageEvent');
 assert.equal(body.snippet.textMessageDetails.messageText,'Thanks for your question');
 assert.ok(!calls[0].url.includes('secret-test-oauth'));
 assert.ok(!calls[0].options.body.includes('secret-test-oauth'));
});
test('YouTube connector binds reads/writes to the exact chat and refuses missing authorization',async()=>{
 const connector=new YouTubeLiveChatConnector({
   liveChatId:chatId,getAccessToken:async()=>null,
   fetcher:async()=>{throw new Error('Should not call network');}
 });
 await assert.rejects(()=>connector.read({provider:'youtube',streamId:chatId}),/OAuth|token|authorization/i);
 await assert.rejects(()=>connector.post({provider:'youtube',streamId:'some-other-stream',text:'hi'}),/stream|identity/i);
});
test('YouTube connector exposes provider failures without echoing tokens',async()=>{
 const connector=new YouTubeLiveChatConnector({
  liveChatId:chatId,getAccessToken:async()=> 'very-secret-oauth',
  fetcher:async()=>response({error:{message:'private info'}},403)
 });
 await assert.rejects(()=>connector.read({provider:'youtube',streamId:chatId}),error=>{
   assert.match(error.message,/HTTP 403/);
   assert.ok(!error.message.includes('very-secret-oauth'));
   return true;
 });
});
