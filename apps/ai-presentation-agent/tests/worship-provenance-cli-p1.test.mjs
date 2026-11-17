import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,readFile,rm} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath} from 'node:url';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {createWorshipLibrary} from '../src/worship-library.mjs';

const exec=promisify(execFile);
const compiler=fileURLToPath(new URL('../scripts/compile-worship-service.mjs',import.meta.url));
const ROOM_ONLY='ROOM_ONLY_MUST_NOT_STREAM';
test('P1 exact ownership also masks denied song-shaped announcement in owner-only offline broadcast export',
 {timeout:6000},async()=>{
  const root=await mkdtemp(join(tmpdir(),'toc-p1-broadcast-rights-'));
  const libraryFile=join(root,'library.json'),planFile=join(root,'service.json');
  const output=join(root,'owner-only-output');
  const librarySource={
    schema:'toc.worship-library/v1',
    songs:[{
      id:'worship-song',revision:'r1',title:'Original Song',
      rights:{source:'original',displayAuthorized:true,streamAuthorized:true},
      sections:[{id:'verse',label:'verse',lines:['Original permitted lyric']}],
      arrangements:[{id:'main',sectionIds:['verse']}]
    }],
    scriptures:[],
    segments:[{
      id:'room-announcement',revision:'r1',type:'announcement',
      title:'Room-only',text:ROOM_ONLY,
      publicAuthorized:true,streamAuthorized:false
    }]
  };
  const inventory=createWorshipLibrary(librarySource).listEntries();
  const ref=(id,slot,sourceType,extra={})=>{
    const asset=inventory.find(x=>x.id===id);
    return {id:slot,sourceType,sourceId:id,
      revision:asset.revision,sha256:asset.sha256,...extra};
  };
  const plan={title:'P1 Offline Broadcast Proof',items:[
    ref('worship-song','opening','song',{arrangementId:'main'}),
    ref('room-announcement','opening-s1-p2','segment')
  ]};
  try{
    await writeFile(libraryFile,JSON.stringify(librarySource),{mode:0o600});
    await writeFile(planFile,JSON.stringify(plan),{mode:0o600});
    const {stdout}=await exec(process.execPath,[
      compiler,'--library',libraryFile,'--plan',planFile,'--output-dir',output
    ],{timeout:4000});
    const receipt=JSON.parse(stdout);
    assert.equal(receipt.compiled,true);
    assert.equal(receipt.hardwareActivated,false);
    assert.equal(receipt.livestreamStarted,false);
    const audience=JSON.parse(await readFile(join(output,'audience.json'),'utf8'));
    const broadcast=JSON.parse(await readFile(join(output,'broadcast.json'),'utf8'));
    assert.equal(audience.slides.find(x=>x.id==='opening-s1-p2').text,ROOM_ONLY);
    assert.equal(broadcast.slides.find(x=>x.id==='opening-s1-p2').text,'');
    assert.equal(broadcast.slides.find(x=>x.id==='opening-s1-p1').text,'Original permitted lyric');
    assert.ok(!JSON.stringify(broadcast).includes(ROOM_ONLY));
  }finally{
    await rm(root,{recursive:true,force:true});
  }
});
