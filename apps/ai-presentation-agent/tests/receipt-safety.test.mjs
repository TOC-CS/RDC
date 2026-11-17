import test from 'node:test';
import assert from 'node:assert/strict';
import {PresentationDirector} from '../src/director.mjs';

const deck={slides:[{id:'first',title:'First'},{id:'second',title:'Second'}]};
test('explicit failed external output receipt cannot advance internal deck',async()=>{
 let attempt=0;
 const adapter={name:'external-fail',external:true,
   show:async()=>({ok:true}),next:async()=>{attempt++;return {ok:false};}};
 const director=new PresentationDirector({adapter});
 director.load(deck);await director.arm(true);await director.start('manual');
 await assert.rejects(()=>director.command({action:'next'}),/output|failed|rejected/i);
 assert.equal(director.snapshot().index,0);
 assert.equal(attempt,1);
});
test('strict readback failure must not count as a successful slide change or trigger retry',async()=>{
 let displayed=0,writes=0;
 const adapter={name:'external-readback',external:true,requiresReadback:true,
   show:async(index)=>{displayed=index;return {ok:true};},
   next:async()=>{writes++;return {ok:true};},
   readback:async({expectedIndex})=>({supported:true,index:displayed,confirmed:displayed===expectedIndex&&expectedIndex===0})};
 const director=new PresentationDirector({adapter});
 director.load(deck);await director.arm(true);await director.start('manual');
 await assert.rejects(()=>director.command({action:'next'}),/readback|mismatch/i);
 assert.equal(director.snapshot().index,0);
 assert.equal(writes,1);
});
test('strict readback succeeds when adapter independently confirms the intended slide',async()=>{
 let actual=0;
 const adapter={name:'external-ok',external:true,requiresReadback:true,
   show:async(index)=>{actual=index;return {ok:true};},
   next:async()=>{actual++;return {ok:true};},
   readback:async({expectedIndex})=>({supported:true,index:actual,confirmed:actual===expectedIndex})};
 const director=new PresentationDirector({adapter});
 director.load(deck);await director.arm(true);await director.start('automatic');
 const out=await director.command({action:'next'});
 assert.equal(out.changed,true);
 assert.equal(director.snapshot().index,1);
});
