import test from 'node:test';
import assert from 'node:assert/strict';
import {WorshipOutputVisibility} from '../src/worship-output-visibility.mjs';

test('output curtains start visible and never perform native, OBS, stream or recording writes',()=>{
 const visibility=new WorshipOutputVisibility();
 const report=visibility.snapshot();
 assert.equal(report.revision,0);
 assert.deepEqual(report.outputs,[
   {destination:'audience',mode:'visible'},
   {destination:'stage',mode:'visible'},
   {destination:'broadcast',mode:'visible'}
 ]);
 assert.equal(report.nativeDisplayWritesPerformed,false);
 assert.equal(report.obsSceneChanged,false);
 assert.equal(report.streamOrRecordChanged,false);
});
test('broadcast clear does not blank audience nor remove private stage confidence',()=>{
 const observed=[];
 const curtains=new WorshipOutputVisibility({onChange:s=>observed.push(s)});
 curtains.set('broadcast','clear');
 assert.equal(curtains.get('broadcast'),'clear');
 assert.equal(curtains.get('audience'),'visible');
 assert.equal(curtains.get('stage'),'visible');
 assert.equal(curtains.snapshot().revision,1);
 assert.equal(observed.length,1);
});
test('audience blank is separate from broadcast overlay clear and does not change cue index',()=>{
 const curtains=new WorshipOutputVisibility();
 curtains.set('audience','blank');
 curtains.set('broadcast','clear');
 assert.equal(curtains.get('audience'),'blank');
 assert.equal(curtains.get('broadcast'),'clear');
 assert.equal(curtains.get('stage'),'visible');
 assert.equal(curtains.snapshot().nativeDisplayWritesPerformed,false);
});
test('unsafe stream-control values and invalid stage blank fail before state mutation',()=>{
 const curtains=new WorshipOutputVisibility();
 for(const [destination,mode] of [
   ['broadcast','stop-stream'],['obs','clear'],['stage','blank'],
   ['audience','delete'],['broadcast',{visibility:'clear'}]
 ])assert.throws(()=>curtains.set(destination,mode),/destination|visibility|mode|not allowed/i);
 assert.equal(curtains.snapshot().revision,0);
});
test('operator clear can be restored locally without moving slide state and resets between services',()=>{
 const curtains=new WorshipOutputVisibility();
 curtains.set('broadcast','clear');curtains.set('audience','blank');
 curtains.set('audience','visible');
 assert.equal(curtains.get('audience'),'visible');
 assert.equal(curtains.get('broadcast'),'clear');
 curtains.reset({restartRevision:true});
 assert.equal(curtains.snapshot().revision,0);
 assert.equal(curtains.get('broadcast'),'visible');
});
