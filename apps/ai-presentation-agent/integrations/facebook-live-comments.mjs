const API_VERSION='v27.0';
const API_BASE='https://graph.facebook.com';
function validVideoId(value){
 if(typeof value!=='string'||!/^[0-9]{1,64}$/.test(value))
   throw new Error('A valid authorized Facebook Live video ID is required.');
 return value;
}
/**
 * Facebook Live video comments, official Graph API read adapter.
 *
 * Current Graph API live-video /comments reference documents GET but no
 * create operation on this edge. This connector deliberately exposes no
 * posting method until a separate verified, authorized API path is available.
 */
export class FacebookLiveCommentsConnector{
 constructor({
   liveVideoId,actorPageId=null,getAccessToken,fetcher=fetch,
   clock=()=>Date.now(),timeoutMs=5000
 }={}){
   this.liveVideoId=validVideoId(liveVideoId);
   if(actorPageId!==null&&(typeof actorPageId!=='string'||actorPageId.length>128))
     throw new Error('Invalid Facebook Page identity.');
   if(typeof getAccessToken!=='function')
     throw new Error('A Facebook Page OAuth token provider is required.');
   if(typeof fetcher!=='function'||typeof clock!=='function')
     throw new Error('Facebook HTTP and clock functions are required.');
   if(!Number.isInteger(timeoutMs)||timeoutMs<500||timeoutMs>30000)
     throw new Error('Invalid Facebook request timeout.');
   this.actorPageId=actorPageId;
   this.getAccessToken=getAccessToken;
   this.fetcher=fetcher;
   this.clock=clock;
   this.timeoutMs=timeoutMs;
   this.provider='facebook';
 }
 async read({provider='facebook',streamId=this.liveVideoId,limit=100}={}){
   if(provider!=='facebook'||streamId!==this.liveVideoId)
     throw new Error('Facebook live video comment stream identity mismatch.');
   if(!Number.isInteger(limit)||limit<1||limit>100)
     throw new Error('Facebook comment read limit must be 1 to 100.');
   const token=await this.getAccessToken({
     provider:'facebook',streamId:this.liveVideoId,action:'read'
   });
   if(typeof token!=='string'||token.length<15||token.length>4096||
      /[\s\u0000-\u001F]/.test(token))
     throw new Error('An authorized Facebook Page OAuth token is required.');
   const url=new URL('/'+API_VERSION+'/'+this.liveVideoId+'/comments',API_BASE);
   url.searchParams.set('order','reverse_chronological');
   url.searchParams.set('filter','stream');
   url.searchParams.set('live_filter','filter_low_quality');
   url.searchParams.set('limit',String(limit));
   url.searchParams.set('fields','id,message,from,created_time');
   const response=await this.fetcher(url,{
     method:'GET',
     headers:{Authorization:'Bearer '+token,Accept:'application/json'},
     redirect:'error',
     signal:AbortSignal.timeout(this.timeoutMs)
   });
   if(!response?.ok)
     throw new Error('Facebook Live Graph API returned HTTP '+String(response?.status??'unknown')+'. Verify permissions.');
   const result=await response.json();
   if(!Array.isArray(result?.data)||result.data.length>limit)
     throw new Error('Facebook live comment response is malformed or unbounded.');
   const now=this.clock();
   const items=result.data.map(comment=>{
     if(typeof comment?.id!=='string'||comment.id.length>128)
       throw new Error('Facebook live comment has an invalid ID.');
     const author=comment.from??{};
     return {
       id:comment.id,provider:'facebook',streamId:this.liveVideoId,
       authorId:typeof author.id==='string'?author.id:null,
       authorName:typeof author.name==='string'?author.name:null,
       text:typeof comment.message==='string'?comment.message.slice(0,4000):'',
       createdAt:Number.isFinite(Date.parse(comment.created_time))?Date.parse(comment.created_time):now,
       isOwnMessage:this.actorPageId!==null&&author.id===this.actorPageId
     };
   }).filter(v=>v.text.trim()!=='');
   return {provider:'facebook',streamId:this.liveVideoId,items};
 }
}
