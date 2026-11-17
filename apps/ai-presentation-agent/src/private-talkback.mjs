import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';

const exec=promisify(execFile);
export function parseMacSpeechOutputs(raw){
 if(typeof raw!=='string'||raw.length>10000)
   throw new Error('Invalid macOS speech-output device listing.');
 const items=[];
 for(const line of raw.split(/\r?\n/)){
   const found=line.match(/^\s*(\d{1,6})\s+(.{1,180}?)\s*$/);
   if(!found)continue;
   const id=Number(found[1]);
   if(!Number.isSafeInteger(id)||id<1||id>65535)continue;
   items.push({id,name:found[2]});
 }
 return items;
}
export async function listMacSpeechOutputs({run=exec,platform=process.platform}={}){
 if(platform!=='darwin')throw new Error('Private macOS audio routing requires macOS.');
 const {stdout}=await run('/usr/bin/say',['-a','?'],{
   encoding:'utf8',timeout:2500,maxBuffer:12000
 });
 return parseMacSpeechOutputs(String(stdout));
}
export function verifyPrivateSpeechOutput({
 deviceId,confirmed=false,availableOutputs=[]
}={}){
 if(!Number.isSafeInteger(deviceId)||deviceId<1||deviceId>65535)
   throw new Error('An explicit numeric macOS speech output device ID is required.');
 if(confirmed!==true)
   throw new Error('Operator must confirm the selected output routes ONLY to a private monitor.');
 if(!Array.isArray(availableOutputs)||!availableOutputs.some(item=>item.id===deviceId))
   throw new Error('Selected speech output device is unavailable; list outputs again.');
 return {deviceId};
}
export async function speakMacPrivate(text,{
 deviceId,confirmed=false,availableOutputs=null,executor=spawn,
 platform=process.platform,timeoutMs=12000
}={}){
 if(platform!=='darwin')throw new Error('Private macOS audio routing requires macOS.');
 const value=String(text??'');
 if(!value.trim()||value.length>400||
   /[\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(value))
   throw new Error('Private spoken response must be 1 to 400 printable characters.');
 const devices=availableOutputs??await listMacSpeechOutputs();
 verifyPrivateSpeechOutput({deviceId,confirmed,availableOutputs:devices});
 return new Promise((resolve,reject)=>{
   let child,done=false;
   try{child=executor('/usr/bin/say',['-a',String(deviceId),'--',value],
     {stdio:'ignore'});}
   catch(error){reject(error);return;}
   const finish=(error)=>{
     if(done)return;
     done=true;clearTimeout(timer);
     return error?reject(error):resolve({spoken:true,deviceId});
   };
   const timer=setTimeout(()=>{
     try{child.kill?.('SIGTERM');}catch{}
     finish(new Error('Private speech output timed out.'));
   },timeoutMs);
   child.once('error',finish);
   child.once('close',code=>finish(code===0?null:new Error('Private speech output failed.')));
 });
}
