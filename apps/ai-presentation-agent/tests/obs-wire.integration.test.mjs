import test from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {createHash} from 'node:crypto';
import {OBSAdapter,obsWebsocketAuth} from '../src/adapters.mjs';

const GUID='258EAFA5-E914-47DA-95CA-C5AB0DC85B11';
const password='isolated-obs-fixture-secret';
const salt='fixture-salt-123',challenge='fixture-challenge-123';

function frame(value){
 const payload=Buffer.from(JSON.stringify(value),'utf8');
 let header;
 if(payload.length<126)header=Buffer.from([0x81,payload.length]);
 else{header=Buffer.alloc(4);header[0]=0x81;header[1]=126;header.writeUInt16BE(payload.length,2);}
 return Buffer.concat([header,payload]);
}
function fixture({observedScene=null,auth=true}={}){
 const server=createServer((req,res)=>{res.writeHead(404);res.end();});
 const sockets=new Set(),requests=[],helloAuth=auth?{salt,challenge}:null;
 let outputScene='Initial',identity=null;
 server.on('upgrade',(req,socket,head)=>{
   sockets.add(socket);socket.on('close',()=>sockets.delete(socket));
   const clientKey=req.headers['sec-websocket-key'];
   if(!clientKey)return socket.destroy();
   const accept=createHash('sha1').update(clientKey+GUID).digest('base64');
   socket.write('HTTP/1.1 101 Switching Protocols\r\n'+
     'Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: '+accept+'\r\n\r\n');
   const send=object=>socket.write(frame(object));
   send({op:0,d:{obsWebSocketVersion:'5.0.0',rpcVersion:1,
     ...(helloAuth?{authentication:helloAuth}:{})}});
   let bytes=Buffer.alloc(0);
   const handle=msg=>{
     if(msg.op===1){
       identity=msg.d?.authentication??null;
       if(auth&&identity!==obsWebsocketAuth(password,salt,challenge))
         return socket.destroy(new Error('Mock OBS authentication failed'));
       return send({op:2,d:{negotiatedRpcVersion:1}});
     }
     if(msg.op!==6)return;
     requests.push(msg.d?.requestType);
     if(msg.d?.requestType==='SetCurrentProgramScene'){
       outputScene=msg.d?.requestData?.sceneName;
       return send({op:7,d:{requestType:'SetCurrentProgramScene',
         requestId:msg.d.requestId,
         requestStatus:{result:true,code:100}}});
     }
     if(msg.d?.requestType==='GetCurrentProgramScene'){
       return send({op:7,d:{requestType:'GetCurrentProgramScene',
         requestId:msg.d.requestId,
         requestStatus:{result:true,code:100},
         responseData:{currentProgramSceneName:observedScene??outputScene}}});
     }
   };
   const processFrame=()=>{
     while(bytes.length>=2){
       const opcode=bytes[0]&15,masked=(bytes[1]&128)!==0;
       let len=bytes[1]&127,offset=2;
       if(len===126){if(bytes.length<4)return;len=bytes.readUInt16BE(2);offset=4;}
       if(len===127||!masked)return socket.destroy();
       if(bytes.length<offset+4+len)return;
       const mask=bytes.subarray(offset,offset+4);
       const data=Buffer.from(bytes.subarray(offset+4,offset+4+len));
       for(let i=0;i<data.length;i++)data[i]^=mask[i%4];
       bytes=bytes.subarray(offset+4+len);
       if(opcode===8){socket.end(Buffer.from([0x88,0]));return;}
       if(opcode===1)handle(JSON.parse(data.toString('utf8')));
     }
   };
   socket.on('data',chunk=>{bytes=Buffer.concat([bytes,chunk]);processFrame();});
   if(head?.length){bytes=Buffer.concat([bytes,head]);processFrame();}
 });
 return {
   async begin(){
     await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
     return 'ws://127.0.0.1:'+server.address().port+'/';
   },
   async stop(){
     for(const socket of sockets)socket.destroy();
     await new Promise(resolve=>server.close(resolve));
   },
   get requests(){return requests.slice();},
   get identity(){return identity;}
 };
}

test('real loopback OBS WebSocket 5 handshake authenticates and independently verifies a scene write',
 {timeout:5000},async()=>{
 const obs=fixture({auth:true});
 const url=await obs.begin();
 try{
   const adapter=new OBSAdapter({url,password,timeoutMs:3000});
   const result=await adapter.show(0,{scene:'Original Worship Scene'});
   assert.deepEqual(result,{ok:true,scene:'Original Worship Scene',confirmed:true});
   assert.deepEqual(obs.requests,['SetCurrentProgramScene','GetCurrentProgramScene']);
   assert.equal(obs.identity,obsWebsocketAuth(password,salt,challenge));
 }finally{await obs.stop();}
});
test('real WebSocket write acknowledgement followed by wrong scene readback is rejected without retries',
 {timeout:5000},async()=>{
 const obs=fixture({observedScene:'Other Scene',auth:false});
 const url=await obs.begin();
 try{
   const adapter=new OBSAdapter({url,password:'',timeoutMs:3000});
   await assert.rejects(()=>adapter.show(0,{scene:'Original Worship Scene'}),/readback.*mismatch/i);
   assert.deepEqual(obs.requests,['SetCurrentProgramScene','GetCurrentProgramScene']);
 }finally{await obs.stop();}
});
