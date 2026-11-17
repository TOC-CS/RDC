#!/usr/bin/env node
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';
const token=process.env.PRESENTATION_API_TOKEN;
if(!token||Buffer.byteLength(token)<16){
 process.stderr.write('Configure PRESENTATION_API_TOKEN (16+ bytes) before starting local API.\n');
 process.exitCode=2;
}else{
 const handler=createMcpHandler({allowExternalControl:process.env.PRESENTATION_ALLOW_EXTERNAL_CONTROL==='1'});
 const server=createHttpServer({handler,token,
   viewerToken:process.env.PRESENTATION_VIEW_TOKEN??null});
 const port=Number(process.env.PRESENTATION_API_PORT??8789);
 if(!Number.isInteger(port)||port<1024||port>65535)throw new Error('Invalid local API port.');
 server.listen(port,'127.0.0.1',()=>{
   process.stderr.write('Local presentation API ready on 127.0.0.1 port '+port+'; bearer authentication required.\n');
 });
}
