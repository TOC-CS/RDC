#!/usr/bin/env python3
"""Isolated private teleprompter Chromium/WebKit acceptance without physical devices."""
import json
import shutil
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parent.parent
NODE=shutil.which('node')
if not NODE:
 raise RuntimeError('Node is unavailable for local test fixture')
PRIVATE='PRIVATE_FIRST_LINE_OF_SERMON'
SECOND='PRIVATE_SECOND_LINE_OF_SERMON'
KEYS={
 'stage':'test-teleprompt-stage-bearer-2026',
 'audience':'test-teleprompt-audience-bearer-2026',
 'stream':'test-teleprompt-broadcast-bearer-2026'
}
results=[]
with sync_playwright() as playwright:
 for name,engine in [('chromium',playwright.chromium),('webkit',playwright.webkit)]:
  fixture=subprocess.Popen([NODE,str(ROOT/'scripts/teleprompt-visual-fixture.mjs')],
   cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
   stderr=subprocess.PIPE,text=True,bufsize=1)
  try:
   config=json.loads(fixture.stdout.readline())
   base='http://127.0.0.1:'+str(config['port'])
   browser=engine.launch(headless=True)
   try:
    stage=browser.new_page(viewport={'width':1280,'height':720})
    audience=browser.new_page(viewport={'width':1280,'height':720})
    stream=browser.new_page(viewport={'width':1280,'height':720})
    assert stage.goto(base+'/v1/stage?key='+KEYS['stage']).status==200
    assert audience.goto(base+'/v1/viewer?key='+KEYS['audience']).status==200
    assert stream.goto(base+'/v1/stream-overlay?key='+KEYS['stream']).status==200
    expect(stage.locator('#teleprompt-current')).to_have_text(PRIVATE,timeout=5000)
    assert stage.locator('#teleprompt').is_visible()
    assert PRIVATE not in audience.content()
    assert PRIVATE not in stream.content()
    def command(action):
     fixture.stdin.write(json.dumps({'action':action})+'\n')
     fixture.stdin.flush()
     reply=json.loads(fixture.stdout.readline())
     assert reply.get('ok')==True,reply
    command('singer')
    expect(stage.locator('#teleprompt-current')).to_have_text('Welcome to our original service',timeout=5000)
    assert stage.locator('#teleprompt').get_attribute('data-mirrored')=='true'
    assert '1.6rem' in (stage.locator('#teleprompt').get_attribute('style') or '')
    command('speaker')
    expect(stage.locator('#teleprompt-current')).to_have_text(PRIVATE,timeout=5000)
    command('follow')
    expect(stage.locator('#teleprompt-current')).to_have_text(SECOND,timeout=5000)
    command('hold')
    command('stage-clear')
    expect(stage.locator('#teleprompt-current')).to_have_text('',timeout=5000)
    assert not stage.locator('#teleprompt').is_visible()
    command('stage-visible')
    expect(stage.locator('#teleprompt-current')).to_have_text(SECOND,timeout=5000)
    assert PRIVATE not in audience.content()
    assert SECOND not in stream.content()
    screenshot=ROOT/'evidence'/f'worship-teleprompt-private-{name}-20261117.png'
    stage.screenshot(path=str(screenshot))
    command('stop')
    command('unload')
    expect(stage.locator('#teleprompt-current')).to_have_text('',timeout=5000)
    assert not stage.locator('#teleprompt').is_visible()
    results.append({'engine':name,'privatePromptRendered':True,
      'publicStageIsolation':True,'mirroredLayout':True,
      'confirmedSpeechCursor':True,'clearAndUnload':True,
      'screenshot':str(screenshot)})
   finally:browser.close()
  finally:
   fixture.terminate()
   try:fixture.wait(timeout=3)
   except subprocess.TimeoutExpired:fixture.kill();fixture.wait(timeout=2)
print(json.dumps({'schema':'toc.worship.teleprompt-browser/v1','passed':len(results)==2,
 'softwareOnly':True,'physicalStageAccepted':False,
 'microphoneOrCameraActivated':False,'broadcastChanged':False,
 'results':results},indent=2))
