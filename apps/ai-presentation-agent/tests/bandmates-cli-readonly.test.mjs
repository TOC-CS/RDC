import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {createServer} from 'node:http';
const cli=fileURLToPath(new URL('../scripts/presentationctl.mjs',import.meta.url));

test('BandMates status CLI provides a safe read-only command without any credentials',()=>{
 const result=spawnSync(process.execPath,[cli,'--help'],
   {encoding:'utf8',timeout:3000});
 assert.equal(result.status,0,result.stderr);
 assert.match(result.stdout,/bandmates-status/);
});

test('BandMates status CLI never requires a running Presentation Agent server',async()=>{
 // Use an isolated test companion that implements only GET read endpoints.
 const api=createServer((req,res)=>{
   assert.equal(req.method,'GET');
   const map={
     '/api/band/status':{running:false,generation:1,activity:'stopped'},
     '/api/live/status':{running:false,status:'idle',hardwareOutputVerified:false},
     '/api/state':{protocol:'bandmates.control.v1',bandTitle:'Test Band',channels:[]}
   };
   const output=map[req.url];
   res.writeHead(output?200:404,{'Content-Type':'application/json'});
   res.end(JSON.stringify(output??{error:'unknown'}));
 });
 await new Promise(resolve=>api.listen(0,'127.0.0.1',resolve));
 const target='http://127.0.0.1:'+api.address().port;
 try{
   const {execFile}=await import('node:child_process');
   const {promisify}=await import('node:util');
   const exec=promisify(execFile);
   const {stdout}=await exec(process.execPath,[cli,'bandmates-status'],{
     env:{...process.env,BANDMATES_LOCAL_STATUS_URL:target,
       PRESENTATION_AGENT_STATE_DIR:'/tmp/no-presentation-session-fixture'},
     timeout:4000
   });
   const result=JSON.parse(stdout);
   assert.equal(result.liveCompanionReachable,true);
   assert.equal(result.nativeSectionSignalAvailable,false);
   assert.equal(result.presentationCueSent,false);
 }finally{api.closeAllConnections();await new Promise(resolve=>api.close(resolve));}
});
