import test from 'node:test';
import assert from 'node:assert/strict';
import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {mkdtemp,rm,writeFile,readFile} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath} from 'node:url';
const exec=promisify(execFile);
const server=fileURLToPath(new URL('../scripts/managed-server.mjs',import.meta.url));
const cli=fileURLToPath(new URL('../scripts/presentationctl.mjs',import.meta.url));
const PRIVATE='STAGE_PRIVATE_PRAYER_DO_NOT_PUBLISH';
test('separate RDC command processes share one rights-filtered worship rundown and preserve output isolation',
 {timeout:10000},async()=>{
 const home=await mkdtemp(join(tmpdir(),'toc-worship-rundown-cli-'));
 const path=join(home,'service.json');
 const environment={...process.env,PRESENTATION_AGENT_STATE_DIR:home};
 await writeFile(path,JSON.stringify({title:'Original Worship Service',items:[
   {id:'opening',type:'announcement',title:'Welcome',text:'Welcome',notes:PRIVATE},
   {id:'reading',type:'scripture',title:'Bible Reading',
     reference:'Psalm 100:1-2',translation:'NKJV',notes:PRIVATE}
 ]}),{mode:0o600});
 const child=spawn(process.execPath,[server],{
   env:environment,stdio:['ignore','ignore','pipe']
 });
 try{
   let ready=false;
   for(let i=0;i<90;i++){
     try{await readFile(join(home,'control.json'));ready=true;break;}
     catch{await new Promise(r=>setTimeout(r,25));}
   }
   assert.equal(ready,true);
   const command=async(...args)=>{
     const {stdout}=await exec(process.execPath,[cli,...args],{
       env:environment,timeout:2200
     });
     return JSON.parse(stdout);
   };
   await assert.rejects(()=>command('rundown'),/Load a worship service/i);
   await command('worship-load','--file',path);
   const initial=await command('rundown');
   assert.equal(initial.current.id,'opening');
   assert.equal(initial.next.id,'reading');
   assert.equal(initial.nativeProjectionVerified,false);
   assert.equal(JSON.stringify(initial).includes(PRIVATE),false);
   await command('start','manual');
   await command('next');
   const after=await command('rundown');
   assert.equal(after.current.reference,'Psalm 100:1-2');
   assert.equal(after.current.id,'reading');
   assert.equal(after.next,null);
   await command('stop');
   await command('unload');
   await assert.rejects(()=>command('rundown'),/Load a worship service/i);
 }finally{
   child.kill('SIGTERM');
   await Promise.race([new Promise(r=>child.once('close',r)),
     new Promise(r=>setTimeout(r,1300))]);
   await rm(home,{recursive:true,force:true});
 }
});
