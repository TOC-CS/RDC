import test from 'node:test';
import assert from 'node:assert/strict';
import {EventEmitter} from 'node:events';
import {PassThrough} from 'node:stream';
import {PowerPointWindowsAdapter,buildWindowsPowerPointScript} from '../src/windows-powerpoint.mjs';

test('Windows PowerPoint script attaches only to an existing running slideshow',()=>{
 const script=buildWindowsPowerPointScript('next');
 assert.match(script,/GetActiveObject/);
 assert.match(script,/SlideShowWindows/);
 assert.match(script,/\.Next\(\)/);
 assert.ok(!script.includes('New-Object -ComObject PowerPoint.Application'));
});
test('Windows PowerPoint script builds documented slide controls and readback',()=>{
 assert.match(buildWindowsPowerPointScript('previous'),/\.Previous\(\)/);
 assert.match(buildWindowsPowerPointScript('goto',3),/\.GotoSlide\(4\)/);
 assert.match(buildWindowsPowerPointScript('readback'),/CurrentShowPosition/);
 assert.throws(()=>buildWindowsPowerPointScript('delete-slide'),/Unsupported/i);
 assert.throws(()=>buildWindowsPowerPointScript('goto','4'),/index/i);
});
test('Windows PowerPoint adapter refuses unsupported host OS',()=>{
 assert.throws(()=>new PowerPointWindowsAdapter({platform:'darwin'}),/Windows/i);
});
test('Windows PowerPoint adapter parses zero-based real position from COM output',async()=>{
 const runner=(cmd,args)=>{
   assert.equal(cmd,'powershell.exe');
   assert.ok(args.includes('-EncodedCommand'));
   const script=Buffer.from(args.at(-1),'base64').toString('utf16le');
   assert.match(script,/CurrentShowPosition/);
   const child=new EventEmitter();
   child.stdout=new PassThrough();child.stderr=new PassThrough();
   queueMicrotask(()=>{
     child.stdout.write('3\r\n');
     child.emit('exit',0);
   });
   return child;
 };
 const ppt=new PowerPointWindowsAdapter({platform:'win32',runner});
 const result=await ppt.readback({expectedIndex:2});
 assert.equal(result.index,2);
 assert.equal(result.confirmed,true);
 assert.equal(result.source,'powerpoint-windows-com');
});
