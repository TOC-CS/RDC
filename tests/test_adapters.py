"""Adapter contract tests. WebDriver fixture verifies actual HTTP request handling."""
import base64
import io
import json
import os
import threading
import unittest
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import patch

try:
    from rdc.adapters import Adapters
except ImportError:
    Adapters = None


def settings(**kwargs):
    return SimpleNamespace(background_only=False, browser_backend='webdriver', webdriver_url=None,
        webdriver_capabilities={'browserName': 'safari'}, desktop_mode='disabled',
        adb_serial=None, **kwargs) if not kwargs else SimpleNamespace(background_only=False, **({
        'browser_backend':'webdriver', 'webdriver_url':None,
        'webdriver_capabilities':{'browserName':'safari'}, 'desktop_mode':'disabled',
        'adb_serial':None} | kwargs))


class Driver(BaseHTTPRequestHandler):
    requests = []
    active_sessions = set()
    fail_timeouts = False
    fail_navigations = False
    fail_observations = False
    fail_deletes = 0
    malformed_capabilities = False
    def log_message(self, *args): pass
    def do_DELETE(self): self.respond('DELETE')
    def do_GET(self): self.respond('GET')
    def do_POST(self): self.respond('POST')
    def respond(self, method):
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or b'{}')
        type(self).requests.append((method,self.path,body))
        value = None
        failure = (self.path.endswith('/timeouts') and type(self).fail_timeouts) or (method == 'POST' and self.path.endswith('/url') and type(self).fail_navigations) or (self.path.endswith('/execute/sync') and 'RDC_OBSERVE' in body.get('script','') and type(self).fail_observations)
        if method == 'DELETE' and type(self).fail_deletes:
            type(self).fail_deletes -= 1
            failure = True
        if failure:
            raw = json.dumps({'value':{'error':'unknown error','message':'Synthetic driver failure'}}).encode()
            self.send_response(500); self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(raw)
            return
        if self.path == '/session':
            type(self).active_sessions.add('safe-session')
            value = {'sessionId':'safe-session','capabilities':None if type(self).malformed_capabilities else {'browserName':'safari'}}
        elif method == 'DELETE': type(self).active_sessions.discard('safe-session')
        elif self.path.endswith('/url') and method == 'GET': value = 'http://fixture.test/'
        elif self.path.endswith('/title'): value = 'Fixture'
        elif self.path.endswith('/window/rect') and method == 'GET': value = {'width':800,'height':600}
        elif self.path.endswith('/screenshot'): value = base64.b64encode(b'\x89PNG\r\n\x1a\nfixture').decode()
        elif self.path.endswith('/execute/sync'):
            if 'RDC_OBSERVE' in body['script']:
                value = {'text':'Fixture text','document_id':'doc1','width':800,'height':600,
                    'controls':[{'element':{'element-6066-11e4-a52e-4f735466cecf':'element1'},'tag':'input','name':'Name','type':'text','value':''}]}
            elif 'RDC_DOCUMENT' in body['script']: value = 'doc1'
        raw = json.dumps({'value':value}).encode()
        self.send_response(200); self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(raw)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(Adapters, 'Adapters must implement the device contract')
        Driver.requests=[]
        Driver.active_sessions=set(); Driver.fail_timeouts=False; Driver.fail_navigations=False; Driver.fail_observations=False; Driver.fail_deletes=0; Driver.malformed_capabilities=False
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Driver)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.a=Adapters(settings(webdriver_url=f'http://127.0.0.1:{self.server.server_port}'))
    def tearDown(self):
        if hasattr(self,'a'): self.a.close()
        if hasattr(self,'server'): self.server.shutdown(); self.server.server_close();self.thread.join()
    def start(self): return self.a.call('rdc_browser_start',{'browser':'safari'})['session_id']
    def test_catalog_truthful_mutations_and_no_agent_driver_endpoint(self):
        catalog={t['name']:t for t in self.a.catalog()}
        self.assertFalse(catalog['rdc_browser_observe']['x-rdc-mutating'])
        self.assertTrue(catalog['rdc_browser_click']['x-rdc-mutating'])
        self.assertNotIn('webdriver_url',catalog['rdc_browser_start']['inputSchema']['properties'])
        self.assertEqual('disabled',self.a.status()['desktop']['mode'])
    def test_real_webdriver_protocol_fill_rejects_stale_handle(self):
        sid=self.start(); obs=self.a.call('rdc_browser_observe',{'session_id':sid})
        args={'session_id':sid,'observation_id':obs['observation_id'],'handle':obs['controls'][0]['handle'],'text':'Sample User'}
        self.a.call('rdc_browser_fill',args)
        self.assertIn(('POST','/session/safe-session/element/element1/value',{'text':'Sample User','value':list('Sample User')}),Driver.requests)
        with self.assertRaisesRegex(Exception,'[Oo]bservation|[Ss]tale'): self.a.call('rdc_browser_fill',args)
    def test_browser_action_observe_composites_preserve_fresh_handles_and_no_replay(self):
        catalog={item['name']:item for item in self.a.catalog()}
        for name in ('rdc_browser_navigate_observe','rdc_browser_click_observe',
                     'rdc_browser_fill_observe'):
            self.assertTrue(catalog[name]['x-rdc-mutating'])
            self.assertTrue(catalog[name]['annotations']['destructiveHint'])
        sid=self.start()
        observed=self.a.call('rdc_browser_navigate_observe',{
            'session_id':sid,'url':'https://example.test/forms'})
        self.assertIn('Fixture text',observed['text'])
        self.assertTrue(observed['observation_id'])
        self.assertEqual(1,sum(method=='POST' and path=='/session/safe-session/url'
                              for method,path,_ in Driver.requests))
        original={'session_id':sid,'observation_id':observed['observation_id'],
                  'handle':observed['controls'][0]['handle'],'text':'RDC atomic input'}
        filled=self.a.call('rdc_browser_fill_observe',original)
        self.assertNotEqual(observed['observation_id'],filled['observation_id'])
        self.assertIn('Fixture text',filled['text'])
        with self.assertRaisesRegex(Exception,'[Oo]bservation|[Ss]tale'):
            self.a.call('rdc_browser_fill_observe',original)
        self.assertEqual(1,sum(path.endswith('/value') for _,path,_ in Driver.requests))
        clicked=self.a.call('rdc_browser_click_observe',{
            'session_id':sid,'observation_id':filled['observation_id'],
            'handle':filled['controls'][0]['handle']})
        self.assertNotEqual(filled['observation_id'],clicked['observation_id'])
        self.assertEqual(1,sum(path.endswith('/click') for _,path,_ in Driver.requests))
        self.assertIn('Fixture text',clicked['text'])

    def test_browser_start_navigate_observe_has_fresh_control_in_one_call(self):
        catalog={item['name']:item for item in self.a.catalog()}
        tool=catalog['rdc_browser_start_navigate_observe']
        self.assertTrue(tool['x-rdc-mutating'])
        self.assertEqual(['url'],tool['inputSchema']['required'])
        result=self.a.call('rdc_browser_start_navigate_observe',{
            'browser':'safari','url':'https://example.test/first'})
        self.assertTrue(result['ok'])
        self.assertTrue(result['session_id'])
        self.assertIn('Fixture text',result['text'])
        self.assertEqual('input',result['controls'][0]['tag'])
        self.assertTrue(result['observation_id'])
        self.assertEqual(1,sum(path=='/session' for _,path,_ in Driver.requests))
        self.assertEqual(1,sum(path.endswith('/url') and method=='POST'
                               for method,path,_ in Driver.requests))
        self.assertEqual(1,len(self.a.call('rdc_browser_list',{})['sessions']))

    def test_browser_start_navigate_observe_invalid_url_never_creates_session(self):
        for url in ('file:///etc/passwd','about:config','javascript:alert(1)'):
            with self.assertRaisesRegex(Exception,'URL'):
                self.a.call('rdc_browser_start_navigate_observe',{
                    'browser':'safari','url':url})
        self.assertEqual([],self.a.call('rdc_browser_list',{})['sessions'])
        self.assertEqual([],Driver.requests)

    def test_browser_start_navigate_observe_navigation_failure_retains_session(self):
        Driver.fail_navigations=True
        result=self.a.call('rdc_browser_start_navigate_observe',{
            'browser':'safari','url':'https://example.test/first'})
        self.assertIs(result['ok'],False)
        self.assertEqual('navigation',result['failure_stage'])
        self.assertEqual('navigation_failed',result['error_code'])
        self.assertIn(result['session_id'],
                      [x['session_id'] for x in self.a.call('rdc_browser_list',{})['sessions']])
        self.assertEqual(1,sum(path.endswith('/url') and method=='POST'
                               for method,path,_ in Driver.requests))
        self.assertEqual(1,len(Driver.active_sessions))

    def test_browser_start_navigate_observe_observation_failure_retains_session(self):
        Driver.fail_observations=True
        result=self.a.call('rdc_browser_start_navigate_observe',{
            'browser':'safari','url':'https://example.test/first'})
        self.assertIs(result['ok'],False)
        self.assertEqual('observation',result['failure_stage'])
        self.assertEqual('observation_failed',result['error_code'])
        self.assertIn(result['session_id'],
                      [x['session_id'] for x in self.a.call('rdc_browser_list',{})['sessions']])
        self.assertEqual(1,sum(path.endswith('/url') and method=='POST'
                               for method,path,_ in Driver.requests))

    def test_pointer_requires_observation_and_updates_preview_cursor(self):
        sid=self.start()
        initial=self.a.call('rdc_browser_list',{})['sessions'][0]['cursor']
        self.assertIs(initial.get('visible'),False)
        obs=self.a.call('rdc_browser_observe',{'session_id':sid})
        self.a.call('rdc_browser_pointer',{'session_id':sid,'observation_id':obs['observation_id'],'x':41,'y':52,'action':'move'})
        shot=self.a.snapshot(sid)
        self.assertEqual({'x':41,'y':52,'visible':True},shot['cursor'])
        self.assertEqual(b'\x89PNG\r\n\x1a\nfixture',base64.b64decode(shot['data']))
        with self.assertRaises(Exception): self.a.call('rdc_browser_pointer',{'session_id':sid,'observation_id':obs['observation_id'],'x':9000,'y':5})
    def test_webdriver_click_hides_old_marker_when_driver_does_not_report_click_position(self):
        sid=self.start()
        observation=self.a.call('rdc_browser_observe',{'session_id':sid})
        moved=self.a.call('rdc_browser_pointer',{'session_id':sid,
            'observation_id':observation['observation_id'],'x':41,'y':52,'action':'move'})
        self.assertTrue(moved['cursor']['visible'])
        observation=self.a.call('rdc_browser_observe',{'session_id':sid})
        clicked=self.a.call('rdc_browser_click',{'session_id':sid,
            'observation_id':observation['observation_id'],
            'handle':observation['controls'][0]['handle']})
        self.assertEqual(sid,clicked['session_id'])
        self.assertIs(self.a.snapshot(sid)['cursor']['visible'],False,
            'An unlocated WebDriver click must clear the previously visible marker')

    def test_driver_config_cannot_be_overridden_and_sessions_bound(self):
        with self.assertRaises(Exception): self.a.call('rdc_browser_start',{'browser':'safari','webdriver_url':'http://attacker/'})
        for _ in range(8): self.start()
        with self.assertRaises(Exception): self.start()
    def test_configured_safari_is_actual_webdriver_not_webkit_alias(self):
        sid=self.start(); self.assertEqual('safari',self.a.call('rdc_browser_list',{})['sessions'][0]['browser'])
        self.assertEqual({'capabilities':{'alwaysMatch':{'browserName':'safari'}}},Driver.requests[0][2])
        with self.assertRaises(Exception): self.a.call('rdc_browser_start',{'browser':'webkit'})
    def test_webdriver_setup_failure_closes_created_session(self):
        Driver.fail_timeouts=True
        with self.assertRaises(Exception): self.start()
        self.assertEqual(set(),Driver.active_sessions,'A failed setup must release its already-created driver session')
        self.assertEqual([],self.a.call('rdc_browser_list',{})['sessions'])
        self.assertIn(('DELETE','/session/safe-session',{}),Driver.requests)
    def test_failed_setup_cleanup_retains_session_for_explicit_close(self):
        Driver.fail_timeouts=True; Driver.fail_deletes=1
        with self.assertRaises(Exception) as error: self.start()
        self.assertEqual('webdriver_cleanup_required',getattr(error.exception,'code',None))
        sessions=self.a.call('rdc_browser_list',{})['sessions']
        self.assertEqual(1,len(sessions),'A driver session with uncertain cleanup must stay discoverable')
        self.assertEqual('cleanup_required',sessions[0]['setup_status'])
        sid=sessions[0]['session_id']
        requests_before=len(Driver.requests)
        with self.assertRaises(Exception) as blocked:
            self.a.call('rdc_browser_navigate',{'session_id':sid,'url':'https://example.test/'})
        self.assertEqual('webdriver_cleanup_required',getattr(blocked.exception,'code',None))
        self.assertEqual(requests_before,len(Driver.requests),'An uninitialized session must accept cleanup only')
        self.assertTrue(self.a.call('rdc_browser_close',{'session_id':sid})['closed'])
        self.assertEqual(set(),Driver.active_sessions)
        self.assertEqual([],self.a.call('rdc_browser_list',{})['sessions'])
    def test_malformed_created_session_metadata_is_cleaned_up(self):
        Driver.malformed_capabilities=True
        with self.assertRaises(Exception): self.start()
        self.assertEqual(set(),Driver.active_sessions)
        self.assertEqual([],self.a.call('rdc_browser_list',{})['sessions'])
    def test_driver_error_response_is_closed(self):
        stream=io.BytesIO(b'{"value":{"error":"unknown error","message":"Synthetic driver failure"}}')
        error=urllib.error.HTTPError('http://fixture.test/session',500,'Synthetic failure',{},stream)
        def reject(*args,**kwargs): raise error
        with patch('rdc.adapters.urllib.request.build_opener',return_value=SimpleNamespace(open=reject)):
            with self.assertRaises(Exception): self.start()
        self.assertTrue(stream.closed,'A rejected driver response must release its HTTP stream')
    def test_disabled_browser_backend_cannot_start_configured_driver(self):
        self.a.settings.browser_backend="disabled"
        with self.assertRaisesRegex(Exception,"[Dd]isabled"): self.start()

    def test_disabled_native_and_unconfigured_android_fail_without_input(self):
        with self.assertRaises(Exception): self.a.call('rdc_desktop_pointer',{'x':1,'y':2,'action':'click'})
        with self.assertRaises(Exception): self.a.call('rdc_android_tap',{'x':1,'y':2})
    def test_native_permission_loss_is_a_bounded_adapter_error(self):
        import sys
        a=Adapters(settings(desktop_mode='shared'))
        try:
            gui=SimpleNamespace(screenshot=lambda: (_ for _ in ()).throw(PermissionError('screen denied')))
            with patch.dict(sys.modules, {'pyautogui':gui}):
                with self.assertRaises(Exception) as result: a.call('rdc_desktop_screenshot',{})
                self.assertEqual('adapter_error',getattr(result.exception,'code',None))
                self.assertNotIn('Traceback',str(result.exception))
        finally:a.close()
    def test_webdriver_does_not_claim_independent_desktop_or_profile(self):
        self.assertFalse(self.a.status()['browser']['independent_input'])
        self.assertIn('configured driver',self.a.status()['browser']['profile_isolation'])

    def test_adb_uses_only_authorized_serial_and_argument_vectors(self):
        a=Adapters(settings(adb_serial='owner-device'))
        try:
            with patch('rdc.adapters.subprocess.run') as run:
                run.return_value=SimpleNamespace(returncode=0,stdout=b'copied',stderr=b'')
                a.call('rdc_android_input',{'text':'hello world'})
                self.assertEqual(['adb','-s','owner-device','shell','input','text','hello%sworld'],run.call_args.args[0])
                with self.assertRaises(Exception): a.call('rdc_android_input',{'text':'$(reboot)'})
                with self.assertRaises(Exception): a.call('rdc_android_tap',{'x':1,'y':2,'serial':'other-device'})
        finally: a.close()


