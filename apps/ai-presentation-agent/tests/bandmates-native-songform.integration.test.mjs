import test from 'node:test';
import assert from 'node:assert/strict';
import {BandMatesPresentationBridge} from '../integrations/bandmates.mjs';
import {PresentationDirector} from '../src/director.mjs';
import {MemoryAdapter} from '../src/adapters.mjs';

let NativeSongDynamics=null;
try{({SongDynamics:NativeSongDynamics}=await import('../../BandMates/src/song-dynamics.js'));}
catch(error){if(error.code!=='ERR_MODULE_NOT_FOUND')throw error;}

test('real BandMates planned snapshots hold slides until independently confirmed performance observations arrive',
 async t=>{
  if(!NativeSongDynamics)return t.skip('Separate BandMates project not installed.');
  const native=new NativeSongDynamics({songForm:{
    schema:'rdc-musician.song-form.v1',meter:{numerator:4,denominator:4},
    sections:[
      {section:'intro',bars:1},{section:'verse',bars:1},
      {section:'chorus',bars:1},{section:'verse-2',bars:1},
      {section:'chorus',bars:1}
    ]
  }});
  let clock=10000;
  const director=new PresentationDirector({adapter:new MemoryAdapter(),clock:()=>clock,cooldownMs:0});
  director.load({slides:[
    {id:'intro',song:'Original Worship',section:'intro'},
    {id:'verse1',song:'Original Worship',section:'Verse 1'},
    {id:'chorus1',song:'Original Worship',section:'chorus',occurrence:1},
    {id:'verse2',song:'Original Worship',section:'Verse 2'},
    {id:'chorus2',song:'Original Worship',section:'chorus',occurrence:2}
  ]});
  await director.start('automatic');
  const bridge=new BandMatesPresentationBridge({
    song:'Original Worship',ingest:event=>director.ingest(event),clock:()=>clock
  });
  for(const [beat,expected] of [[0,'intro'],[4,'verse1'],
       [8,'chorus1'],[12,'verse2'],[16,'chorus2']]){
    native.forBeat(beat,{id:'worship',intensity:.6,swing:0});
    const source=native.snapshot();
    assert.equal(source.stateKind,'planned');
    const unverified=await bridge.observe({sessionId:'bandmates-real-song-form',
      songDynamics:source});
    assert.equal(unverified.reason,'planned_section_requires_live_confirmation');
    const before=director.snapshot().current?.id;
    const receipt=await bridge.observe({sessionId:'bandmates-real-song-form',
      songDynamics:{...source,stateKind:'performed',performanceConfirmed:true,
        confidence:.99,eventId:'observed-'+beat,timestamp:clock}});
    assert.equal(receipt.changed,before!==expected,
      'The independently confirmed current song section may advance only on change.');
    assert.equal(director.snapshot().current?.id,expected,
      'BandMates verified section '+source.section+' at beat '+beat+
      ' must identify the right presentation slide, receipt='+JSON.stringify(receipt));
    clock+=500;
  }
});
