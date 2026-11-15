"""Embedded preview checks using a clearly test-only MCP Apps host fixture.

The real official App SDK runs inside a sandboxed iframe. The fixture implements
the host wire protocol and a synthetic read-only worker, so these checks prove
UI/lifecycle behavior, not actual ChatGPT or Claude product integration.
"""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from threading import Thread
import base64
import io
import json
import shutil
import sys
import tempfile
import time
import unittest

EMBEDDED = Path(__file__).resolve().parents[1] / 'rdc' / 'embedded'
SESSION = 'b2957a7b-2062-483f-b174-9c0a3d113d55'

HOST = r'''<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;background:#eef2f4;font:14px system-ui;color:#163444}main{max-width:1000px;margin:24px auto;padding:0 12px}
h1{font-size:20px;margin-bottom:5px}p{font-size:12px;margin-top:0;color:#55717f}iframe{width:100%;height:730px;border:0;border-radius:12px}
iframe.fullscreen{position:fixed;inset:0;width:100vw;height:100vh;border-radius:0;z-index:2}
iframe.pip{position:fixed;right:20px;bottom:20px;width:460px;height:500px;z-index:2}
</style></head><body><main><h1>RDC protocol test host</h1><p id="fixture-description">Synthetic MCP Apps host and browser image. This fixture is not ChatGPT or Claude.</p><div id="mount"></div></main><script>
const OPEN = __OPEN__;
const PNG = __PNG__;
const config = new URLSearchParams(location.search);
if(config.get('worker')==='real') document.getElementById('fixture-description').textContent='Live RDC browser worker inside a test MCP Apps host. This fixture is not ChatGPT or Claude.';
const modes = (config.get('modes') || 'inline,fullscreen,pip').split(',');
window.protocolCalls = []; window.toolCalls = []; window.requestedModes = [];
window.frameCalls = 0; window.activeRequests = 0; window.maxRequests = 0;
window.workerTicks = 0; window.workerAlive = true; window.sessionAlive = true;
window.teardownRequests = 0; window.teardownAcks = 0; window.delayMs = 0;
window.deniedMode = null; window.wrongSession = false; window.frameErrorCode = null; window.currentMode = 'inline';
window.openResult = structuredClone(OPEN); window.contextUpdates = [];
window.pendingResults = new Map(); window.statusCalls = 0; window.openCalls = 0;
window.deferFrames = 0; window.deferOpen = 0; window.recoveryAllowed = true;
window.completedRecoveryIDs = []; let pendingSequence = 0;
function pendingResult(id) {
  const data={ok:true,pending:true,operation_id:id,status:'claimed',recovery_tool:'rdc_operation_status'};
  return {structuredContent:data,content:[{type:'text',text:JSON.stringify(data)}]};
}
setInterval(() => { if (window.workerAlive) window.workerTicks += 1; }, 50);
let frame;
function send(data) { frame?.contentWindow.postMessage({jsonrpc:'2.0', ...data}, '*'); }
function reply(id,result) { send({id,result}); }
window.sendContext = context => send({method:'ui/notifications/host-context-changed',params:context});
function context() {
  return {theme:'dark',displayMode:window.currentMode,availableDisplayModes:modes,
    containerDimensions:{width:frame.clientWidth,height:frame.clientHeight},platform:'web'};
}
window.mountPreview = function() {
  frame = document.createElement('iframe'); frame.id = 'app-frame';
  frame.title = 'Embedded RDC protocol fixture'; frame.sandbox = 'allow-scripts';
  frame.src = '/preview.html'; document.getElementById('mount').replaceChildren(frame);
};
window.addEventListener('message', event => {
  if (event.source !== frame?.contentWindow || event.data?.jsonrpc !== '2.0') return;
  const message = event.data;
  if (message.id === 'host-teardown' && message.result) {
    window.teardownAcks += 1; frame.remove(); return;
  }
  window.protocolCalls.push({method:message.method,id:message.id});
  if (message.method === 'ui/initialize') {
    reply(message.id,{protocolVersion:message.params.protocolVersion,
      hostInfo:{name:'RDC fixture host',version:'1.0.0'},
      hostCapabilities:config.get('bridge')==='0'?{}:{serverTools:{},updateModelContext:{text:{}}},hostContext:context()});
  } else if (message.method === 'ui/notifications/initialized') {
    if(config.get('worker')==='real') {
      fetch('/fixture/tool',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:'rdc_preview_open',arguments:{}})})
        .then(response=>response.json()).then(result=>send({method:'ui/notifications/tool-result',params:result}));
    } else {
      let result={structuredContent:window.openResult,content:[{type:'text',text:JSON.stringify(window.openResult)}]};
      if(config.get('initial')==='pending') {
        const id='initial-open-operation'; window.pendingResults.set(id,{result,remaining:2}); result=pendingResult(id);
      }
      send({method:'ui/notifications/tool-result',params:result});
    }
  } else if (message.method === 'tools/call') {
    const {name,arguments:args} = message.params;
    window.toolCalls.push({name,arguments:args});
    window.activeRequests += 1; window.maxRequests = Math.max(window.maxRequests,window.activeRequests);
    if (name === 'rdc_preview_frame') window.frameCalls += 1;
    if (name === 'rdc_preview_open') window.openCalls += 1;
    setTimeout(async () => {
      if (config.get('worker')==='real') {
        try {
          const response = await fetch('/fixture/tool',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,arguments:args})});
          reply(message.id,await response.json());
        } finally { window.activeRequests -= 1; }
        return;
      }
      if(name==='rdc_operation_status') {
        window.statusCalls += 1;
        const pending=window.pendingResults.get(args.operation_id);
        if(!pending) reply(message.id,{isError:true,structuredContent:{ok:false,error:{message:'Unknown test operation'}},content:[]});
        else if(!window.recoveryAllowed || pending.remaining-->0) reply(message.id,pendingResult(args.operation_id));
        else {window.completedRecoveryIDs.push(args.operation_id);reply(message.id,pending.result);}
        window.activeRequests -= 1; return;
      }
      let data = structuredClone(window.openResult), content;
      if (name === 'rdc_preview_frame') {
        data = {ok:true,device_id:'fixture-device',session_id:window.wrongSession?'wrong-session':args.session_id,
          width:900,height:560,viewport:{width:900,height:560},cursor:{x:280,y:200,visible:true},
          paused:false,mime_type:'image/png',image_in_content:true,captured_at:new Date().toISOString()};
        content = [{type:'image',mimeType:'image/png',data:PNG}];
        if(window.frameErrorCode) {data={ok:false,error:{code:window.frameErrorCode,message:'Synthetic capture refusal'}};content=[];}
      } else if (name === 'rdc_preview_open') {
        if(args.session_id && !data.sessions.some(item=>item.session_id===args.session_id)) data={ok:false,error:{code:'session_not_found',message:'Requested fixture session ended'}};
        else data.session_id=args.session_id||data.sessions[0]?.session_id||null;
      } else {
        window.workerAlive = false; window.sessionAlive = false;
        data = {ok:false,error:{message:'Forbidden mutation in read-only fixture'}};
      }
      let result={structuredContent:data,content:content||[{type:'text',text:JSON.stringify(data)}]};
      if((name==='rdc_preview_frame'&&window.deferFrames>0)||(name==='rdc_preview_open'&&window.deferOpen>0)) {
        if(name==='rdc_preview_frame') window.deferFrames-=1; else window.deferOpen-=1;
        const id='pending-preview-'+(++pendingSequence);
        window.pendingResults.set(id,{result,remaining:1}); result=pendingResult(id);
      }
      reply(message.id,result);
      window.activeRequests -= 1;
    }, window.delayMs);
  } else if (message.method === 'ui/update-model-context') {
    window.contextUpdates.push(message.params); reply(message.id,{});
  } else if (message.method === 'ui/request-display-mode') {
    window.requestedModes.push(message.params.mode);
    window.currentMode = window.deniedMode || message.params.mode;
    frame.className = window.currentMode === 'inline'?'':window.currentMode;
    if(window.currentMode==='fullscreen') frame.style.height='100vh';
    else if(window.currentMode==='pip') frame.style.height='500px';
    else frame.style.height='730px';
    window.sendContext(context()); reply(message.id,{mode:window.currentMode});
  } else if (message.method === 'ui/notifications/size-changed') {
    if (window.currentMode==='inline') frame.style.height=Math.max(80,Math.min(1000,message.params.height))+'px';
  } else if (message.method === 'ui/notifications/request-teardown') {
    window.teardownRequests += 1; send({id:'host-teardown',method:'ui/resource-teardown',params:{}});
  } else if (message.id!==undefined) {
    send({id:message.id,error:{code:-32601,message:'Unsupported fixture request'}});
  }
});
window.mountPreview();
</script></body></html>'''


