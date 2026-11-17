import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {renderDeckPptx} from '../src/pptx-export.mjs';
import {createMcpHandler} from '../src/mcp.mjs';

const deck={
 title:'Worship and Training',
 theme:'dark',
 slides:[
  {id:'intro',kind:'title',title:'Welcome',text:'Opening greeting'},
  {id:'verse',kind:'lyrics',title:'Original Song',text:'Our voices rise\nTogether we sing',song:'Original Song',section:'verse 1'},
  {id:'scripture',kind:'scripture',title:'John 3:16',text:'Scripture reference on screen',reference:'John 3:16'}
 ]
};
const rpc=(name,args)=>({jsonrpc:'2.0',id:1,method:'tools/call',params:{name,arguments:args}});
test('PowerPoint renderer creates a self-contained presentation with visible authored text',async()=>{
 const data=await renderDeckPptx(deck);
 assert.ok(Buffer.isBuffer(data));
 assert.equal(data.subarray(0,2).toString('ascii'),'PK');
 assert.ok(data.length>3000);
 const temp=await mkdtemp(join(tmpdir(),'ai-present-pptx-'));
 try{
  const file=join(temp,'test.pptx');
  const {writeFile}=await import('node:fs/promises');
  await writeFile(file,data);
  const list=spawnSync('unzip',['-Z1',file],{encoding:'utf8'});
  assert.equal(list.status,0,list.stderr);
  assert.match(list.stdout,/ppt\/slides\/slide1\.xml/);
  assert.match(list.stdout,/ppt\/slides\/slide3\.xml/);
  const slideTwo=spawnSync('unzip',['-p',file,'ppt/slides/slide2.xml'],{encoding:'utf8'});
  assert.equal(slideTwo.status,0,slideTwo.stderr);
  assert.match(slideTwo.stdout,/Our voices rise/);
  assert.match(slideTwo.stdout,/Together we sing/);
  assert.match(slideTwo.stdout,/Original Song/);
 }finally{await rm(temp,{recursive:true,force:true});}
});
test('PowerPoint renderer validates limits and disallows unsupported titles',async()=>{
 await assert.rejects(()=>renderDeckPptx({slides:[]}),/slide|deck/i);
 await assert.rejects(()=>renderDeckPptx({slides:[{id:'x',title:'A'.repeat(10001)}]}),/length|long|limit/i);
 await assert.rejects(()=>renderDeckPptx({slides:Array.from({length:201},(_,i)=>({id:String(i)}))}),/limit|slides/i);
});
test('MCP PowerPoint export is opt-in, keeps existing files and uses a safe name',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'ai-present-export-'));
 try{
  const handler=createMcpHandler({exportRoot:dir});
  const load=await handler(rpc('presentation_load',{deck}));
  assert.equal(load.result.isError,undefined);
  const result=await handler(rpc('presentation_export_pptx',{name:'church-demo'}));
  assert.equal(result.result.isError,undefined,JSON.stringify(result.result));
  const out=result.result.structuredContent;
  assert.equal(out.format,'pptx');
  assert.equal(out.exported,true);
  assert.equal((await readFile(out.file)).subarray(0,2).toString('ascii'),'PK');
  const repeat=await handler(rpc('presentation_export_pptx',{name:'church-demo'}));
  assert.equal(repeat.result.isError,true);
  const unsafe=await handler(rpc('presentation_export_pptx',{name:'../secrets'}));
  assert.equal(unsafe.result.isError,true);
 }finally{await rm(dir,{recursive:true,force:true});}
});

test('PowerPoint export over local HTTP requires bearer authorization and returns file metadata',async()=>{
 const {createHttpServer}=await import('../src/http.mjs');
 const folder=await mkdtemp(join(tmpdir(),'ai-present-http-pptx-'));
 const token='pptx-authorization-987654321';
 const handler=createMcpHandler({exportRoot:folder});
 const server=createHttpServer({handler,token});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const base='http://127.0.0.1:'+server.address().port;
 const post=(url,data,header=true)=>fetch(base+url,{
  method:'POST',
  headers:{
   'Content-Type':'application/json',
   ...(header?{Authorization:'Bearer '+token}:{})
  },
  body:JSON.stringify(data)
 });
 try{
  assert.equal((await post('/v1/export/pptx',{name:'test'},false)).status,401);
  const loaded=await post('/v1/load',{deck});
  assert.equal(loaded.status,200);
  const response=await post('/v1/export/pptx',{name:'service'});
  assert.equal(response.status,200);
  const data=await response.json();
  assert.equal(data.format,'pptx');
  assert.ok(Buffer.from(await readFile(data.file)).subarray(0,2).toString('ascii')==='PK');
 }finally{
  await new Promise(resolve=>server.close(resolve));
  await rm(folder,{recursive:true,force:true});
 }
});
