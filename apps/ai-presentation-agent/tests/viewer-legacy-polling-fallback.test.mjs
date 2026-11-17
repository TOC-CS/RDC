import test from 'node:test';
import assert from 'node:assert/strict';
import {createHttpServer} from '../src/http.mjs';
import {createMcpHandler} from '../src/mcp.mjs';

test('legacy MCP-only handler with no subscriber still updates the authenticated SSE viewer',
 {timeout:5000},async()=>{
 const underlying=createMcpHandler();
 // A legacy tool host exports an MCP request handler and no subscribe hook.
 const legacy=async request=>underlying(request);
 assert.equal(typeof legacy.subscribe,'undefined');
 const secret='legacy-control-token-for-test';
 const viewer='legacy-viewer-token-for-test';
 const server=createHttpServer({handler:legacy,token:secret,viewerToken:viewer});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const base='http://127.0.0.1:'+server.address().port;
 const control=async(path,payload)=>{
   const res=await fetch(base+path,{method:'POST',
     headers:{Authorization:'Bearer '+secret,'Content-Type':'application/json'},
     body:JSON.stringify(payload),signal:AbortSignal.timeout(2000)});
   if(res.status!==200)throw new Error('Legacy control rejected request '+res.status);
   return res.json();
 };
 const abort=new AbortController();
 let reader=null,buffer='';
 const decoder=new TextDecoder();
 const readEvent=async()=>{
   for(let tries=0;tries<12;tries++){
     const {value,done}=await Promise.race([reader.read(),new Promise((_,reject)=>
       setTimeout(()=>reject(new Error('Legacy SSE update timed out.')),500))]);
     if(done)throw new Error('Legacy SSE stream closed.');
     buffer+=decoder.decode(value);
     const match=buffer.match(/data: (.+)\n\n/);
     if(match){buffer=buffer.slice(match.index+match[0].length);return JSON.parse(match[1]);}
   }
   throw new Error('Legacy SSE emitted no data event.');
 };
 try{
   await control('/v1/load',{deck:{slides:[{id:'first'},{id:'second'}]}});
   await control('/v1/start',{mode:'manual'});
   const response=await fetch(base+'/v1/view-events?key='+viewer,{signal:abort.signal});
   assert.equal(response.status,200);
   reader=response.body.getReader();
   assert.equal((await readEvent()).slideId,'first');
   await control('/v1/command',{action:'next'});
   assert.equal((await readEvent()).slideId,'second');
 }finally{
   abort.abort();
   try{await reader?.cancel();}catch{}
   server.closeAllConnections();
   await new Promise(resolve=>server.close(resolve));
 }
});
