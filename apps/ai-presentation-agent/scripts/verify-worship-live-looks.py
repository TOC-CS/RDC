#!/usr/bin/env python3
"""Chromium/WebKit live Look updates on separate stage/audience/broadcast outputs.
An isolated localhost synthetic fixture; no external apps, real OBS or devices.
"""
import json
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parent.parent
TOKENS={
    'audience':'visual-test-audience-token-2026',
    'stage':'visual-test-stage-token-2026',
    'stream':'visual-test-stream-token-2026'
}
PRIVATE='PRIVATE_STAGE_VISUAL_TEST_MARKER'

def send(fixture,action):
    fixture.stdin.write(json.dumps({'action':action})+'\n')
    fixture.stdin.flush()
    ack=json.loads(fixture.stdout.readline())
    if ack.get('ok')!=True:
        raise AssertionError(f'Isolated action {action} failed')

report={
    'schema':'toc.worship.live-looks-browser/v1',
    'softwareOnly':True,'physicalHardwareAccepted':False,
    'obsSceneChanges':0,'streamOrRecordingStarted':False,
    'engines':[]
}
with sync_playwright() as playwright:
    for name,engine in [('chromium',playwright.chromium),('webkit',playwright.webkit)]:
        fixture=subprocess.Popen(
            ['/opt/homebrew/opt/node@24/bin/node',str(ROOT/'scripts/worship-visual-fixture.mjs')],
            cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,text=True,bufsize=1
        )
        try:
            start=json.loads(fixture.stdout.readline())
            base='http://127.0.0.1:'+str(start['port'])
            browser=engine.launch(headless=True)
            try:
                audience=browser.new_page(viewport={'width':1280,'height':720})
                stage=browser.new_page(viewport={'width':1280,'height':720})
                stream=browser.new_page(viewport={'width':1280,'height':720})
                assert audience.goto(base+'/v1/viewer?key='+TOKENS['audience']).status==200
                assert stage.goto(base+'/v1/stage?key='+TOKENS['stage']).status==200
                assert stream.goto(base+'/v1/stream-overlay?key='+TOKENS['stream']).status==200
                expect(stage.locator('#private-notes')).to_contain_text(PRIVATE,timeout=4000)
                assert audience.locator('.slide:not([hidden]) h1').is_visible()
                assert PRIVATE not in stream.content()
                assert PRIVATE not in audience.content()

                send(fixture,'look-broadcast-minimal')
                expect(stream.locator('body')).to_have_attribute('data-look','minimal',timeout=4000)
                assert stream.locator('#title').inner_text()==''
                assert audience.locator('.slide:not([hidden]) h1').is_visible()
                assert stage.locator('#private-notes').inner_text()==PRIVATE

                send(fixture,'look-audience-minimal')
                expect(audience.locator('body')).to_have_attribute('data-look','minimal',timeout=4000)
                assert audience.locator('.slide:not([hidden]) h1').is_hidden()
                assert audience.locator('.slide:not([hidden]) .slide-text').is_visible()

                send(fixture,'look-stage-no-notes')
                expect(stage.locator('#private-notes')).to_have_text('',timeout=4000)
                assert stage.locator('#private-notes').inner_text()==''
                assert PRIVATE not in audience.content()
                assert PRIVATE not in stream.content()

                send(fixture,'next')
                expect(audience.locator('.slide:not([hidden])')).to_have_attribute('data-index','1',timeout=4000)
                expect(stage.locator('#title')).to_have_text('Welcome',timeout=4000)
                assert audience.locator('.slide:not([hidden]) h1').is_hidden()
                assert stream.locator('#title').inner_text()==''

                path=ROOT/'evidence'/f'worship-live-looks-{name}-20261117.png'
                stream.screenshot(path=str(path),omit_background=True)
                send(fixture,'stop')
                send(fixture,'unload')
                expect(audience.locator('#session-status')).to_have_text('PRESENTATION CLEARED',timeout=4000)
                expect(stream.locator('#overlay')).to_be_hidden(timeout=4000)
                expect(stage.locator('#private-notes')).to_have_text('',timeout=4000)
                report['engines'].append({
                    'engine':name,'outputSpecificLookSelection':True,
                    'stagePrivacyAfterLookChanges':True,
                    'sameCueAcrossOutputs':True,
                    'unloadClearsDisplay':True,
                    'screenshot':str(path)
                })
            finally:
                browser.close()
        finally:
            fixture.terminate()
            try:fixture.wait(timeout=3)
            except subprocess.TimeoutExpired:fixture.kill();fixture.wait(timeout=2)

report['passed']=len(report['engines'])==2
print(json.dumps(report,indent=2))
