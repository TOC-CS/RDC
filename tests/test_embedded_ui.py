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
from tests.ui_artifacts import artifact_path

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
const selected = config.get('session') || window.openResult.session_id;
if (config.get('worker')!=='real' && selected !== window.openResult.session_id) {
  window.openResult.sessions.push({session_id:selected,kind:'mobile',viewport:{width:390,height:844}});
  window.openResult.session_id=selected;
}
if(config.get('initial')==='unbound') delete window.openResult.viewer;
if(config.get('resize')==='1') window.openResult.sessions.find(s=>s.session_id===selected).resize_to_view=true;

window.pendingResults = new Map(); window.statusCalls = 0; window.openCalls = 0;
window.deferFrames = 0; window.deferOpen = 0; window.recoveryAllowed = true;
window.resizeErrorCode=config.get('resize_error'); window.deferResizes=Number(config.get('resize_pending')||0);
window.nativeWidth=null; window.nativeHeight=null;
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
  frame.src = '/preview.html';
  if(config.get('short_mount')==='1') frame.style.height='80px'; document.getElementById('mount').replaceChildren(frame);
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
    if(config.get('initial')!=='unbound') send({method:'ui/notifications/tool-input',params:{arguments:{session_id:selected}}});
    if(config.get('worker')==='real') {
      fetch('/fixture/tool',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:'rdc_preview_open',arguments:{session_id:selected}})})
        .then(response=>response.json()).then(result=>send({method:'ui/notifications/tool-result',params:result}));
    } else {
      let result={structuredContent:window.openResult,content:[{type:'text',text:JSON.stringify(window.openResult)}]};
      if(config.get('initial')==='pending') {
        const id='initial-open-operation'; window.pendingResults.set(id,{result,remaining:2,kind:'primary'}); result=pendingResult(id);
      }
      send({method:'ui/notifications/tool-result',params:result});
    }
  } else if (message.method === 'tools/call') {
    const {name,arguments:args} = message.params;
    window.toolCalls.push({name,arguments:args});
    window.activeRequests += 1; window.maxRequests = Math.max(window.maxRequests,window.activeRequests);
    const finishRequest = () => {window.activeRequests -= 1;};
    if (name === 'rdc_preview_frame') window.frameCalls += 1;
    if (name === 'rdc_preview_open') window.openCalls += 1;
    setTimeout(async () => {
      if (config.get('worker')==='real') {
        try {
          const response = await fetch('/fixture/tool',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,arguments:args})});
          reply(message.id,await response.json());
        } finally { finishRequest(); }
        return;
      }
      if(name==='rdc_operation_status') {
        window.statusCalls += 1;
        const pending=window.pendingResults.get(args.operation_id);
        if(!pending) reply(message.id,{isError:true,structuredContent:{ok:false,error:{message:'Unknown test operation'}},content:[]});
        else if(!window.recoveryAllowed || pending.remaining-->0) reply(message.id,pendingResult(args.operation_id));
        else {window.completedRecoveryIDs.push(args.operation_id);reply(message.id,pending.result);}
        finishRequest(); return;
      }
      let data = structuredClone(window.openResult), content;
      if (name === 'rdc_preview_frame') {
        data = {ok:true,device_id:'fixture-device',session_id:window.wrongSession?'wrong-session':args.session_id,
          width:900,height:560,viewport:{width:900,height:560},cursor:{x:280,y:200,visible:true},
          paused:false,mime_type:'image/png',image_in_content:true,captured_at:new Date().toISOString()};
        if(window.nativeWidth) Object.assign(data,{window_width:window.nativeWidth,window_height:window.nativeHeight});
        content = [{type:'image',mimeType:'image/png',data:PNG}];
        if(window.frameErrorCode) {data={ok:false,error:{code:window.frameErrorCode,message:'Synthetic capture refusal'}};content=[];}
      } else if (name === 'rdc_preview_open') {
        if(args.session_id && !data.sessions.some(item=>item.session_id===args.session_id)) data={ok:false,error:{code:'session_not_found',message:'Requested fixture session ended'}};
        else data.session_id=args.session_id||data.sessions[0]?.session_id||null;
      } else if (name === 'rdc_preview_resize' && config.get('resize')==='1') {
        data={ok:true,session_id:args.session_id,device_id:'fixture-device',width:args.width,height:args.height,size_constrained:false};
        if(window.resizeErrorCode) data={ok:false,error:{code:window.resizeErrorCode}};
      } else {
        window.workerAlive = false; window.sessionAlive = false;
        data = {ok:false,error:{message:'Forbidden mutation in read-only fixture'}};
      }
      let result={structuredContent:data,content:content||[{type:'text',text:JSON.stringify(data)}]};
      if((name==='rdc_preview_frame'&&window.deferFrames>0)||(name==='rdc_preview_open'&&window.deferOpen>0)||(name==='rdc_preview_resize'&&window.deferResizes>0)) {
        if(name==='rdc_preview_frame') window.deferFrames-=1; else if(name==='rdc_preview_resize') window.deferResizes-=1; else window.deferOpen-=1;
        const id='pending-preview-'+(++pendingSequence);
        window.pendingResults.set(id,{result,remaining:1,kind:'preview'}); result=pendingResult(id);
      }
      reply(message.id,result);
      finishRequest();
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


