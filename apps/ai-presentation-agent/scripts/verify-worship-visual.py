#!/usr/bin/env python3
"""Headless Chromium/WebKit output isolation and transparent OBS overlay test.
No real stage, livestream or installed broadcaster is controlled.
"""
import json
import os
import subprocess
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parent.parent
fixture=subprocess.Popen(
    ['/opt/homebrew/opt/node@24/bin/node',str(root/'scripts/worship-visual-fixture.mjs')],
    cwd=root,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
    text=True,bufsize=1
)
audience='visual-test-audience-token-2026'
stage_key='visual-test-stage-token-2026'
stream_key='visual-test-stream-token-2026'
private='PRIVATE_STAGE_VISUAL_TEST_MARKER'
report={'schema':'toc.worship.browser-visual-acceptance/v1','softwareOnly':True,
 'physicalVenueAccepted':False,'actualOBSConnected':False,'results':[]}
try:
    setup=fixture.stdout.readline()
    if not setup: raise RuntimeError('Isolated worship fixture did not start')
    port=json.loads(setup)['port']
    base=f'http://127.0.0.1:{port}'
    with sync_playwright() as p:
        for kind,engine in [('chromium',p.chromium),('webkit',p.webkit)]:
            browser=engine.launch(headless=True)
            try:
                stage=browser.new_page(viewport={'width':1280,'height':720})
                stream=browser.new_page(viewport={'width':1280,'height':720})
                audience_page=browser.new_page(viewport={'width':1280,'height':720})
                assert stage.goto(f'{base}/v1/stage?key={stage_key}').status==200
                assert stream.goto(f'{base}/v1/stream-overlay?key={stream_key}').status==200
                assert audience_page.goto(f'{base}/v1/viewer?key={audience}').status==200
                stage.locator('#private-notes').get_by_text(private).wait_for(timeout=4000)
                stream.locator('#overlay').wait_for(state='visible',timeout=4000)
                assert private in stage.locator('#private-notes').inner_text()
                assert private not in audience_page.content()
                assert private not in stream.content()
                assert 'PRIVATE:' not in stream.locator('main').inner_text()
                assert stage_key not in stream.content()
                assert stage_key not in audience_page.content()
                assert stream_key not in stage.content()
                bg=stream.evaluate('getComputedStyle(document.body).backgroundColor')
                assert bg in ('rgba(0, 0, 0, 0)','transparent'),bg
                stage_image=root/'evidence'/f'worship-stage-{kind}-20261117.png'
                broadcast_image=root/'evidence'/f'worship-stream-{kind}-20261117.png'
                stage.screenshot(path=str(stage_image))
                stream.screenshot(path=str(broadcast_image),omit_background=True)
                with Image.open(broadcast_image) as image:
                    rgba=image.convert('RGBA')
                    alpha=rgba.getpixel((0,0))[3]
                    assert alpha==0,f'{kind} broadcast top-left alpha expected 0, received {alpha}'
                report['results'].append({'engine':kind,'privateStageVisible':True,
                    'audiencePrivateDataExcluded':True,'broadcastPrivateDataExcluded':True,
                    'streamTransparentCorner':True,'streamBackground':bg,
                    'stageScreenshot':str(stage_image),
                    'broadcastScreenshot':str(broadcast_image)})
            finally:browser.close()
    report['passed']=len(report['results'])==2
    print(json.dumps(report,indent=2))
finally:
    fixture.terminate()
    try:fixture.wait(timeout=3)
    except subprocess.TimeoutExpired:
        fixture.kill();fixture.wait(timeout=2)
