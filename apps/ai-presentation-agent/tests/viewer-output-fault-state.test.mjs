import test from 'node:test';
import assert from 'node:assert/strict';
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';

const controlToken='operator-control-test-token-2026';
const viewerToken='viewer-only-test-token-2026';
test('read-only SSE viewer receives an output fault even when the displayed deck index stays unchanged',
 {timeout:5000},async()=>{
  const adapter={
    name:'external-fault-fixture',external:true,requiresReadback:true,
    async show(){return {ok:true};},
    async next(){return {ok:true};},
    async readback({expectedIndex}){
      return {supported:true,index:0,confirmed:expectedIndex===0};
    }
  };
  const handler=createMcpHandler({adapter,allowExternalControl:true});
  const server=createHttpServer({handler,token:controlToken,viewerToken});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const base='http://127.0.0.1:'+server.address().port;
  const post=async(path,body)=>{
    const response=await fetch(base+path,{method:'POST',headers:{
      Authorization:'Bearer '+controlToken,'Content-Type':'application/json'},
      body:JSON.stringify(body),signal:AbortSignal.timeout(2000)});
    return {status:response.status,body:await response.json()};
  };
  const abort=new AbortController();
  let reader=null;
  try{
    await post('/v1/load',{deck:{title:'Fault test',slides:[{id:'one'},{id:'two'}]}});
    await post('/v1/arm',{enabled:true});
    await post('/v1/start',{mode:'automatic'});
    const response=await fetch(base+'/v1/view-events?key='+viewerToken,{signal:abort.signal});
    assert.equal(response.status,200);
    reader=response.body.getReader();
    const decoder=new TextDecoder();
    let buffered='';
    async function nextEvent(){
      for(let i=0;i<10;i++){
        const {done,value}=await Promise.race([reader.read(),
          new Promise((_,reject)=>setTimeout(()=>reject(new Error('No SSE event after output fault.')),500))]);
        if(done)throw new Error('SSE closed prematurely.');
        buffered+=decoder.decode(value);
        const match=buffered.match(/data: (.+)\n\n/);
        if(match){buffered=buffered.slice(match.index+match[0].length);return JSON.parse(match[1]);}
      }
      throw new Error('SSE event missing.');
    }
    const initial=await nextEvent();
    assert.equal(initial.index,0);
    assert.equal(initial.outputFaulted,false);
    const viewer=await fetch(base+'/v1/viewer?key='+viewerToken);
    const html=await viewer.text();
    assert.match(html,/id="session-status"/);
    const failure=await post('/v1/command',{action:'next'});
    assert.equal(failure.status,422);
    const fault=await nextEvent();
    assert.equal(fault.index,0);
    assert.equal(fault.outputFaulted,true);
    assert.equal(fault.held,true);
    assert.equal(fault.armed,false);
    assert.equal(fault.source,'external-fault-fixture');
  }finally{
    abort.abort();
    try{await reader?.cancel();}catch{}
    server.closeAllConnections();
    await new Promise(resolve=>server.close(resolve));
  }
});