def real_worker_tool_result(engine, request):
    """Test-host bridge with the exact local worker observation allowlist."""
    if engine is None or request['name'] not in ('rdc_preview_open', 'rdc_preview_frame'):
        raise ValueError('Forbidden fixture tool')
    result = engine.call(request['name'], request['arguments'])
    metadata = {key: value for key, value in result.items() if key != 'data'}
    content = []
    if result.get('mime_type') and result.get('data'):
        metadata['image_in_content'] = True
        content.append({'type': 'image', 'mimeType': result['mime_type'], 'data': result['data']})
    content.insert(0, {'type': 'text', 'text': json.dumps(metadata)})
    return {'structuredContent': metadata, 'content': content, 'isError': result.get('ok') is False}


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
            'viewer': {'bound_to_session': True, 'close_keeps_working': True}}
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
                if self.path != '/fixture/tool':
                    self.send_error(403); return
                try:
                    result = real_worker_tool_result(cls.real_engine, request)
                except ValueError:
                    self.send_error(403); return
                payload = json.dumps(result).encode()
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

    def assert_singleflight_reads(self):
        self.assertLessEqual(self.page.evaluate('window.maxRequests'), 1)

    def assert_pinned(self, session_id=SESSION):
        calls = self.page.evaluate('window.toolCalls')
        frames = [call['arguments']['session_id'] for call in calls if call['name'] == 'rdc_preview_frame']
        self.assertTrue(frames)
        self.assertEqual(set(frames), {session_id})

    def assert_read_only(self):
        calls = self.page.evaluate('window.toolCalls')
        self.assertTrue(all(call['name'] in ('rdc_preview_open', 'rdc_preview_frame', 'rdc_operation_status') for call in calls))
        self.assertTrue(self.page.evaluate('window.workerAlive && window.sessionAlive'))
        self.assertEqual(self.errors, [])

    def test_preview_only_shows_the_bound_source_and_does_not_poll_dashboard(self):
        self.live()
        self.assertEqual(self.view.get_by_role('combobox').count(), 0)
        self.assertEqual(self.view.locator('details, pre').count(), 0)
        self.wait_condition('window.frameCalls >= 2')
        calls = self.page.evaluate('window.toolCalls')
        self.assertNotIn('rdc_preview_activity', [call['name'] for call in calls])
        self.assert_pinned()
        self.assert_read_only()

    def test_live_image_fills_the_panel_in_light_mode(self):
        self.live()
        self.page.evaluate("window.sendContext({theme:'light'})")
        self.view.locator('html[data-theme="light"]').wait_for()
        panel = self.view.locator('#panel').bounding_box()
        screen = self.view.locator('#screen').bounding_box()
        self.assertGreater(screen['height'] / panel['height'], 0.85)
        self.assertEqual(self.view.locator('#frame').evaluate('(image) => image.naturalWidth'), 900)
        self.assert_read_only()

    def test_native_window_resizes_to_landscape_in_tall_host_and_hide_stops_resizing(self):
        window_session='window-'+SESSION
        self.page.goto(self.base+'?session='+window_session+'&resize=1')
        self.page.set_viewport_size({'width':400,'height':900})
        self.live()
        self.wait_condition("window.toolCalls.some(c=>c.name==='rdc_preview_resize'&&c.arguments.width<400)")
        requests=self.page.evaluate("window.toolCalls.filter(c=>c.name==='rdc_preview_resize')")
        args=requests[-1]['arguments']
        self.assertEqual(args['session_id'],window_session)
        self.assertLess(args['width'],400)
        self.assertAlmostEqual(args['width']/args['height'],16/9,delta=.02)
        self.assertTrue(args['_rdc_request_id'])
        panel=self.view.locator('#panel').bounding_box()
        host=self.page.locator('#app-frame').bounding_box()
        self.assertAlmostEqual(panel['height'],host['height'],delta=2)
        self.view.get_by_role('button',name='Hide preview',exact=True).click()
        count=len(self.page.evaluate("window.toolCalls.filter(c=>c.name==='rdc_preview_resize')"))
        self.page.set_viewport_size({'width':500,'height':800})
        self.page.wait_for_timeout(1800)
        self.assertEqual(len(self.page.evaluate("window.toolCalls.filter(c=>c.name==='rdc_preview_resize')")),count)
        self.assertTrue(self.page.evaluate('window.workerAlive && window.sessionAlive'))

    def test_inline_landscape_size_recovers_after_hide_and_short_mount(self):
        self.live()
        self.view.get_by_role('button',name='Hide preview',exact=True).click()
        self.wait_condition("document.getElementById('app-frame').clientHeight<100")
        self.view.get_by_role('button',name='Reopen preview',exact=True).click()
        self.live()
        self.wait_condition("document.getElementById('app-frame').clientHeight>400")
        screen=self.view.locator('#screen').bounding_box()
        self.assertAlmostEqual(screen['width']/screen['height'],16/9,delta=.02)
        self.page.goto(self.base+'?short_mount=1');self.live()
        self.wait_condition("document.getElementById('app-frame').clientHeight>400")
        screen=self.view.locator('#screen').bounding_box()
        self.assertAlmostEqual(screen['width']/screen['height'],16/9,delta=.02)

    def test_window_permission_retry_retires_only_definitively_unperformed_resize(self):
        for pending in (0,1):
            self.page.goto(self.base+'?session=window-'+SESSION+'&resize=1&resize_error=accessibility_permission_required&resize_pending='+str(pending))
            self.live()
            self.view.get_by_role('button',name='Retry window resizing',exact=True).wait_for(timeout=15000)
            self.assertIn('current size',self.view.locator('#mode-note').inner_text())
            first=self.page.evaluate("window.toolCalls.filter(c=>c.name==='rdc_preview_resize')")
            self.assertEqual(len(first),1)
            self.page.evaluate('window.resizeErrorCode=null')
            self.view.get_by_role('button',name='Retry window resizing',exact=True).click()
            self.wait_condition("window.toolCalls.filter(c=>c.name==='rdc_preview_resize').length===2")
            self.live()
            calls=self.page.evaluate("window.toolCalls.filter(c=>c.name==='rdc_preview_resize')")
            self.assertEqual(len(calls),2)
            self.assertNotEqual(calls[0]['arguments']['_rdc_request_id'],calls[1]['arguments']['_rdc_request_id'])

    def test_window_frame_uses_current_native_dimensions_after_external_resize(self):
        self.page.goto(self.base+'?session=window-'+SESSION+'&resize=1')
        self.live()
        self.page.evaluate('window.nativeWidth=720;window.nativeHeight=820')
        self.view.locator('#frame').evaluate("image=>image.dataset.before=image.style.width")
        self.wait_condition('window.frameCalls>=2')
        self.assertEqual(self.view.locator('#frame').evaluate('image=>[image.style.width,image.style.height]'),['720px','820px'])

    def test_uncertain_resize_keeps_exact_capture_and_original_recovery_identity(self):
        for pending in (0,1):
            self.page.goto(self.base+'?session=window-'+SESSION+'&resize=1&resize_error=host_tool_unavailable&resize_pending='+str(pending))
            self.live()
            self.assertIn('unconfirmed',self.view.locator('#mode-note').inner_text())
            calls=self.page.evaluate("window.toolCalls.filter(c=>c.name==='rdc_preview_resize')")
            self.assertEqual(len(calls),1)
            self.wait_condition('window.frameCalls>=2')
            self.assertEqual(len(self.page.evaluate("window.toolCalls.filter(c=>c.name==='rdc_preview_resize')")),1)
            self.view.get_by_role('button',name='Retry window resizing',exact=True).click()
            self.live()
            if pending:
                self.assertEqual(len(self.page.evaluate("window.toolCalls.filter(c=>c.name==='rdc_preview_resize')")),1)
                ids=self.page.evaluate("window.toolCalls.filter(c=>c.name==='rdc_operation_status').map(c=>c.arguments.operation_id)")
                self.assertEqual(len(set(ids)),1)
            else:
                self.wait_condition("window.toolCalls.filter(c=>c.name==='rdc_preview_resize').length===2")
                after=self.page.evaluate("window.toolCalls.filter(c=>c.name==='rdc_preview_resize')")
                self.assertEqual(after[0]['arguments'],after[1]['arguments'])
            self.page.evaluate("window.frameErrorCode='screenshot_redaction_required'")
            self.view.get_by_role('heading',name='Preview hidden for privacy').wait_for(timeout=15000)
            self.assertTrue(self.view.locator('#frame').is_hidden())
            self.assert_pinned('window-'+SESSION)

    def test_legacy_desktop_binding_never_captures_or_requests_mode(self):
        self.page.goto(self.base+'?session=desktop')
        self.view.get_by_role('heading',name='No visual source').wait_for(timeout=5000)
        self.assertTrue(self.view.locator('#frame').is_hidden())
        self.assertEqual(self.page.evaluate('window.toolCalls'),[])
        self.assertEqual(self.page.evaluate('window.requestedModes'),[])

    def test_unbound_legacy_open_never_reads_the_global_source(self):
        self.page.goto(self.base + '?initial=unbound')
        self.view = self.page.frame_locator('#app-frame')
        self.view.get_by_role('heading', name='No visual source').wait_for()
        self.assertTrue(self.view.locator('#frame').is_hidden())
        self.assertEqual(self.page.evaluate('window.toolCalls'), [])

    def test_hide_reopen_and_host_teardown_preserve_worker_session(self):
        self.live()
        self.view.get_by_role('button', name='Hide preview', exact=True).click()
        self.view.get_by_text('Preview hidden. Work keeps running.', exact=True).wait_for()
        calls = self.page.evaluate('window.frameCalls')
        ticks = self.page.evaluate('window.workerTicks')
        hidden_at = self.page.evaluate('performance.now()')
        self.wait_condition('(snapshot) => window.workerTicks > snapshot.ticks && performance.now() - snapshot.at >= 1750',
                            arg={'ticks': ticks, 'at': hidden_at})
        self.assertEqual(self.page.evaluate('window.frameCalls'), calls)
        self.assertGreater(self.page.evaluate('window.workerTicks'), ticks)
        self.view.get_by_role('button', name='Reopen preview', exact=True).click()
        self.wait_condition('(n) => window.frameCalls > n', arg=calls)
        self.assert_pinned()
        self.wait_condition('window.contextUpdates.some(item=>item.structuredContent?.rdc_preview?.session_id)')
        self.view.get_by_role('button', name='Hide preview', exact=True).click()
        self.view.get_by_role('button', name='Dismiss view', exact=True).click()
        self.wait_condition('window.teardownAcks === 1')
        self.assertEqual(self.page.locator('#app-frame').count(), 0)
        self.assert_read_only()
        self.page.evaluate('window.mountPreview()')
        self.view = self.page.frame_locator('#app-frame'); self.live()
        self.assert_pinned()
        self.assert_read_only()

    def test_ended_source_never_falls_back_to_another_active_session(self):
        self.live()
        self.page.evaluate('''() => {
            window.openResult.sessions.push({session_id:'1830547e-5ecd-4b37-9ba1-08e96b5d0754',browser:'chromium'});
            window.frameErrorCode='session_not_found';
        }''')
        self.view.get_by_role('heading', name='Session ended').wait_for()
        self.assertTrue(self.view.locator('#frame').is_hidden())
        self.assertEqual(self.page.evaluate('window.openCalls'), 0)
        self.assert_pinned()
        self.assert_read_only()

    def test_mobile_capture_refusal_clears_pixels_and_retains_source(self):
        mobile = 'mobile-87654321-4321-4321-4321-cba987654321'
        self.page.goto(self.base + '?session=' + mobile)
        self.view = self.page.frame_locator('#app-frame')
        self.live()
        self.page.evaluate("window.frameErrorCode='screenshot_redaction_required'")
        self.view.get_by_role('heading', name='Preview hidden for privacy').wait_for()
        self.assertTrue(self.view.locator('#frame').is_hidden())
        self.assertIsNone(self.view.locator('#frame').get_attribute('src'))
        self.page.evaluate('window.frameErrorCode=null')
        self.view.get_by_role('button', name='Retry preview').click()
        self.live()
        self.assert_pinned(mobile)
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
        hide = self.view.get_by_role('button', name='Hide preview', exact=True)
        control = hide.bounding_box()
        self.assertGreaterEqual(control['y'], 0)
        self.assertLessEqual(control['y'] + control['height'], 200)
        self.assert_read_only()

    def test_two_live_viewers_keep_their_own_browser_sources(self):
        from rdc.config import Settings
        from rdc.engine import Engine
        from urllib.parse import quote
        from playwright.sync_api import expect
        with tempfile.TemporaryDirectory(prefix='rdc-two-viewers-') as directory:
            root=Path(directory).resolve()
            engine=Engine(Settings(state_dir=root/'state',roots=[root],approval_mode='trusted'))
            type(self).real_engine=engine
            second_page=self.browser.new_page(viewport={'width':900,'height':800})
            try:
                ids=[]
                for title,color in [('Task A','#ee4444'),('Task B','#2244ee')]:
                    result=engine.call('rdc_browser_start',{'browser':'chromium'});self.assertTrue(result['ok'],result)
                    ids.append(result['session_id'])
                    result=engine.call('rdc_browser_navigate',{'session_id':ids[-1],'url':'data:text/html,'+quote('<title>'+title+'</title><body style="background:'+color+'"><h1>'+title+'</h1>')})
                    self.assertTrue(result['ok'],result)
                self.page.goto(self.base+'?worker=real&session='+ids[0]);self.live()
                second_page.goto(self.base+'?worker=real&session='+ids[1])
                other=second_page.frame_locator('#app-frame').locator('#frame');expect(other).to_be_visible(timeout=15000)
                first=self.view.locator('#frame');a=first.get_attribute('src');b=other.get_attribute('src');self.assertNotEqual(a,b)
                engine.call('rdc_browser_navigate',{'session_id':ids[0],'url':'data:text/html,'+quote('<title>A changed</title><body style="background:green"><h1>A changed</h1>')})
                expect(first).not_to_have_attribute('src',a,timeout=6000)
                second_page.wait_for_timeout(1700)
                self.assertEqual(other.get_attribute('src'),b)
                for page,session in [(self.page,ids[0]),(second_page,ids[1])]:
                    self.assertTrue(all(c['arguments'].get('session_id')==session for c in page.evaluate('window.toolCalls') if c['name'] in ('rdc_preview_open','rdc_preview_frame')))
                    self.assertEqual(page.evaluate('window.requestedModes'),[])
                self.view.get_by_role('button',name='Hide preview',exact=True).click()
                expect(other).to_be_visible()
                self.assertEqual(len(engine.call('rdc_browser_list',{})['sessions']),2)
            finally:
                second_page.close();type(self).real_engine=None;engine.close()

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
                self.page.goto(self.base + '?worker=real&session=' + session_id)
                self.view = self.page.frame_locator('#app-frame'); self.live()
                self.assert_pinned(session_id)
                from playwright.sync_api import expect
                cursor = self.view.locator('#cursor')
                old_position = cursor.get_attribute('style') or ''
                observation = engine.call('rdc_browser_observe', {'session_id': session_id})
                moved = engine.call('rdc_browser_pointer', {
                    'session_id': session_id, 'observation_id': observation['observation_id'],
                    'action': 'move', 'x': 300, 'y': 190,
                })
                self.assertTrue(moved['ok'], moved)
                expect(cursor).to_be_visible(timeout=5000)
                expect(cursor).not_to_have_attribute('style', old_position)
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
                self.assert_pinned(session_id)
                self.page.screenshot(path=str(artifact_path('embedded-preview.png')), full_page=True)
                self.view.get_by_role('button', name='Hide preview', exact=True).click()
                self.view.get_by_role('button', name='Dismiss view', exact=True).click()
                self.wait_condition('window.teardownAcks===1')
                self.assertIn(session_id, [item['session_id'] for item in engine.call('rdc_browser_list', {})['sessions']])
                self.page.evaluate('window.mountPreview()')
                self.view = self.page.frame_locator('#app-frame'); self.live()
                self.assert_pinned(session_id)
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
    def test_display_mode_tracks_host_and_does_not_change_source(self):
        self.live()
        self.view.get_by_role('button', name='Expand', exact=True).click()
        self.wait_condition('window.currentMode === "fullscreen"')
        self.assertEqual(self.view.locator('#canvas').get_attribute('data-mode'), 'fullscreen')
        self.view.get_by_role('button', name='Float', exact=True).click()
        self.wait_condition('window.currentMode === "pip"')
        self.view.get_by_role('button', name='Inline', exact=True).click()
        self.wait_condition('window.currentMode === "inline"')
        self.page.evaluate('window.deniedMode = "inline"')
        self.view.get_by_role('button', name='Expand', exact=True).click()
        self.view.get_by_text('The app kept its current display mode.', exact=True).wait_for()
        self.assertEqual(self.view.locator('#canvas').get_attribute('data-mode'), 'inline')
        self.assert_pinned()
        self.assert_read_only()

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
        self.assert_pinned()
        self.assert_read_only()

    def test_single_inflight_read_and_reject_wrong_session_frame(self):
        self.live()
        self.page.evaluate('window.delayMs = 600; window.wrongSession = true')
        self.view.get_by_text('The preview response belongs to a different session.', exact=True).wait_for()
        self.assertTrue(self.view.locator('#frame').is_hidden())
        self.assert_singleflight_reads()
        self.page.evaluate('window.wrongSession = false')
        self.view.get_by_role('button', name='Retry preview', exact=True).click()
        self.live()
        self.assert_singleflight_reads()
        self.assert_pinned()
        self.assert_read_only()

    def test_initial_pending_open_recovers_original_without_another_open(self):
        self.page.goto(self.base + '?initial=pending')
        self.view = self.page.frame_locator('#app-frame'); self.live()
        self.assertEqual(self.page.evaluate('window.openCalls'), 0)
        self.assertGreaterEqual(self.page.evaluate('window.statusCalls'), 3)
        self.assertIn('initial-open-operation', self.page.evaluate('window.completedRecoveryIDs'))
        self.assert_pinned()
        self.assert_singleflight_reads()
        self.assert_read_only()

    def test_pending_frame_hide_reopen_resumes_the_same_operation(self):
        self.live()
        self.page.evaluate('window.deferFrames=1; window.recoveryAllowed=false')
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
        self.assert_singleflight_reads()
        self.assert_read_only()

    def test_pending_recovery_deadline_requires_manual_original_observation(self):
        self.live()
        self.page.evaluate('window.deferFrames=1; window.recoveryAllowed=false')
        self.wait_condition('window.statusCalls>0 && window.activeRequests===0')
        # Advance only the view's test clock to exercise the two-minute bound.
        self.view.locator('html').evaluate('''() => { const actual=performance.now.bind(performance); Object.defineProperty(performance,'now',{value:()=>actual()+130000}); }''')
        self.view.get_by_text('The preview recovery wait ended. Retry preview checks the original observation.', exact=True).wait_for()
        frames = self.page.evaluate('window.frameCalls'); statuses = self.page.evaluate('window.statusCalls')
        self.page.wait_for_timeout(800)
        self.assertEqual(self.page.evaluate('window.frameCalls'), frames)
        self.assertEqual(self.page.evaluate('window.statusCalls'), statuses)
        self.page.evaluate('window.recoveryAllowed=true')
        self.view.get_by_role('button', name='Retry preview', exact=True).click()
        self.wait_condition('(n)=>window.statusCalls>n && window.activeRequests===0', arg=statuses)
        self.assertEqual(self.page.evaluate('window.frameCalls'), frames)
        self.assert_read_only()

    def test_missing_server_tool_bridge_never_polls(self):
        self.page.goto(self.base + '?bridge=0')
        self.view = self.page.frame_locator('#app-frame')
        self.view.get_by_text('This app does not provide the live preview connection.', exact=True).wait_for()
        self.page.wait_for_timeout(1750)
        self.assertEqual(self.page.evaluate('window.toolCalls'), [])
        self.assert_read_only()


if __name__ == '__main__':
    unittest.main()