class RealPlaywrightTests(unittest.TestCase):
    def setUp(self):
        if os.path.exists('/usr/bin/chromium'):
            self.patch=patch.dict(os.environ, {'RDC_CHROMIUM_EXECUTABLE':'/usr/bin/chromium'})
            self.patch.start();self.addCleanup(self.patch.stop)
    def test_isolated_browser_across_caller_threads(self):
        self.assertIsNotNone(Adapters)
        a=Adapters(settings(browser_backend='playwright'))
        try:
            try: sid=a.call('rdc_browser_start',{})['session_id']
            except Exception as exc:
                if not os.environ.get('RDC_CHROMIUM_EXECUTABLE') and ('Executable doesn' in str(exc) or 'playwright install' in str(exc) or 'not installed' in str(exc)): self.skipTest(str(exc))
                if 'Operation not permitted' in str(exc) and 'socket() failed' in str(exc): self.skipTest('Host sandbox forbids Chromium singleton sockets; real browser launch unverified here')
                raise
            fixture="data:text/html,<title>RDC Fixture</title><label>Name<input aria-label='Name'></label><button onclick=\"document.querySelector('p').textContent=document.querySelector('input').value\">Save</button><p>Waiting</p>"
            with ThreadPoolExecutor(max_workers=2) as pool:
                pool.submit(a.call,'rdc_browser_navigate',{'session_id':sid,'url':fixture}).result()
                obs=pool.submit(a.call,'rdc_browser_observe',{'session_id':sid}).result()
                field=next(c for c in obs['controls'] if c['tag']=='input')
                pool.submit(a.call,'rdc_browser_fill',{'session_id':sid,'observation_id':obs['observation_id'],'handle':field['handle'],'text':'Saved by RDC'}).result()
                with self.assertRaises(Exception): a.call('rdc_browser_click',{'session_id':sid,'observation_id':obs['observation_id'],'handle':field['handle']})
                obs=a.call('rdc_browser_observe',{'session_id':sid}); button=next(c for c in obs['controls'] if c['tag']=='button')
                a.call('rdc_browser_click',{'session_id':sid,'observation_id':obs['observation_id'],'handle':button['handle']})
                self.assertIn('Saved by RDC',a.call('rdc_browser_observe',{'session_id':sid})['text'])
                shot=pool.submit(a.snapshot,sid).result()
                self.assertTrue(base64.b64decode(shot['data']).startswith(b'\xff\xd8'))
                self.assertGreater(shot['cursor']['x'], 0, 'Semantic clicks must move the preview cursor')
                self.assertGreater(shot['cursor']['y'], 0)
            a.call('rdc_browser_close',{'session_id':sid});self.assertEqual([],a.call('rdc_browser_list',{})['sessions'])
        finally: a.close()
