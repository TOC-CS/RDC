const BASE='https://www.googleapis.com/youtube/v3/liveChat/messages';
function validateChatId(value){
 if(typeof value!=='string'||value.length<1||value.length>256||
    !/^[A-Za-z0-9_-]+$/.test(value))
   throw new Error('Authorized YouTube live chat ID required.');
 return value;
}
/**
 * Official YouTube LiveChatMessages list / insert adapter.
 * OAuth is supplied at action time by the authorized AI host or connected app.
 * The agent never stores OAuth tokens or writes them into query parameters.
 * "Reply" means a new message referring to a viewer's comment, since the
 * liveChatMessages insert endpoint has no threaded replyTo parameter.
 */
export class YouTubeLiveChatConnector{
 constructor({
   liveChatId,actorChannelId=null,getAccessToken,
   fetcher=fetch,clock=()=>Date.now(),timeoutMs=5000
 }={}){
   this.liveChatId=validateChatId(liveChatId);
   if(actorChannelId!==null&&(typeof actorChannelId!=='string'||actorChannelId.length>256))
     throw new Error('Invalid YouTube channel identity.');
   this.actorChannelId=actorChannelId;
   if(typeof getAccessToken!=='function')
     throw new Error('YouTube OAuth access-token provider required.');
   if(typeof fetcher!=='function'||typeof clock!=='function')
     throw new Error('YouTube HTTP and clock functions required.');
   if(!Number.isInteger(timeoutMs)||timeoutMs<500||timeoutMs>30000)
     throw new Error('Invalid YouTube API timeout.');
   this.getAccessToken=getAccessToken;
   this.fetcher=fetcher;
   this.clock=clock;
   this.timeoutMs=timeoutMs;
   this.nextPageToken=null;
   this.nextPollAt=-Infinity;
   this.provider='youtube';
 }
 assertStream({provider,streamId}={}){
   if(provider!=='youtube'||streamId!==this.liveChatId)
     throw new Error('YouTube comment provider/stream identity mismatch.');
 }
 async api(method,url,body=null){
   const token=await this.getAccessToken({
     provider:'youtube',streamId:this.liveChatId,action:method==='GET'?'read':'post'
   });
   if(typeof token!=='string'||token.length<15||token.length>4096||
      /[\s\u0000-\u001F]/.test(token))
     throw new Error('A valid authorized YouTube OAuth token is required.');
   const options={
     method,
     headers:{
       Authorization:'Bearer '+token,
       Accept:'application/json',
       ...(body?{'Content-Type':'application/json'}:{})
     },
     redirect:'error',
     signal:AbortSignal.timeout(this.timeoutMs)
   };
   if(body)options.body=JSON.stringify(body);
   const response=await this.fetcher(url,options);
   if(!response?.ok)
     throw new Error('YouTube Live Chat API returned HTTP '+String(response?.status??'unknown')+'. Verify account permissions and stream status.');
   const payload=await response.json();
   if(!payload||typeof payload!=='object'||Array.isArray(payload))
     throw new Error('YouTube Live Chat API returned invalid JSON.');
   return payload;
 }
 async read({provider='youtube',streamId=this.liveChatId,limit=200}={}){
   this.assertStream({provider,streamId});
   if(!Number.isInteger(limit)||limit<1||limit>200)
     throw new Error('YouTube comment read limit must be 1 to 200.');
   const now=this.clock();
   if(now<this.nextPollAt)
     return {items:[],provider,streamId,nextPollAfterMs:this.nextPollAt-now};
   const url=new URL(BASE);
   url.searchParams.set('liveChatId',this.liveChatId);
   url.searchParams.set('part','snippet,authorDetails');
   url.searchParams.set('maxResults','200'); // Minimum supported by API.
   if(this.nextPageToken)url.searchParams.set('pageToken',this.nextPageToken);
   const result=await this.api('GET',url);
   if(!Array.isArray(result.items))
     throw new Error('YouTube live chat response missing message list.');
   const items=result.items.slice(0,200).map(item=>{
     const author=item?.authorDetails??{};
     const snippet=item?.snippet??{};
     if(typeof item?.id!=='string'||item.id.length>128)
       throw new Error('YouTube response contains an invalid message ID.');
     const message=snippet.displayMessage??snippet.textMessageDetails?.messageText??'';
     return {
       id:item.id,provider:'youtube',streamId:this.liveChatId,
       authorId:typeof author.channelId==='string'?author.channelId:null,
       authorName:typeof author.displayName==='string'?author.displayName:null,
       text:String(message).slice(0,4000),
       createdAt:Number.isFinite(Date.parse(snippet.publishedAt))?Date.parse(snippet.publishedAt):now,
       isOwnMessage:this.actorChannelId!==null&&this.actorChannelId===author.channelId
     };
   });
   if(result.nextPageToken!==undefined&&typeof result.nextPageToken!=='string')
     throw new Error('YouTube returned an invalid pagination token.');
   this.nextPageToken=result.nextPageToken??this.nextPageToken;
   const delay=Number.isFinite(result.pollingIntervalMillis)
     ?Math.min(120000,Math.max(1000,Math.floor(result.pollingIntervalMillis)))
     :3000;
   this.nextPollAt=now+delay;
   return {items,provider:'youtube',streamId:this.liveChatId,nextPollAfterMs:delay};
 }
 async post({provider,streamId,text,replyToId,requestId}={}){
   this.assertStream({provider,streamId});
   if(typeof replyToId!=='string'||replyToId.length<1||replyToId.length>128)
     throw new Error('YouTube response requires an observed comment ID.');
   if(typeof requestId!=='string'||requestId.length<1||requestId.length>128)
     throw new Error('YouTube response requires an exact operation ID.');
   if(typeof text!=='string'||!text.trim()||text.length>500)
     throw new Error('Invalid YouTube chat message.');
   const url=new URL(BASE);
   url.searchParams.set('part','snippet');
   const result=await this.api('POST',url,{
     snippet:{
       liveChatId:this.liveChatId,
       type:'textMessageEvent',
       textMessageDetails:{messageText:text.trim()}
     }
   });
   if(typeof result.id!=='string'||!result.id)
     throw new Error('YouTube chat post response has no confirmable message ID.');
   return {status:'sent',messageId:result.id,
     provider:'youtube',streamId:this.liveChatId,threaded:false,requestId};
 }
}
