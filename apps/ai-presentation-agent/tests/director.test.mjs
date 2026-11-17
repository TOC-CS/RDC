import test from 'node:test';
import assert from 'node:assert/strict';
import {PresentationDirector} from '../src/director.mjs';
import {MemoryAdapter, ProPresenterAdapter, buildKeynoteScript, buildPowerPointScript} from '../src/adapters.mjs';
import {interpretVoice, VoiceChat} from '../src/voice.mjs';

const deck={title:'Service',slides:[
  {id:'welcome',kind:'title',title:'Welcome',text:'Welcome to Sunday worship'},
  {id:'v1',kind:'lyrics',title:'Song',song:'Test Hymn',section:'verse 1',text:'The morning light is shining',cues:['morning light is shining']},
  {id:'chorus',kind:'lyrics',title:'Song',song:'Test Hymn',section:'chorus',text:'We sing together with joy',cues:['we sing together with joy']},
  {id:'v2',kind:'lyrics',title:'Song',song:'Test Hymn',section:'verse 2',text:'Our voices rise together',cues:['our voices rise together']},
  {id:'scripture',kind:'scripture',title:'John 3:16',reference:'John 3:16',text:'For God so loved the world'}
]};
function setup(clock=()=>10000){const adapter=new MemoryAdapter();const director=new PresentationDirector({adapter,clock,cooldownMs:250});director.load(deck);return {adapter,director};}

test('loads deck, changes slide only on explicit commands in assisted mode',async()=>{
 const {director,adapter}=setup();
 await director.start('assisted');
 assert.equal(director.snapshot().current.id,'welcome');
 assert.equal((await director.ingest({source:'speech',type:'transcript',text:'morning light is shining',confidence:.98,final:true})).reason,'assisted_mode');
 assert.equal(director.snapshot().current.id,'welcome');
 await director.command({action:'next'});
 assert.equal(director.snapshot().current.id,'v1');
 assert.equal(adapter.events.at(-1).slide.id,'v1');
});
test('BandMates song sections follow setlist in automatic mode with repeats and duplicate suppression',async()=>{
 const {director,adapter}=setup();
 await director.start('automatic');
 assert.equal((await director.ingest({source:'bandmates',type:'song.section',song:'Test Hymn',section:'chorus',eventId:'a'})).changed,true);
 assert.equal(director.snapshot().current.id,'chorus');
 assert.equal((await director.ingest({source:'bandmates',type:'song.section',song:'Test Hymn',section:'chorus',eventId:'a'})).reason,'duplicate');
 assert.equal(adapter.events.length,2);
 const event=await director.ingest({source:'bandmates',type:'song.section',song:'Test Hymn',section:'verse 2',eventId:'b'});
 assert.equal(event.reason,'cooldown');
});
test('manual hold prevents auto advances, manual commands still work',async()=>{
 let now=10000;const {director}=setup(()=>now);
 await director.start('automatic');
 await director.command({action:'hold'});
 assert.equal((await director.ingest({source:'bandmates',type:'song.section',section:'chorus',song:'Test Hymn'})).reason,'held');
 await director.command({action:'next'});
 assert.equal(director.snapshot().current.id,'v1');
 await director.command({action:'resume'});
 now+=400;
 assert.equal((await director.ingest({source:'bandmates',type:'song.section',section:'chorus',song:'Test Hymn',eventId:'new'})).changed,true);
 assert.equal(director.snapshot().current.id,'chorus');
});
test('transcript matching requires final, confidence and substantive text',async()=>{
 let now=10000;const {director}=setup(()=>now);
 await director.start('automatic');
 for(const x of [
  {text:'we sing',confidence:.98,final:true},
  {text:'we sing together with joy',confidence:.98,final:false},
  {text:'we sing together with joy',confidence:.4,final:true}
 ]) assert.equal((await director.ingest({source:'speech',type:'transcript',...x})).changed,false);
 now+=300;
 assert.equal((await director.ingest({source:'speech',type:'transcript',text:'we sing together with joy',confidence:.95,final:true})).changed,true);
 assert.equal(director.snapshot().current.id,'chorus');
});
test('voice commands require wake phrase or push to talk, ordinary speech cannot trigger',()=>{
 assert.equal(interpretVoice('go to next slide'),null);
 assert.deepEqual(interpretVoice('presentation agent next slide'),{action:'next'});
 assert.deepEqual(interpretVoice('presentation agent hold slides'),{action:'hold'});
 assert.deepEqual(interpretVoice('next slide',{pushToTalk:true}),{action:'next'});
 assert.deepEqual(interpretVoice('presentation agent show slide 3'),{action:'goto',index:2});
 assert.deepEqual(interpretVoice('presentation agent what slide are we on'),{action:'status'});
 assert.equal(interpretVoice('presentation agent a mountain is a peaceful place'),null);
});
test('voice chat speaks a response to manual commands without altering performance input',async()=>{
 const {director}=setup();await director.start('manual');
 const spoken=[];const voice=new VoiceChat(director,{speak:async(text)=>{spoken.push(text);}});
 const ordinary=await voice.handle('next slide');
 assert.equal(ordinary.accepted,false);
 assert.equal(director.snapshot().current.id,'welcome');
 const command=await voice.handle('presentation agent next slide',{respondAloud:true});
 assert.equal(command.accepted,true);
 assert.equal(director.snapshot().current.id,'v1');
 assert.equal(spoken.length,1);
 assert.match(command.reply,/verse 1|Song/i);
});
test('external control remains disarmed until specifically enabled',async()=>{
 let writes=0;const adapter={external:true,show:async()=>{writes++;}};
 const director=new PresentationDirector({adapter,clock:()=>10000});
 director.load(deck);
 await director.start('automatic');
 assert.equal(writes,0);
 assert.equal(director.snapshot().dryRun,true);
 await director.arm(true);
 await director.command({action:'next'});
 assert.equal(writes,1);
});
test('invalid slides, unknown commands and stale events are rejected',async()=>{
 const {director}=setup();
 assert.throws(()=>director.load({slides:[{id:'x'},{id:'x'}]}),/unique|Duplicate/i);
 director.load(deck);await director.start('automatic');
 await assert.rejects(()=>director.command({action:'shutdown'}),/unsupported|unknown/i);
 assert.equal((await director.ingest({source:'speech',type:'transcript',text:'we sing together with joy',confidence:.9,final:true,timestamp:1000})).reason,'stale');
});
test('ProPresenter adapter uses verified API paths and requires explicit configuration',async()=>{
 const paths=[];const adapter=new ProPresenterAdapter({baseUrl:'http://127.0.0.1:50001',fetcher:async(url,options)=>{paths.push(new URL(url).pathname);return {ok:true,status:204};}});
 await adapter.next();
 await adapter.goto(2,{presentationId:'123e4567-e89b-12d3-a456-426614174000'});
 assert.deepEqual(paths,['/v1/presentation/active/next/trigger','/v1/presentation/123e4567-e89b-12d3-a456-426614174000/2/trigger']);
 await assert.rejects(()=>adapter.goto(1,{}),/presentation/i);
 assert.throws(()=>new ProPresenterAdapter({baseUrl:'https://example.com'}),/local|private|loopback/i);
});
test('installed macOS script adapter contracts use application-specific verbs',()=>{
 assert.match(buildKeynoteScript('next'),/show next/);
 assert.match(buildKeynoteScript('previous'),/show previous/);
 assert.match(buildPowerPointScript('next'),/go to next slide/);
 assert.match(buildPowerPointScript('goto',3),/number 4/);
});
