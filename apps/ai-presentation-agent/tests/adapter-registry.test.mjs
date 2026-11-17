import test from 'node:test';
import assert from 'node:assert/strict';
import {registerPresentationAdapter,makeAdapter} from '../src/adapters.mjs';
test('custom presentation outputs can be plugged in by RDC or another host without changing the core',async()=>{
 const received=[];
 const unbind=registerPresentationAdapter('rdc-host-sample',()=>{
   return {name:'rdc-host-sample',external:true,show:async(index)=>{received.push(index);return {ok:true};}};
 });
 try{
   const adapter=makeAdapter('rdc-host-sample');
   assert.equal(adapter.external,true);
   await adapter.show(2);
   assert.deepEqual(received,[2]);
 }finally{unbind();}
});
test('registry prevents accidental replacement of installed output adapters',()=>{
 assert.throws(()=>registerPresentationAdapter('obs',()=>({show(){}})),/reserved|built-in/i);
 assert.throws(()=>registerPresentationAdapter('../bad',()=>({show(){}})),/name|invalid/i);
});
