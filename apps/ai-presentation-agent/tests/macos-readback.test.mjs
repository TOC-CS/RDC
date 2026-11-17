import test from 'node:test';
import assert from 'node:assert/strict';
import {EventEmitter} from 'node:events';
import {PassThrough} from 'node:stream';
import {PowerPointMacAdapter,KeynoteAdapter,buildPowerPointScript,buildKeynoteScript} from '../src/adapters.mjs';

function commandRunner(text){
 return (_bin,_args)=>{
   const child=new EventEmitter();
   child.stdout=new PassThrough();child.stderr=new PassThrough();
   queueMicrotask(()=>{child.stdout.write(text);child.emit('exit',0);});
   return child;
 };
}
test('PowerPoint Mac readback uses installed AppleScript current slideshow position',()=>{
 assert.match(buildPowerPointScript('readback'),/current show position/);
});
test('Keynote readback uses selected slide and avoids claiming actual projection',()=>{
 assert.match(buildKeynoteScript('readback'),/slide number of current slide/);
});
test('PowerPoint Mac converts native one-based current position to zero-based index',async()=>{
 const ppt=new PowerPointMacAdapter({executor:commandRunner('3\n')});
 const r=await ppt.readback({expectedIndex:2});
 assert.equal(r.supported,true);
 assert.equal(r.index,2);
 assert.equal(r.confirmed,true);
 assert.equal(r.source,'powerpoint-macos-applescript');
});
test('Keynote selected slide alone does not prove the projected presentation changed',async()=>{
 const keynote=new KeynoteAdapter({executor:commandRunner('3\n')});
 const r=await keynote.readback({expectedIndex:2});
 assert.equal(r.supported,true);
 assert.equal(r.index,2);
 assert.equal(r.confirmed,false);
});
test('PowerPoint rejects malformed native readback',async()=>{
 const ppt=new PowerPointMacAdapter({executor:commandRunner('not-an-index\n')});
 await assert.rejects(()=>ppt.readback({expectedIndex:0}),/position|index/i);
});
