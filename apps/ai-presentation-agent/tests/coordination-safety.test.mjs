import test from 'node:test';
import assert from 'node:assert/strict';
import {PresentationDirector} from '../src/director.mjs';
import {MemoryAdapter} from '../src/adapters.mjs';
import {createMcpHandler} from '../src/mcp.mjs';

const deck={title:'Cue coordination',slides:[
  {id:'one',title:'One'},
  {id:'two',title:'Two',song:'Sample',section:'chorus'},
  {id:'three',title:'Three',song:'Sample',section:'verse 2'}
]};
const rpc=(name,args)=>({jsonrpc:'2.0',id:1,method:'tools/call',params:{name,arguments:args}});

test('untrusted presentation_command cannot bypass external-output arm permission',async()=>{
 const handler=createMcpHandler({allowExternalControl:false});
 await handler(rpc('presentation_load',{deck}));
 await handler(rpc('presentation_select_output',{kind:'keynote'}));
 const attempted=await handler(rpc('presentation_command',{action:'arm',enabled:true}));
 assert.equal(attempted.result.isError,true);
 const state=await handler(rpc('presentation_status',{}));
 assert.equal(state.result.structuredContent.armed,false);
});

test('failed native startup stays faulted until an explicit operator reload and rearm',async()=>{
 let attempts=0;
 const adapter={name:'test-external',external:true,show:async()=>{
   if(++attempts===1)throw new Error('not connected');return {ok:true};
 }};
 const director=new PresentationDirector({adapter});
 director.load(deck);
 await director.arm(true);
 await assert.rejects(director.start('automatic'),/not connected/);
 const fault=director.snapshot();
 assert.equal(fault.started,false);
 assert.equal(fault.mode,'manual');
 assert.equal(fault.outputFaulted,true);
 assert.equal(fault.armed,false);
 assert.equal(fault.held,true);
 await assert.rejects(director.start('automatic'),/fault|reload/i);
 assert.equal(attempts,1,'A possibly committed native write must not be replayed.');
 director.load(deck);
 assert.equal(director.snapshot().outputFaulted,false);
 assert.equal(director.snapshot().armed,false);
 await director.arm(true);
 await director.start('automatic');
 assert.equal(director.snapshot().started,true);
 assert.equal(attempts,2);
});

test('two simultaneous next commands are serialized, preserve both commands, and advance two slides',async()=>{
 const seen=[];
 const adapter=new MemoryAdapter();
 adapter.next=async slide=>{
   seen.push(slide.id);
   await new Promise(resolve=>setTimeout(resolve,10));
 };
 const director=new PresentationDirector({adapter,cooldownMs:0});
 director.load(deck);await director.start('manual');
 const [first,second]=await Promise.all([
   director.command({action:'next'}),
   director.command({action:'next'})
 ]);
 assert.equal(first.slide.id,'two');
 assert.equal(second.slide.id,'three');
 assert.deepEqual(seen,['two','three']);
 assert.equal(director.snapshot().current.id,'three');
});

test('two simultaneous auto cues targeting the same section result in one external advance',async()=>{
 const seen=[];
 const adapter=new MemoryAdapter();
 adapter.show=async(index,slide)=>{seen.push(slide.id);await new Promise(resolve=>setTimeout(resolve,8));};
 const director=new PresentationDirector({adapter,clock:()=>10000,cooldownMs:0});
 director.load(deck);await director.start('automatic');
 const [a,b]=await Promise.all([
   director.ingest({source:'bandmates',type:'song.section',song:'Sample',section:'chorus',eventId:'b1'}),
   director.ingest({source:'vision',type:'song.section',song:'Sample',section:'chorus',eventId:'v1'})
 ]);
 assert.equal([a.changed,b.changed].filter(Boolean).length,1);
 assert.deepEqual(seen,['one','two']);
});

test('stale operations cannot mutate a newly loaded deck mid-flight',async()=>{
 let release;
 const gate=new Promise(resolve=>{release=resolve;});
 const adapter=new MemoryAdapter();
 adapter.next=async()=>gate;
 const director=new PresentationDirector({adapter});
 director.load(deck);await director.start('manual');
 const pending=director.command({action:'next'});
 assert.throws(()=>director.load({title:'Replacement',slides:[{id:'replacement'}]}),/busy|in progress/i);
 release();await pending;
 assert.equal(director.snapshot().current.id,'two');
});

test('MCP output selection cannot replace a director whose first app write is pending',async()=>{
 let release;
 const gate=new Promise(resolve=>{release=resolve;});
 const external={name:'test',external:true,show:async()=>gate};
 const handler=createMcpHandler({adapter:external,allowExternalControl:true});
 await handler(rpc('presentation_load',{deck}));
 await handler(rpc('presentation_arm',{enabled:true}));
 const startup=handler(rpc('presentation_start',{mode:'automatic'}));
 const replacement=await handler(rpc('presentation_select_output',{kind:'memory'}));
 release();
 await startup;
 assert.equal(replacement.result.isError,true);
 const status=await handler(rpc('presentation_status',{}));
 assert.equal(status.result.structuredContent.adapter,'test');
 assert.equal(status.result.structuredContent.started,true);
});
