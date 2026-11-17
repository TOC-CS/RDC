#!/usr/bin/env node
// Independent stdio MCP server. Optional loopback HTTP shares the SAME
// in-memory PresentationDirector when the operator supplies an API token.
import {createInterface} from 'node:readline';
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';
const handler=createMcpHandler({allowExternalControl:process.env.PRESENTATION_ALLOW_EXTERNAL_CONTROL==='1'});
let server=null;
if(process.env.PRESENTATION_API_TOKEN){
 const port=Number(process.env.PRESENTATION_API_PORT??8789);
 if(!Number.isInteger(port)||port<1024||port>65535)throw new Error('Invalid loopback API port.');
 server=createHttpServer({handler,token:process.env.PRESENTATION_API_TOKEN,
   viewerToken:process.env.PRESENTATION_VIEW_TOKEN??null});
 server.listen(port,'127.0.0.1',()=>{
   process.stderr.write('Presentation MCP and local API share one session on port '+port+'.\n');
 });
}
const reader=createInterface({input:process.stdin,crlfDelay:Infinity});
let pending=Promise.resolve();
for await(const line of reader){
 if(!line.trim())continue;
 pending=pending.then(async()=>{
   let request;
   try{request=JSON.parse(line);}
   catch{process.stdout.write(JSON.stringify({jsonrpc:'2.0',id:null,error:{code:-32700,message:'Parse error'}})+'\n');return;}
   const response=await handler(request);
   if(response)process.stdout.write(JSON.stringify(response)+'\n');
 }).catch(error=>process.stderr.write('Presentation agent error: '+String(error.message??error)+'\n'));
}
await pending;
if(server)await new Promise(resolve=>server.close(resolve));
