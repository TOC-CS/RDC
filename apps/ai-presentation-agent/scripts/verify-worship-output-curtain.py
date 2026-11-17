#!/usr/bin/env python3
"""Real Chromium/WebKit local HTML audience blackout and independent OBS overlay clear.
Uses synthetic, owner-isolated localhost fixtures only. Never touches native OBS,
projector devices, real microphone/camera, broadcast destinations or MIDI.
"""
import json
import subprocess
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parent.parent
KEYS={
 'audience':'visual-test-audience-token-2026',
 'stage':'visual-test-stage-token-2026',
 'stream':'visual-test-stream-token-2026'
}
PRIVATE='PRIVATE_STAGE_VISUAL_TEST_MARKER'
report={'schema':'toc.worship.curtailed-outputs-visual/v1',
 'softwareOnly':True,'nativeProjectorBlanked':False,
 'obsSceneOrStreamChanged':False,'engines':[]}
def send(fixture,action):
 fixture.stdin.write(json.dumps({'action':action})+'\n')
 fixture.stdin.flush()
 receipt=json.loads(fixture.stdout.readline())
 if receipt.get('ok')!=True:
  raise AssertionError('Isolated output action was rejected: '+action)

with sync_playwright() as browsers:
 for name,engine in [('chromium',browsers.chromium),('webkit',browsers.webkit)]:
  fixture=subprocess.Popen(
   ['/opt/homebrew/opt/node@24/bin/node',str(ROOT/'scripts/worship-visual-fixture.mjs')],
   cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
   text=True,bufsize=1
  )
  try:
   setup=json.loads(fixture.stdout.readline())
   base='http://127.0.0.1:'+str(setup['port'])
   browser=engine.launch(headless=True)
   try:
    audience=browser.new_page(viewport={'width':1280,'height':720})
    stage=browser.new_page(viewport={'width':1280,'height':720})
    broadcast=browser.new_page(viewport={'width':1280,'height':720})
    assert audience.goto(base+'/v1/viewer?key='+KEYS['audience']).status==200
    assert stage.goto(base+'/v1/stage?key='+KEYS['stage']).status==200
    assert broadcast.goto(base+'/v1/stream-overlay?key='+KEYS['stream']).status==200
    expect(stage.locator('#private-notes')).to_contain_text(PRIVATE,timeout=4000)
    broadcast.locator('#overlay').wait_for(state='visible',timeout=4000)
    assert audience.locator('.slide:not([hidden]) h1').is_visible()

    send(fixture,'visibility-broadcast-clear')
    expect(broadcast.locator('body')).to_have_attribute('data-visibility','clear',timeout=4000)
    assert broadcast.locator('#overlay').is_hidden()
    assert audience.locator('.slide:not([hidden]) h1').is_visible()
    assert PRIVATE in stage.locator('#private-notes').inner_text()

    send(fixture,'visibility-audience-blank')
    expect(audience.locator('body')).to_have_attribute('data-visibility','blank',timeout=4000)
    expect(audience.locator('body')).to_have_css('background-color','rgb(0, 0, 0)')
    expect(audience.locator('main')).to_have_css('visibility','hidden')
    audience_image=ROOT/'evidence'/f'worship-audience-black-{name}-20261117.png'
    audience.screenshot(path=str(audience_image))
    with Image.open(audience_image) as image:
     rgb=image.convert('RGB')
     assert rgb.getpixel((640,360))==(0,0,0),'Audience center must be opaque black'

    send(fixture,'visibility-stage-clear')
    expect(stage.locator('#status')).to_have_text('STAGE CLEARED',timeout=4000)
    assert stage.locator('#private-notes').inner_text()==''
    assert stage.locator('#current').inner_text()==''
    assert PRIVATE not in audience.content()
    assert PRIVATE not in broadcast.content()

    send(fixture,'visibility-broadcast-visible')
    expect(broadcast.locator('body')).to_have_attribute('data-visibility','visible',timeout=4000)
    broadcast.locator('#overlay').wait_for(state='visible',timeout=4000)
    send(fixture,'visibility-audience-visible')
    expect(audience.locator('body')).to_have_attribute('data-visibility','visible',timeout=4000)
    assert audience.locator('.slide:not([hidden]) h1').is_visible()
    send(fixture,'visibility-stage-visible')
    expect(stage.locator('#private-notes')).to_contain_text(PRIVATE,timeout=4000)
    assert PRIVATE not in audience.content()
    assert PRIVATE not in broadcast.content()

    send(fixture,'stop');send(fixture,'unload')
    expect(audience.locator('#session-status')).to_have_text('PRESENTATION CLEARED',timeout=4000)
    broadcast.locator('#overlay').wait_for(state='hidden',timeout=4000)
    expect(stage.locator('#private-notes')).to_have_text('',timeout=4000)
    report['engines'].append({
     'engine':name,'audienceOpaqueBlackVerified':True,
     'broadcastClearedWithoutAudienceChange':True,
     'stagePrivateDataClearedAndRestored':True,
     'privateInformationExcludedFromPublicOutputs':True,
     'recoveredWithoutMovingCue':True,
     'screenshot':str(audience_image)
    })
   finally:browser.close()
  finally:
   fixture.terminate()
   try:fixture.wait(timeout=3)
   except subprocess.TimeoutExpired:
    fixture.kill();fixture.wait(timeout=2)
report['passed']=len(report['engines'])==2
print(json.dumps(report,indent=2))
