import test from 'node:test';
import assert from 'node:assert/strict';
import {EventEmitter} from 'node:events';
import {PassThrough} from 'node:stream';
import {spawnSync} from 'node:child_process';
import {platform} from 'node:os';
import {KeynoteAdapter,buildKeynoteScript,buildPowerPointScript} from '../src/adapters.mjs';

test('native AppleScript commands refuse to launch a presentation application automatically',()=>{
  for(const [name,script] of [
    ['Keynote',buildKeynoteScript('next')],
    ['Microsoft PowerPoint',buildPowerPointScript('next')]
  ]){
    assert.match(script,new RegExp('application "'+name+'" is not running'));
    assert.match(script,/error .*not running/i);
  }
});
test('a hung AppleScript subprocess is terminated instead of blocking presentation commands forever',async()=>{
  let terminated=false;
  const runner=()=>{
    const child=new EventEmitter();
    child.stdout=new PassThrough();child.stderr=new PassThrough();
    child.kill=()=>{terminated=true;return true;};
    return child;
  };
  const keynote=new KeynoteAdapter({executor:runner,timeoutMs:75});
  await assert.rejects(keynote.next(),/timed out/i);
  assert.equal(terminated,true);
});
test('installed macOS presentation app preflight blocks commands without opening the app',t=>{
  if(platform()!=='darwin')return t.skip('macOS required');
  for(const [app,command] of [
    ['Keynote',buildKeynoteScript('next')],
    ['Microsoft PowerPoint',buildPowerPointScript('next')]
  ]){
    const probe=()=>spawnSync('/usr/bin/osascript',['-e',
      'return application "'+app+'" is running'],{encoding:'utf8',timeout:3000});
    const before=probe();
    assert.equal(before.status,0,before.stderr);
    if(before.stdout.trim()!=='false')continue;
    const guarded=spawnSync('/usr/bin/osascript',['-e',command],
      {encoding:'utf8',timeout:5000});
    assert.notEqual(guarded.status,0,'Disallowed launch must fail for '+app);
    const after=probe();
    assert.equal(after.stdout.trim(),'false','Must not launch '+app);
  }
});
