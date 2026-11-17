import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {platform} from 'node:os';
import {buildKeynoteScript} from '../src/adapters.mjs';

test('Keynote native external writes require a playing show, not an editor-only document',()=>{
 for(const action of ['next','previous','goto']){
   const text=buildKeynoteScript(action,1);
   assert.match(text,/application "Keynote" is not running/);
   assert.match(text,/playing of application "Keynote"/);
   assert.match(text,/No Keynote slideshow is playing/i);
 }
});
test('Keynote playing guard compiles and refuses an unloaded app without triggering an auto-launch',t=>{
 if(platform()!=='darwin')return t.skip('macOS required');
 const isRunning=()=>spawnSync('/usr/bin/osascript',['-e','return application "Keynote" is running'],
   {encoding:'utf8',timeout:3000});
 const probe=isRunning();
 assert.equal(probe.status,0,probe.stderr);
 if(probe.stdout.trim()!=='false')return t.skip('Leave an already-running Keynote session undisturbed.');
 const result=spawnSync('/usr/bin/osascript',['-e',buildKeynoteScript('next')],
   {encoding:'utf8',timeout:3000});
 assert.notEqual(result.status,0);
 assert.equal(isRunning().stdout.trim(),'false','Keynote remains unopened');
});
