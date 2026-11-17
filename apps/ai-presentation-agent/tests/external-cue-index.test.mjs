import test from 'node:test';
import assert from 'node:assert/strict';
import {PresentationDirector} from '../src/director.mjs';
import {ProPresenterAdapter} from '../src/adapters.mjs';

const deck={title:'Imported Cue Mapping',slides:[
 {id:'welcome',title:'Welcome',targetIndex:7,presentationId:'abc-def'},
 {id:'lyrics',title:'Lyrics',targetIndex:13,presentationId:'abc-def'},
 {id:'reading',title:'Reading',targetIndex:2,presentationId:'abc-def'}
]};
test('external targetIndex is independent of local deck position',async()=>{
 let observed=7;
 const calls=[];
 const adapter={name:'indexed-external',external:true,requiresReadback:true,
   async show(deckIndex,slide){
     calls.push({op:'show',deckIndex,outputIndex:slide.targetIndex});
     observed=slide.targetIndex;return {ok:true};
   },
   async readback({expectedIndex}){
     calls.push({op:'readback',expectedIndex});
     return {supported:true,index:observed,confirmed:expectedIndex===observed};
   }
 };
 const director=new PresentationDirector({adapter});
 director.load(deck);
 await director.arm(true);
 await director.start('automatic');
 await director.command({action:'goto',index:1});
 assert.equal(director.snapshot().current.id,'lyrics');
 assert.deepEqual(calls.filter(c=>c.op==='readback').map(c=>c.expectedIndex),[7,13]);
 const result=await director.readback();
 assert.equal(result.confirmed,true);
 assert.equal(result.index,13);
 assert.equal(result.expectedDeckIndex,1);
 assert.equal(result.expectedIndex,13);
});
test('ProPresenter imported cue uses its target index rather than setlist ordering',async()=>{
 let actualIndex=7;
 const requests=[];
 const a=new ProPresenterAdapter({
   baseUrl:'http://127.0.0.1:50001',presentationId:'abc-def',
   fetcher:async url=>{
     const path=new URL(url).pathname;requests.push(path);
     if(path==='/v1/presentation/slide_index')return {ok:true,status:200,json:async()=>({presentation:{index:actualIndex,presentation_id:{uuid:'abc-def'}}})};
     const match=path.match(/^\/v1\/presentation\/abc-def\/(\d+)\/trigger$/);
     if(match){actualIndex=Number(match[1]);return {ok:true,status:204};}
     return {ok:false,status:404};
   }
 });
 const director=new PresentationDirector({adapter:a});
 director.load(deck);
 await director.arm(true);
 await director.start('manual');
 await director.command({action:'next'});
 assert.equal(director.snapshot().current.id,'lyrics');
 assert.ok(requests.includes('/v1/presentation/abc-def/13/trigger'));
 await director.command({action:'next'});
 assert.equal(director.snapshot().current.id,'reading');
 assert.equal((await director.readback()).confirmed,true);
 assert.ok(requests.includes('/v1/presentation/abc-def/2/trigger'));
 assert.equal(requests.includes('/v1/presentation/active/next/trigger'),false,
   'Mapped targets must use exact cue triggering, not blind next.');
});
test('invalid negative target index is rejected before starting the show',()=>{
 const adapter={name:'mock',external:true,show:async()=>({ok:true})};
 const director=new PresentationDirector({adapter});
 assert.throws(()=>director.load({slides:[{id:'oops',targetIndex:-4}]}),/targetIndex|index/i);
});
