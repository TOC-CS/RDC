#!/usr/bin/env python3
"""Private stage timer visual isolation in Chromium + WebKit.
Synthetic localhost fixture only. No projector, OBS, native apps, audio devices.
"""
import json
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parent.parent
KEYS={
  'stage':'visual-test-stage-token-2026',
  'audience':'visual-test-audience-token-2026',
  'broadcast':'visual-test-stream-token-2026'
}
PRIVATE='PRIVATE_TIMER_VISUAL_MARKER'
results=[]
with sync_playwright() as playwright:
 for name,engine in [('chromium',playwright.chromium),('webkit',playwright.webkit)]:
  fixture=subprocess.Popen([
    '/opt/homebrew/opt/node@24/bin/node',
    str(ROOT/'scripts/worship-visual-fixture.mjs')
   ],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,text=True,bufsize=1)
  try:
   config=json.loads(fixture.stdout.readline())
   base='http://127.0.0.1:'+str(config['port'])
   browser=engine.launch(headless=True)
   try:
    stage=browser.new_page(viewport={'width':1280,'height':720})
    audience=browser.new_page(viewport={'width':1280,'height':720})
    broadcast=browser.new_page(viewport={'width':1280,'height':720})
    assert stage.goto(base+'/v1/stage?key='+KEYS['stage']).status==200
    assert audience.goto(base+'/v1/viewer?key='+KEYS['audience']).status==200
    assert broadcast.goto(base+'/v1/stream-overlay?key='+KEYS['broadcast']).status==200
    expect(stage.locator('#private-notes')).not_to_be_empty(timeout=4000)
    def command(action):
     fixture.stdin.write(json.dumps({'action':action})+'\n')
     fixture.stdin.flush()
     reply=json.loads(fixture.stdout.readline())
     assert reply.get('ok')==True,reply
    command('timer-configure')
    expect(stage.locator('#timer-label')).to_have_text(PRIVATE,timeout=4000)
    assert stage.locator('#timer-remaining').inner_text()=='01:30'
    assert PRIVATE not in audience.content()
    assert PRIVATE not in broadcast.content()
    command('timer-start')
    expect(stage.locator('#timer-remaining')).not_to_have_text('01:30',timeout=3500)
    remaining=stage.locator('#timer-remaining').inner_text()
    assert remaining.startswith('01:'),remaining
    command('timer-pause')
    expect(stage.locator('#timer-remaining')).not_to_be_empty(timeout=4000)
    command('visibility-stage-clear')
    expect(stage.locator('#timer-label')).to_have_text('',timeout=4000)
    assert PRIVATE not in stage.locator('#timer-label').inner_text()
    command('visibility-stage-visible')
    expect(stage.locator('#timer-label')).to_have_text(PRIVATE,timeout=4000)
    assert PRIVATE not in audience.content()
    assert PRIVATE not in broadcast.content()
    path=ROOT/'evidence'/f'worship-private-timer-{name}-20261117.png'
    stage.screenshot(path=str(path))
    command('stop')
    command('unload')
    expect(stage.locator('#timer-label')).to_have_text('',timeout=4000)
    results.append({'engine':name,'stageLabelVisible':True,
      'privateLabelAbsentFromPublic':True,
      'timerAdvancesOnlyOnStage':True,
      'stageClearAndRestoreWorks':True,
      'unloadClearsTimer':True,
      'screenshot':str(path)})
   finally:browser.close()
  finally:
   fixture.terminate()
   try:fixture.wait(timeout=3)
   except subprocess.TimeoutExpired:fixture.kill();fixture.wait(timeout=2)
print(json.dumps({'schema':'toc.worship.stage-clock-browser/v1',
  'softwareOnly':True,'physicalTimerDisplayQualified':False,
  'passed':len(results)==2,'engines':results},indent=2))
