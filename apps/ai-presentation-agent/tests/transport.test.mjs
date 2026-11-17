import test from 'node:test';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {createInterface} from 'node:readline';
import {createServer} from 'node:net';
import {fileURLToPath} from 'node:url';
const executable=fileURLToPath(new URL('../scripts/mcp.mjs',import.meta.url));
async function unusedPort(){
 const server=createServer();
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const port=server.address().port;
 await new Promise(resolve=>server.close(resolve));
 return port;
}
test('real MCP stdio and authenticated HTTP clients share one live presentation session',async()=>{
 const port=await unusedPort();
 const token='presentation-transport-test-secret-9876';
 const child=spawn(process.execPath,[executable],{stdio:['pipe','pipe','pipe'],
   env:{PATH:process.env.PATH,PRESENTATION_API_TOKEN:token,PRESENTATION_API_PORT:String(port)}});
 const lines=createInterface({input:child.stdout})[Symbol.asyncIterator]();
 let err='';
 child.stderr.on('data',b=>{if(err.length<2048)err+=String(b);});
 let id=0;
 async function rpc(method,params={}){
   child.stdin.write(JSON.stringify({jsonrpc:'2.0',id:++id,method,params})+'\n');
   const line=await Promise.race([
     lines.next(),new Promise((_,reject)=>setTimeout(()=>reject(new Error('MCP response timeout.')),2500))
   ]);
   assert.equal(line.done,false,err);
   const output=JSON.parse(line.value);
   assert.equal(output.id,id,err);
   return output.result;
 }
 async function post(path,value){
   const response=await fetch('http://127.0.0.1:'+port+path,{
     method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},
     body:JSON.stringify(value),signal:AbortSignal.timeout(2000)});
   if(response.status!==200)throw new Error('HTTP '+response.status+': '+await response.text());return response.json();
 }
 try{
   assert.equal((await rpc('initialize',{protocolVersion:'2025-06-18',capabilities:{},clientInfo:{name:'integration-test',version:'1'}})).serverInfo.name,'ai-presentation-agent');
   await rpc('tools/call',{name:'presentation_load',arguments:{deck:{title:'Live',slides:[{id:'first',title:'First'},{id:'second',title:'Second'}]}}});
   const started=await post('/v1/start',{mode:'automatic'});
   assert.equal(started.current.id,'first');
   const next=await post('/v1/command',{action:'next'});
   assert.equal(next.slide.id,'second');
   const status=await rpc('tools/call',{name:'presentation_status',arguments:{}});
   assert.equal(status.structuredContent.current.id,'second');
 }finally{
   child.stdin.end();
   await new Promise(resolve=>{
     if(child.exitCode!==null)return resolve();
     const limit=setTimeout(()=>{child.kill('SIGTERM');resolve();},2000);
     child.once('close',()=>{clearTimeout(limit);resolve();});
   });
 }
});