class EmbeddedResourceTests(unittest.TestCase):
    def test_bundled_resource_is_self_contained_and_bounded(self):
        html = (EMBEDDED / 'preview.html').read_text()
        self.assertLess(len(html.encode()), 4 * 1024 * 1024)
        self.assertNotIn('RDC_LOGO_DATA', html)
        self.assertNotIn('/* RDC_SCRIPT */', html)
        self.assertNotRegex(html, r'<script[^>]+src=')
        self.assertNotRegex(html, r'<link[^>]+href=')
        self.assertIn('ui/initialize', html)
        self.assertIn('data:image/png;base64,', html)
        notices = (EMBEDDED / 'THIRD_PARTY_NOTICES.txt').read_text()
        self.assertIn('@modelcontextprotocol/ext-apps 2.0.4', notices)
        self.assertIn('Permission is hereby granted', notices)


class EmbeddedPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch(headless=True, executable_path=shutil.which('chromium'), args=['--no-sandbox'])
        except Exception as exc:
            cls.playwright.stop()
            raise unittest.SkipTest(f'Chromium unavailable: {exc}')
        from PIL import Image, ImageDraw
        image = Image.new('RGB', (900, 560), '#f3f7fa')
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 900, 55), fill='#153447')
        draw.text((30, 23), 'RDC EMBEDDED PREVIEW TEST', fill='white')
        draw.rounded_rectangle((100, 140, 800, 410), radius=15, fill='white', outline='#c1d9e3', width=2)
        draw.text((140, 185), 'Synthetic browser fixture', fill='#1a4b60')
        draw.text((140, 220), 'View lifecycle is independent of the worker.', fill='#466c7c')
        draw.rounded_rectangle((140, 280, 320, 335), radius=8, fill='#65dfbd')
        draw.text((165, 302), 'Worker continues', fill='#153b30')
        output = io.BytesIO(); image.save(output, format='PNG')
        open_result = {'ok': True, 'device_id': 'fixture-device', 'session_id': SESSION,
            'sessions': [{'session_id': SESSION, 'backend': 'chromium', 'url': 'https://example.test/rdc-fixture', 'viewport': {'width': 900, 'height': 560}}],
            'paused': False, 'active_jobs': 1, 'pending_approvals': 0,
            'viewer': {'close_keeps_working': True, 'worker_required': True}}
        cls.host_html = HOST.replace('__OPEN__', json.dumps(open_result)).replace('__PNG__', json.dumps(base64.b64encode(output.getvalue()).decode()))
        host_html = cls.host_html
        cls.real_engine = None

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                payload = (EMBEDDED / 'preview.html').read_bytes() if self.path == '/preview.html' else host_html.encode()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(payload)))
                connect = "'none'" if self.path == '/preview.html' else "'self'"
                self.send_header('Content-Security-Policy', f"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; frame-src 'self'; connect-src {connect}; base-uri 'none'; form-action 'none'")
                self.end_headers(); self.wfile.write(payload)
            def do_POST(self):
                # Test-host-only shim. The production view has no direct network
                # access and still calls the official MCP Apps server-tool bridge.
                request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if self.path != '/fixture/tool' or request['name'] not in ('rdc_preview_open', 'rdc_preview_frame') or cls.real_engine is None:
                    self.send_error(403); return
                result = cls.real_engine.call(request['name'], request['arguments'])
                metadata = {key: value for key, value in result.items() if key != 'data'}
                content = []
                if result.get('mime_type') and result.get('data'):
                    metadata['image_in_content'] = True
                    content.append({'type': 'image', 'mimeType': result['mime_type'], 'data': result['data']})
                content.insert(0, {'type': 'text', 'text': json.dumps(metadata)})
                payload = json.dumps({'structuredContent': metadata, 'content': content, 'isError': result.get('ok') is False}).encode()
                self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(payload)))
                self.end_headers(); self.wfile.write(payload)
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.playwright.stop()
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def setUp(self):
        self.page = self.browser.new_page(viewport={'width': 1440, 'height': 1000})
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        self.page.goto(self.base)
        self.view = self.page.frame_locator('#app-frame')

    def tearDown(self):
        self.page.close()

    def wait_condition(self, expression, arg=None, timeout=15):
        # Poll from the test driver, not wait_for_function's in-page string
        # evaluator. The iframe and host retain their restrictive CSP.
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.page.evaluate(expression, arg):
                return
            self.page.wait_for_timeout(25)
        self.fail(f'Fixture condition did not become true: {expression}')

    def live(self):
        self.view.get_by_role('img', name='Live RDC workspace', exact=True).wait_for(timeout=15000)
        self.wait_condition('window.frameCalls > 0 && window.activeRequests === 0')

    def assert_read_only(self):
        calls = self.page.evaluate('window.toolCalls')
        self.assertTrue(all(call['name'] in ('rdc_preview_open', 'rdc_preview_frame', 'rdc_operation_status') for call in calls))
        self.assertTrue(self.page.evaluate('window.workerAlive && window.sessionAlive'))
        self.assertEqual(self.errors, [])

    def test_hide_reopen_and_host_teardown_preserve_worker_session(self):
        self.live()
        self.view.get_by_role('button', name='Hide preview', exact=True).click()
        self.view.get_by_text('Preview hidden', exact=True).wait_for()
        calls = self.page.evaluate('window.frameCalls')
        ticks = self.page.evaluate('window.workerTicks')
        self.page.wait_for_timeout(1750)
        self.assertEqual(self.page.evaluate('window.frameCalls'), calls)
        self.assertGreater(self.page.evaluate('window.workerTicks'), ticks)
        self.view.get_by_role('button', name='Reopen preview', exact=True).click()
        self.wait_condition('(n) => window.frameCalls > n', arg=calls)
        self.assertEqual(self.view.get_by_label('Workspace session', exact=True).input_value(), SESSION)
        self.wait_condition('window.contextUpdates.some(item=>item.structuredContent?.rdc_preview?.session_id)')
        self.view.get_by_role('button', name='Hide preview', exact=True).click()
        self.view.get_by_role('button', name='Dismiss view', exact=True).click()
        self.wait_condition('window.teardownAcks === 1')
        self.assertEqual(self.page.locator('#app-frame').count(), 0)
        self.assert_read_only()
        self.page.evaluate('window.mountPreview()')
        self.view = self.page.frame_locator('#app-frame'); self.live()
        self.assertEqual(self.view.get_by_label('Workspace session', exact=True).input_value(), SESSION)
        self.assert_read_only()

    def test_selected_second_session_survives_refresh_and_expired_session_is_explicit(self):
        self.live()
        second = '1830547e-5ecd-4b37-9ba1-08e96b5d0754'
        self.page.evaluate('''sid => window.openResult.sessions.push({session_id:sid,backend:'firefox',url:'https://second.test/',viewport:{width:900,height:560}})''', second)
        self.view.get_by_role('button', name='Sessions', exact=True).click()
        self.view.get_by_label('Workspace session', exact=True).select_option(second)
        self.wait_condition('window.activeRequests === 0')
        self.view.get_by_role('button', name='Sessions', exact=True).click()
        self.wait_condition('window.activeRequests === 0')
        self.assertEqual(self.view.get_by_label('Workspace session', exact=True).input_value(), second)
        self.page.evaluate('sid => window.openResult.sessions = window.openResult.sessions.filter(item=>item.session_id!==sid)', second)
        self.view.get_by_role('button', name='Sessions', exact=True).click()
        self.view.get_by_text('The selected session is no longer active', exact=True).wait_for()
        self.assertEqual(self.view.get_by_label('Workspace session', exact=True).input_value(), '')
        self.view.get_by_label('Workspace session', exact=True).select_option(SESSION)
        self.live()
        self.assert_read_only()

    def test_mobile_label_shared_input_and_private_capture_keep_work_alive(self):
        self.live()
        mobile = 'mobile-87654321-4321-4321-4321-cba987654321'
        self.page.evaluate('''sid => window.openResult.sessions.push({session_id:sid,kind:'mobile',backend:'appium',platform:'Android',profile:'fixture-phone',width:390,height:844,input_notice:'Input is shared with the configured mobile device.'})''', mobile)
        self.view.get_by_role('button', name='Sessions', exact=True).click()
        selector = self.view.get_by_label('Workspace session', exact=True)
        selector.select_option(mobile)
        self.live()
        self.assertIn('Android · fixture-phone', selector.locator('option:checked').inner_text())
        self.assertIn('shared', self.view.locator('#work-state').inner_text())
        self.assertEqual(self.view.locator('#page-address').inner_text(), 'Android · fixture-phone')
        self.page.evaluate("window.frameErrorCode='screenshot_redaction_required'")
        self.view.get_by_role('button', name='Refresh', exact=True).click()
        self.view.get_by_text('Preview hidden for privacy', exact=True).wait_for()
        self.assertTrue(self.view.locator('#frame').is_hidden())
        self.assertEqual(selector.input_value(), mobile)
        self.assertIn('1 active job', self.view.locator('#work-state').inner_text())
        self.assert_read_only()

    def test_ended_mobile_capture_stops_until_explicit_read_retry(self):
        self.live()
        mobile = 'mobile-87654321-4321-4321-4321-cba987654321'
        self.page.evaluate('''sid => {window.openResult.sessions.push({session_id:sid,kind:'mobile',backend:'appium',platform:'iOS',profile:'fixture-ipad'});window.frameErrorCode='mobile_session_gone';}''', mobile)
        self.view.get_by_role('button', name='Sessions', exact=True).click()
        self.view.get_by_label('Workspace session', exact=True).select_option(mobile)
        self.view.get_by_text('The native session has ended', exact=True).wait_for()
        self.wait_condition('window.activeRequests === 0')
        calls = self.page.evaluate('window.frameCalls')
        self.page.wait_for_timeout(1750)
        self.assertEqual(self.page.evaluate('window.frameCalls'), calls)
        self.assertEqual(self.view.get_by_label('Workspace session', exact=True).input_value(), mobile)
        self.assertIn('owner panel', self.view.locator('#empty-copy').inner_text())
        self.view.get_by_role('button', name='Refresh', exact=True).click()
        self.wait_condition('(n) => window.frameCalls === n + 1 && window.activeRequests === 0', calls)
        self.assert_read_only()

    def test_short_fullscreen_host_keeps_panel_and_controls_inside_canvas(self):
        self.page.set_viewport_size({'width': 390, 'height': 400})
        self.live()
        self.view.get_by_role('button', name='Expand', exact=True).click()
        self.wait_condition('window.currentMode === "fullscreen"')
        self.page.evaluate('document.getElementById("app-frame").style.height="200px"; window.sendContext({containerDimensions:{width:390,height:200}})')
        self.page.wait_for_timeout(100)
        panel = self.view.locator('#panel').bounding_box()
        self.assertGreaterEqual(panel['y'], 0)
        self.assertLessEqual(panel['y'] + panel['height'], 200)
        refresh = self.view.get_by_role('button', name='Refresh', exact=True)
        refresh.scroll_into_view_if_needed()
        control = refresh.bounding_box()
        self.assertGreaterEqual(control['y'], 0)
        self.assertLessEqual(control['y'] + control['height'], 200)
        self.assert_read_only()

    def test_real_worker_job_and_browser_survive_hidden_and_remounted_view(self):
        from rdc.config import Settings
        from rdc.engine import Engine
        with tempfile.TemporaryDirectory(prefix='rdc-embedded-') as directory:
            root = Path(directory).resolve(); work = root / 'work'; work.mkdir()
            engine = Engine(Settings(state_dir=root / 'state', roots=[work], approval_mode='trusted', allow_exec=True))
            type(self).real_engine = engine
            job_id = None
            try:
                started = engine.call('rdc_browser_start', {'browser': 'chromium'})
                self.assertTrue(started['ok'], started)
                session_id = started['session_id']
                from urllib.parse import quote
                demo = '<!doctype html><title>RDC live worker proof</title><style>body{font:24px system-ui;background:#edf6f5;color:#173447;padding:45px}main{border:1px solid #adcfc9;background:white;border-radius:16px;padding:32px}button{background:#65dfbd;border:0;border-radius:8px;padding:14px;font:inherit}</style><main><h1>Independent RDC workspace</h1><p>This frame comes from a real browser worker.</p><button>Browser session stays active</button></main>'
                navigated = engine.call('rdc_browser_navigate', {'session_id': session_id, 'url': 'data:text/html;charset=utf-8,' + quote(demo)})
                self.assertTrue(navigated['ok'], navigated)
                self.page.goto(self.base + '?worker=real')
                self.view = self.page.frame_locator('#app-frame'); self.live()
                self.assertEqual(self.view.get_by_label('Workspace session', exact=True).input_value(), session_id)
                script = "import pathlib,time; time.sleep(4); pathlib.Path('view-lifecycle.txt').write_text('RDC worker survived view lifecycle\\n'); print('RDC lifecycle job complete',flush=True)"
                job = engine.call('rdc_job_start', {'argv': [sys.executable, '-c', script], 'cwd': str(work), 'idempotency_key': 'embedded-lifecycle'})
                self.assertTrue(job['ok'], job); job_id = job['job']['id']
                self.view.get_by_role('button', name='Hide preview', exact=True).click()
                calls = self.page.evaluate('window.frameCalls')
                self.page.wait_for_timeout(1750)
                self.assertEqual(self.page.evaluate('window.frameCalls'), calls)
                self.assertIn(engine.call('rdc_job_status', {'job_id': job_id})['job']['status'], ('queued', 'running'))
                self.view.get_by_role('button', name='Reopen preview', exact=True).click()
                self.wait_condition('(count)=>window.frameCalls>count && window.activeRequests===0', arg=calls)
                self.assertEqual(self.view.get_by_label('Workspace session', exact=True).input_value(), session_id)
                out = EMBEDDED.parents[1] / 'test-results'; out.mkdir(exist_ok=True)
                self.page.screenshot(path=str(out / 'embedded-preview.png'), full_page=True)
                self.view.get_by_role('button', name='Hide preview', exact=True).click()
                self.view.get_by_role('button', name='Dismiss view', exact=True).click()
                self.wait_condition('window.teardownAcks===1')
                self.assertIn(session_id, [item['session_id'] for item in engine.call('rdc_browser_list', {})['sessions']])
                self.page.evaluate('window.mountPreview()')
                self.view = self.page.frame_locator('#app-frame'); self.live()
                self.assertEqual(self.view.get_by_label('Workspace session', exact=True).input_value(), session_id)
                deadline = time.monotonic() + 12
                while time.monotonic() < deadline:
                    status = engine.call('rdc_job_status', {'job_id': job_id})['job']
                    if status['status'] not in ('queued', 'running', 'cancelling'): break
                    time.sleep(0.05)
                self.assertEqual(status['status'], 'completed', status)
                self.assertEqual(status['exit_code'], 0)
                self.assertEqual((work / 'view-lifecycle.txt').read_text(), 'RDC worker survived view lifecycle\n')
                output = engine.call('rdc_job_output', {'job_id': job_id, 'offset': 0})
                self.assertIn('RDC lifecycle job complete', output['text'])
                observed = engine.call('rdc_browser_observe', {'session_id': session_id})
                self.assertIn('Independent RDC workspace', observed['text'])
                self.assert_read_only()
            finally:
                self.page.goto('about:blank')
                if job_id:
                    status = engine.call('rdc_job_status', {'job_id': job_id})['job']
                    if status['status'] in ('queued', 'running', 'cancelling'):
                        engine.call('rdc_job_cancel', {'job_id': job_id})
                        deadline = time.monotonic() + 5
                        while time.monotonic() < deadline and engine.call('rdc_job_status', {'job_id': job_id})['job']['status'] in ('queued', 'running', 'cancelling'):
                            time.sleep(0.05)
                engine.close(); type(self).real_engine = None
    def test_modes_constrained_move_resize_and_host_denial(self):
        self.live()
        self.view.get_by_role('button', name='Expand', exact=True).click()
        self.wait_condition('window.currentMode === "fullscreen"')
        panel = self.view.locator('#panel')
        before = panel.bounding_box()
        resize = self.view.get_by_role('button', name='Resize preview within RDC canvas', exact=True)
        resize.focus(); resize.press('ArrowLeft'); resize.press('ArrowUp')
        smaller = panel.bounding_box()
        self.assertLess(smaller['width'], before['width']); self.assertLess(smaller['height'], before['height'])
        move = self.view.get_by_role('button', name='Move preview within RDC canvas', exact=True)
        move.focus(); move.press('ArrowRight'); move.press('ArrowDown')
        moved = panel.bounding_box()
        self.assertGreater(moved['x'], smaller['x']); self.assertGreater(moved['y'], smaller['y'])
        # Actual pointer drag stays bounded by the host's allocated canvas.
        point = move.bounding_box()
        self.page.mouse.move(point['x'] + point['width']/2, point['y'] + point['height']/2)
        self.page.mouse.down(); self.page.mouse.move(2000, 2000); self.page.mouse.up()
        bounded = panel.bounding_box()
        self.assertGreaterEqual(bounded['x'], 0); self.assertGreaterEqual(bounded['y'], 0)
        self.assertLessEqual(bounded['x'] + bounded['width'], 1440)
        self.assertLessEqual(bounded['y'] + bounded['height'], 1000)
        self.view.get_by_role('button', name='Float', exact=True).click()
        self.wait_condition('window.currentMode === "pip"')
        self.view.get_by_role('button', name='Inline', exact=True).click()
        self.wait_condition('window.currentMode === "inline"')
        self.page.evaluate('window.deniedMode = "inline"')
        self.view.get_by_role('button', name='Expand', exact=True).click()
        self.view.get_by_text('Your AI app kept the preview in its current display mode.', exact=True).wait_for()
        self.assertEqual(self.view.locator('#canvas').get_attribute('data-mode'), 'inline')
        self.assert_read_only()
        out = EMBEDDED.parents[1] / 'test-results'; out.mkdir(exist_ok=True)
        self.page.screenshot(path=str(out / 'embedded-protocol-host.png'), full_page=True)

    def test_small_screen_and_missing_display_modes(self):
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.page.goto(self.base + '?modes=inline')
        self.view = self.page.frame_locator('#app-frame'); self.live()
        self.assertEqual(self.view.get_by_role('button', name='Expand', exact=True).count(), 0)
        self.assertEqual(self.view.get_by_role('button', name='Float', exact=True).count(), 0)
        self.assertFalse(self.view.locator('html').evaluate('(node) => node.scrollWidth > innerWidth'))
        # The official SDK ignores messages from the iframe itself. Only the
        # initialized parent source is allowed to send host notifications.
        self.view.locator('html').evaluate('''() => window.postMessage({jsonrpc:'2.0',method:'ui/notifications/tool-result',params:{structuredContent:{ok:true,sessions:[{session_id:'forged'}],session_id:'forged'},content:[]}}, '*')''')
        self.page.wait_for_timeout(100)
        self.assertEqual(self.view.get_by_label('Workspace session', exact=True).input_value(), SESSION)
        self.assert_read_only()

    def test_single_inflight_read_and_reject_wrong_session_frame(self):
        self.live()
        self.page.evaluate('window.delayMs = 600; window.wrongSession = true')
        self.view.get_by_role('button', name='Refresh', exact=True).click()
        self.view.get_by_text('The preview response belongs to a different session.', exact=True).wait_for()
        self.assertEqual(self.page.evaluate('window.maxRequests'), 1)
        self.page.evaluate('window.wrongSession = false')
        self.view.get_by_role('button', name='Refresh', exact=True).click()
        self.wait_condition('window.activeRequests === 0')
        self.assertEqual(self.page.evaluate('window.maxRequests'), 1)
        self.assertEqual(self.view.get_by_label('Workspace session', exact=True).input_value(), SESSION)
        self.assert_read_only()

    def test_initial_pending_open_recovers_original_without_another_open(self):
        self.page.goto(self.base + '?initial=pending')
        self.view = self.page.frame_locator('#app-frame'); self.live()
        self.assertEqual(self.page.evaluate('window.openCalls'), 0)
        self.assertGreaterEqual(self.page.evaluate('window.statusCalls'), 3)
        self.assertIn('initial-open-operation', self.page.evaluate('window.completedRecoveryIDs'))
        self.assertEqual(self.view.get_by_label('Workspace session', exact=True).input_value(), SESSION)
        self.assertEqual(self.page.evaluate('window.maxRequests'), 1)
        self.assert_read_only()

    def test_pending_frame_hide_reopen_resumes_the_same_operation(self):
        self.live()
        self.page.evaluate('window.deferFrames=1; window.recoveryAllowed=false')
        self.view.get_by_role('button', name='Refresh', exact=True).click()
        self.wait_condition('window.statusCalls>0 && window.activeRequests===0')
        original = self.page.evaluate('[...window.pendingResults.keys()][0]')
        self.view.get_by_role('button', name='Hide preview', exact=True).click()
        frames = self.page.evaluate('window.frameCalls'); statuses = self.page.evaluate('window.statusCalls')
        self.page.wait_for_timeout(900)
        self.assertEqual(self.page.evaluate('window.statusCalls'), statuses)
        self.assertEqual(self.page.evaluate('window.frameCalls'), frames)
        self.page.evaluate('window.recoveryAllowed=true; for(const item of window.pendingResults.values()) item.remaining=0')
        self.view.get_by_role('button', name='Reopen preview', exact=True).click()
        self.wait_condition('(id)=>window.completedRecoveryIDs.includes(id)', arg=original)
        self.assertEqual(self.page.evaluate('window.frameCalls'), frames)
        self.assertEqual(self.page.evaluate('window.maxRequests'), 1)
        self.assert_read_only()

    def test_pending_sessions_refresh_recovers_existing_operation(self):
        self.live()
        self.page.evaluate('window.deferOpen=1')
        before = self.page.evaluate('window.openCalls')
        self.view.get_by_role('button', name='Sessions', exact=True).click()
        self.wait_condition('window.completedRecoveryIDs.length>0 && window.activeRequests===0')
        self.assertEqual(self.page.evaluate('window.openCalls'), before + 1)
        self.assertEqual(self.view.get_by_label('Workspace session', exact=True).input_value(), SESSION)
        self.assertEqual(self.page.evaluate('window.maxRequests'), 1)
        self.assert_read_only()

    def test_pending_ended_session_fetches_one_list_and_requires_explicit_selection(self):
        self.live()
        remaining = '1830547e-5ecd-4b37-9ba1-08e96b5d0754'
        # Both the failed selected-session read and the replacement list take
        # the cloud pending-operation route. Neither may be dispatched twice.
        self.page.evaluate('''sid => {
            window.openResult.sessions = [{session_id:sid,backend:'firefox',url:'https://remaining.test/',viewport:{width:900,height:560}}];
            window.deferOpen = 2;
        }''', remaining)
        before = self.page.evaluate('window.openCalls')
        self.view.get_by_role('button', name='Sessions', exact=True).click()
        self.view.get_by_text('The selected session is no longer active', exact=True).wait_for()
        self.wait_condition('window.activeRequests === 0 && window.completedRecoveryIDs.length === 2')
        self.assertEqual(self.page.evaluate('window.openCalls'), before + 2)
        self.assertEqual(self.view.get_by_label('Workspace session', exact=True).input_value(), '')
        opens = self.page.evaluate('window.toolCalls.filter(call=>call.name === "rdc_preview_open").map(call=>call.arguments)')
        self.assertEqual(opens[-2:], [{'session_id': SESSION}, {}])
        self.assertEqual(self.view.get_by_label('Workspace session', exact=True).locator('option').count(), 2)
        self.view.get_by_label('Workspace session', exact=True).select_option(remaining)
        self.live()
        self.assertEqual(self.view.get_by_label('Workspace session', exact=True).input_value(), remaining)
        self.assertEqual(self.page.evaluate('window.maxRequests'), 1)
        self.assert_read_only()

    def test_approval_waiting_identifies_owner_panel_and_clears_at_zero(self):
        self.live()
        self.page.evaluate('window.openResult.pending_approvals=3; window.openResult.active_jobs=2')
        self.view.get_by_role('button', name='Sessions', exact=True).click()
        self.view.get_by_text('3 actions awaiting review', exact=False).wait_for()
        message = self.view.locator('#work-state').inner_text()
        self.assertIn('Last status check:', message)
        self.assertIn('2 active jobs', message)
        self.assertIn("RDC's owner panel on the paired computer", message)
        self.wait_condition('window.activeRequests === 0')
        self.page.evaluate('window.openResult.pending_approvals=0; window.openResult.active_jobs=0')
        self.view.get_by_role('button', name='Sessions', exact=True).click()
        self.view.get_by_text('Hiding this view keeps the worker running.', exact=True).wait_for()
        message = self.view.locator('#work-state').inner_text()
        self.assertNotIn('awaiting review', message)
        self.assertNotIn('active jobs', message)
        self.assertNotIn('owner panel', message)
        self.assert_read_only()

    def test_session_label_prefers_browser_name_over_backend(self):
        self.live()
        self.page.evaluate("window.openResult.sessions[0].backend='playwright'; window.openResult.sessions[0].browser='firefox'")
        self.view.get_by_role('button', name='Sessions', exact=True).click()
        option = self.view.get_by_label('Workspace session', exact=True).locator('option:checked').filter(has_text='firefox')
        option.wait_for(state='attached')
        self.wait_condition('window.activeRequests === 0')
        self.assertEqual(option.inner_text(), f'firefox · {SESSION[:8]}')
        self.assert_read_only()

    def test_pending_recovery_deadline_requires_manual_new_observation(self):
        self.live()
        self.page.evaluate('window.deferFrames=1; window.recoveryAllowed=false')
        self.view.get_by_role('button', name='Refresh', exact=True).click()
        self.wait_condition('window.statusCalls>0 && window.activeRequests===0')
        # Advance only the view's test clock to exercise the two-minute bound.
        self.view.locator('html').evaluate('''() => { const actual=performance.now.bind(performance); Object.defineProperty(performance,'now',{value:()=>actual()+130000}); }''')
        self.view.get_by_text('The preview recovery wait ended. Use Refresh to request a new observation.', exact=True).wait_for()
        frames = self.page.evaluate('window.frameCalls'); statuses = self.page.evaluate('window.statusCalls')
        self.page.wait_for_timeout(800)
        self.assertEqual(self.page.evaluate('window.frameCalls'), frames)
        self.assertEqual(self.page.evaluate('window.statusCalls'), statuses)
        self.page.evaluate('window.recoveryAllowed=true')
        self.view.get_by_role('button', name='Refresh', exact=True).click()
        self.wait_condition('(n)=>window.frameCalls>n && window.activeRequests===0', arg=frames)
        self.assertEqual(self.page.evaluate('window.statusCalls'), statuses)
        self.assert_read_only()

    def test_missing_server_tool_bridge_never_polls(self):
        self.page.goto(self.base + '?bridge=0')
        self.view = self.page.frame_locator('#app-frame')
        self.view.get_by_text('This AI app does not provide the server-tool bridge needed for live preview.', exact=True).wait_for()
        self.page.wait_for_timeout(1750)
        self.assertEqual(self.page.evaluate('window.toolCalls'), [])
        self.assertTrue(self.view.get_by_role('button', name='Refresh', exact=True).is_disabled())
        self.assert_read_only()


if __name__ == '__main__':
    unittest.main()
