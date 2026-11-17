import test from 'node:test';
import assert from 'node:assert/strict';
import {VerifiedBandMatesSectionRelay} from '../integrations/bandmates-verified-relay.mjs';
import {PresentationDirector} from '../src/director.mjs';
import {MemoryAdapter} from '../src/adapters.mjs';

const current={schema:'bandmates.performance-section/v1',
 sessionId:'native-001',eventId:'section-a',song:'Original Song',
 section:'chorus',occurrence:1,stateKind:'performed',
 performanceConfirmed:true,confidence:.99,timestamp:10000};
test('a current verified BandMates event advances an independent presentation once',async()=>{
 const director=new PresentationDirector({adapter:new MemoryAdapter(),clock:()=>10000,cooldownMs:0});
 director.load({slides:[{id:'intro'},{id:'chorus1',song:'Original Song',section:'chorus',occurrence:1}]});
 await director.start('automatic');
 let sent=0;
 const relay=new VerifiedBandMatesSectionRelay({sessionId:'native-001',clock:()=>10000,
   send:async event=>{sent++;return director.ingest(event)}});
 const first=await relay.accept(current);
 assert.equal(first.changed,true);
 assert.equal(director.snapshot().current.id,'chorus1');
 const duplicate=await relay.accept(current);
 assert.equal(duplicate.changed,false);
 assert.equal(duplicate.reason,'duplicate_verified_section');
 assert.equal(sent,1);
});
test('planned native section, weak prediction, and unconfirmed vocal position can never advance a slide',async()=>{
 const out=[];
 const relay=new VerifiedBandMatesSectionRelay({sessionId:'native-001',clock:()=>10000,
   send:async cue=>{out.push(cue);return {changed:true}}});
 const candidates=[
   {...current,stateKind:'planned'},
   {...current,confidence:.6},
   {...current,performanceConfirmed:false},
   {...current,timestamp:100},
   {...current,timestamp:undefined}
 ];
 const responses=await Promise.all(candidates.map(e=>relay.accept(e)));
 assert.ok(responses.every(x=>x.changed===false));
 assert.equal(out.length,0);
});
test('cross-session spoofed events are rejected before any external call',async()=>{
 let sent=0;
 const relay=new VerifiedBandMatesSectionRelay({sessionId:'native-001',clock:()=>10000,
   send:async()=>{sent++;return {changed:true}}});
 await assert.rejects(()=>relay.accept({...current,sessionId:'other-session'}),/another session/i);
 await assert.rejects(()=>relay.accept({...current,eventId:'../hello'}),/stable ID/i);
 assert.equal(sent,0);
});
test('same event identity with different song title or occurrence fails closed',async()=>{
 const relay=new VerifiedBandMatesSectionRelay({sessionId:'native-001',clock:()=>10000,
   send:async()=>({changed:true})});
 await relay.accept(current);
 await assert.rejects(()=>relay.accept({...current,occurrence:2}),/identity conflict/i);
});
test('possible external write with lost response stays pinned to the original event ID',async()=>{
 let sends=0;
 const relay=new VerifiedBandMatesSectionRelay({sessionId:'native-001',clock:()=>10000,
   send:async()=>{sends++;throw Error('connection lost after potential remote write');}});
 await assert.rejects(()=>relay.accept(current),/connection lost/);
 await assert.rejects(()=>relay.accept(current),/connection lost/);
 assert.equal(sends,1);
});
