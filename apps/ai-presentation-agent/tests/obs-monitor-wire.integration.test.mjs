import test from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {createHash} from 'node:crypto';
import {OBSReadOnlyMonitor} from '../src/obs-monitor.mjs';
import {obsWebsocketAuth} from '../src/adapters.mjs';

const GUID='258EAFA5-E914-47DA-95CA-C5AB0DC85B11';
const password='local-obs-readonly-fixture-secret';
const salt='obs-fixture-monitor-salt',challenge='obs-fixture-monitor-challenge';
function frame(value){
 const bytes=Buffer.from(JSON.stringify(value));
 if(bytes.length>=65535)throw Error('Test payload too large.');
 const header=bytes.length<126?
   Buffer.from([0x81,bytes.length]):
   Buffer.from([0x81,126,(bytes.length>>8)&255,bytes.length&255]);
 return Buffer.concat([header,bytes]);
}
function fixture({withAuth=true,disagree=false}={}){
 const server=createServer((req,res)=>{res.writeHead(404);res.end();});
 const requests=[],sockets=new Set();
 server.on('upgrade',(req,socket,head)=>{
   sockets.add(socket);
   socket.on('close',()=>sockets.delete(socket));
   const key=req.headers['sec-websocket-key'];
   assert.ok(key);
   const accept=createHash('sha1').update(key+GUID).digest('base64');
   socket.write('HTTP/1.1 101 Switching Protocols\r\n'+
     'Upgrade: websocket\r\nConnection: Upgrade\r\n'+
     'Sec-WebSocket-Accept: '+accept+'\r\n\r\n');
   const send=value=>socket.write(frame(value));
   send({op:0,d:{obsWebSocketVersion:'5.2.0',rpcVersion:1,
     ...(withAuth?{authentication:{salt,challenge}}:{})}});
   let pending=Buffer.alloc(0);
   function receive(message){
     if(message.op===1){
       if(withAuth)assert.equal(message.d.authentication,
         obsWebsocketAuth(password,salt,challenge));
       send({op:2,d:{negotiatedRpcVersion:1}});
       return;
     }
     if(message.op!==6)return;
     const type=message.d.requestType;
     requests.push(type);
     const responses={
       GetSceneList:{
         scenes:[{sceneName:'Wide Camera'},{sceneName:'Pastor Camera'}],
         currentProgramSceneName:disagree?'Unexpected Scene':'Wide Camera',
         currentPreviewSceneName:'Pastor Camera'
       },
       GetCurrentProgramScene:{sceneName:'Wide Camera'},
       GetStreamStatus:{outputActive:false,outputReconnecting:false},
       GetRecordStatus:{outputActive:true,outputPaused:false}
     };
     assert.ok(Object.hasOwn(responses,type),'No writes may reach OBS monitor fixture.');
     send({op:7,d:{requestType:type,requestId:message.d.requestId,
       requestStatus:{result:true,code:100},responseData:responses[type]}});
   }
   const parse=()=>{
     while(pending.length>=2){
       const opcode=pending[0]&15;
       const masked=(pending[1]&128)!==0;
       let len=pending[1]&127,position=2;
       if(len===126){
         if(pending.length<4)return;
         len=pending.readUInt16BE(2);position=4;
       }
       if(len===127||len>65535||!masked)return socket.destroy();
       if(pending.length<position+4+len)return;
       const mask=pending.subarray(position,position+4);
       const content=Buffer.from(pending.subarray(position+4,position+4+len));
       for(let i=0;i<len;i++)content[i]^=mask[i%4];
       pending=pending.subarray(position+4+len);
       if(opcode===8){socket.end(Buffer.from([0x88,0]));return;}
       if(opcode===1)receive(JSON.parse(content.toString('utf8')));
     }
   };
   socket.on('data',chunk=>{pending=Buffer.concat([pending,chunk]);parse();});
   if(head?.length){pending=Buffer.concat([pending,head]);parse();}
 });
 return {
   async start(){await new Promise(r=>server.listen(0,'127.0.0.1',r));return 'ws://127.0.0.1:'+server.address().port+'/';},
   async stop(){for(const s of sockets)s.destroy();await new Promise(r=>server.close(r));},
   requests
 };
}
test('actual local OBS WebSocket 5 framing authenticates and performs only four read-only queries',
 {timeout:5000},async()=>{
 const obs=fixture();
 const url=await obs.start();
 try{
   const data=await new OBSReadOnlyMonitor({url,password,timeoutMs:2200}).inspect();
   assert.equal(data.connected,true);
   assert.deepEqual(obs.requests,[
     'GetSceneList','GetCurrentProgramScene','GetStreamStatus','GetRecordStatus'
   ]);
   assert.equal(data.programScene,'Wide Camera');
   assert.equal(data.previewScene,'Pastor Camera');
   assert.equal(data.programReadbackMatchesSceneList,true);
   assert.equal(data.streamingActive,false);
   assert.equal(data.recordingActive,true);
   assert.equal(data.outputWritesPerformed,false);
 }finally{await obs.stop();}
});
test('OBS Program readback inconsistency is reported without switching scenes',
 {timeout:5000},async()=>{
 const obs=fixture({withAuth:false,disagree:true});
 const url=await obs.start();
 try{
   const data=await new OBSReadOnlyMonitor({url,password:'',timeoutMs:2200}).inspect();
   assert.equal(data.programReadbackMatchesSceneList,false);
   assert.equal(obs.requests.length,4);
   assert.equal(data.streamOrRecordingChanged,false);
 }finally{await obs.stop();}
});
