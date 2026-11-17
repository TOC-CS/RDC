import test from 'node:test';
import assert from 'node:assert/strict';
import {PresentationDirector} from '../src/director.mjs';
import {MemoryAdapter} from '../src/adapters.mjs';

test('repeated presentation start does not unexpectedly restart a live show at slide one',async()=>{
 const adapter=new MemoryAdapter();
 const director=new PresentationDirector({adapter});
 director.load({slides:[{id:'a'},{id:'b'}]});
 await director.start('automatic');
 await director.command({action:'next'});
 const eventsBefore=adapter.events.length;
 const repeated=await director.start('automatic');
 assert.equal(repeated.current.id,'b');
 assert.equal(adapter.events.length,eventsBefore);
 await assert.rejects(()=>director.start('manual'),/running|mode/i);
 assert.equal(director.snapshot().current.id,'b');
});
test('two concurrent duplicate start calls cannot trigger two initial external writes',async()=>{
 let writes=0;
 const adapter={name:'external',external:true,show:async()=>{writes++;await new Promise(r=>setTimeout(r,5));return {ok:true};}};
 const director=new PresentationDirector({adapter});
 director.load({slides:[{id:'a'}]});await director.arm(true);
 await Promise.all([director.start('automatic'),director.start('automatic')]);
 assert.equal(writes,1);
});
