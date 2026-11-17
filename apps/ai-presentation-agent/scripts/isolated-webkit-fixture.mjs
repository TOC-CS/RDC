#!/usr/bin/env node
// Isolated ephemeral localhost presentation fixture for cross-engine tests.
// This process never reads the owner's private managed presentation session.
import {createMcpHandler} from '../src/mcp.mjs';
import {createHttpServer} from '../src/http.mjs';
const handler=createMcpHandler();
const send=async(name,args={})=>{
 const result=await handler({jsonrpc:'2.0',id:1,method:'tools/call',
   params:{name,arguments:args}});
 if(result?.result?.isError)throw new Error(result.result.content[0].text);
 return result.result.structuredContent;
};
await send('presentation_load',{deck:{title:'WebKit Live Test',
 slides:[{id:'one',title:'WebKit Opening',text:'Private offline test slide'},
         {id:'two',title:'WebKit Updated',text:'Confirmed independent renderer update'}]}});
await send('presentation_start',{mode:'automatic'});
const server=createHttpServer({handler,
 token:'webkit-browser-private-control-fixture',
 viewerToken:'webkit-browser-viewer-fixture'});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
process.stdout.write(JSON.stringify({port:server.address().port})+'\n');
let closing=false;
function close(){
 if(closing)return;closing=true;
 server.closeAllConnections();
 server.close(()=>process.exit(0));
}
process.on('SIGTERM',close);
process.on('SIGINT',close);
