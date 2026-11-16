"""Native adapter contracts against a synthetic Appium HTTP server and ADB.

These fixtures exercise RDC, never a real phone, tablet, driver, or vault.
"""
import base64
import io
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import patch

from rdc.adapters import Adapters
from rdc.config import Settings
from rdc.engine import Engine
from rdc.errors import RDCError

try:
    from rdc.mobile import Mobile, validate_mobile_profiles
except ImportError:
    Mobile = validate_mobile_profiles = None


ANDROID_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0"><android.widget.FrameLayout class="android.widget.FrameLayout" bounds="[0,0][400,800]" displayed="true">
  <android.widget.TextView class="android.widget.TextView" text="Example" bounds="[10,10][200,50]" displayed="true" enabled="true" />
  <android.widget.EditText class="android.widget.EditText" text="PRIVATE_INPUT_VALUE" content-desc="PRIVATE_INPUT_VALUE" password="false" bounds="[10,60][300,110]" displayed="true" enabled="true" />
  <android.widget.Button class="android.widget.Button" text="Save" clickable="true" password="false" bounds="[10,130][100,180]" displayed="true" enabled="true" />
</android.widget.FrameLayout></hierarchy>'''
IOS_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<AppiumAUT><XCUIElementTypeApplication type="XCUIElementTypeApplication" name="Example" enabled="true" visible="true" x="0" y="0" width="400" height="800">
  <XCUIElementTypeStaticText type="XCUIElementTypeStaticText" label="Example" name="Example" value="PRIVATE_STATIC_VALUE" enabled="true" visible="true" x="10" y="10" width="200" height="40" />
  <XCUIElementTypeTextField type="XCUIElementTypeTextField" name="PRIVATE_INPUT_VALUE" label="PRIVATE_INPUT_VALUE" value="PRIVATE_INPUT_VALUE" enabled="true" visible="true" x="10" y="60" width="300" height="50" />
  <XCUIElementTypeButton type="XCUIElementTypeButton" label="Save" name="Save" enabled="true" visible="true" x="10" y="130" width="100" height="50" />
</XCUIElementTypeApplication></AppiumAUT>'''


def png(width=800, height=1600):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress((b'\0' + b'\xff\xff\xff' * width) * height)) + chunk(b'IEND', b''))


def settings(**changes):
    return SimpleNamespace(**({'mobile_profiles': {}, 'adb_serial': None,
        'desktop_mode': 'disabled', 'browser_backend': 'disabled',
        'webdriver_url': None, 'webdriver_capabilities': None} | changes))


class NativeDriver(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self): self.respond('GET')
    def do_POST(self): self.respond('POST')
    def do_DELETE(self): self.respond('DELETE')

    def respond(self, method):
        state = self.server.state
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
        path = self.path.removeprefix('/wd/hub')
        state.requests.append((method, path, body))
        if state.expired and path.startswith('/session/'):
            self.reply({'error':'invalid session id','message':'PRIVATE_EXPIRED_DETAILS'},404)
            return
        failed = path.endswith('/timeouts') and state.fail_setup
        if method == 'DELETE' and path.count('/') == 2 and state.fail_delete:
            state.fail_delete -= 1
            failed = True
        if state.fail_path and path.endswith(state.fail_path):
            failed = True
        if failed:
            self.reply({'error': 'unknown error', 'message': 'PRIVATE_DRIVER_ERROR ' + json.dumps(body)}, 500)
            return
        value = None
        if path == '/session' and method == 'POST':
            state.created += 1
            driver_id = 'native-driver-' + str(state.created)
            state.active.add(driver_id)
            value = {'sessionId': driver_id,
                     'capabilities': None if state.malformed_caps else body['capabilities']['alwaysMatch']}
        elif method == 'DELETE' and path.count('/') == 2:
            state.active.discard(path.split('/')[-1])
        elif path.endswith('/context'):
            value = state.context
        elif path.endswith('/window/rect'):
            value = state.rect
        elif path.endswith('/source'):
            value = state.sources.pop(0) if state.sources else state.source
        elif path.endswith('/element'):
            value = {'element-6066-11e4-a52e-4f735466cecf': 'native-element'}
        elif path.endswith('/screenshot'):
            value = state.screenshot
        self.reply(value)

    def reply(self, value, status=200):
        data = json.dumps({'value': value}).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class MobileTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(Mobile, 'The native Mobile adapter is required')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), NativeDriver)
        self.server.state = SimpleNamespace(requests=[], created=0, active=set(), fail_setup=False, expired=False,
            fail_delete=0, fail_path=None, malformed_caps=False, context='NATIVE_APP',
            rect={'x': 0, 'y': 0, 'width': 400, 'height': 800}, source=ANDROID_XML,
            sources=[], screenshot=base64.b64encode(png()).decode())
        self.driver = self.server.state
        self.thread = threading.Thread(target=lambda:self.server.serve_forever(poll_interval=.01), daemon=True)
        self.thread.start()
        self.endpoint = 'http://127.0.0.1:' + str(self.server.server_port) + '/wd/hub'
        self.profiles = {'phone': {'platformName': 'Android', 'automationName': 'UiAutomator2',
            'endpoint': self.endpoint, 'capabilities': {'appium:udid': 'PRIVATE_DEVICE_ID',
            'appium:appPackage': 'test.example', 'appium:appActivity': '.MainActivity', 'appium:noReset': True}}}
        self.mobile = Mobile(settings(mobile_profiles=self.profiles))

    def tearDown(self):
        if hasattr(self, 'mobile'):
            self.mobile.close()
        if hasattr(self, 'server'):
            self.server.shutdown()
            self.server.server_close()
            self.thread.join()

    def start(self):
        return self.mobile.call('rdc_mobile_start', {'profile': 'phone'})['session_id']

    def observe(self, sid):
        self.assertTrue(hasattr(self.mobile, '_observe'), 'Native observation must be implemented')
        return self.mobile.call('rdc_mobile_observe', {'session_id': sid})

    def snapshot(self, sid):
        self.assertTrue(hasattr(self.mobile, 'snapshot'), 'Native screenshot privacy must be implemented')
        return self.mobile.snapshot(sid)

    def test_start_uses_owner_profile_and_public_status_redacts_private_configuration(self):
        sid = self.start()
        self.assertRegex(sid, r'^mobile-[0-9a-f-]{36}$')
        self.assertEqual(('POST', '/session', {'capabilities': {'alwaysMatch': {
            'platformName': 'Android', 'appium:automationName': 'UiAutomator2',
            'appium:udid': 'PRIVATE_DEVICE_ID', 'appium:appPackage': 'test.example',
            'appium:appActivity': '.MainActivity', 'appium:noReset': True,
            'appium:newCommandTimeout': 120}}}), self.driver.requests[0])
        status = self.mobile.status()
        self.assertEqual([{'profile': 'phone', 'platform': 'Android', 'automation': 'UiAutomator2'}], status['profiles'])
        self.assertFalse(status['independent_input'])
        self.assertEqual((400, 800), (status['sessions'][0]['width'], status['sessions'][0]['height']))
        self.assertNotIn('PRIVATE_DEVICE_ID', json.dumps(status))
        self.assertNotIn(self.endpoint, json.dumps(status))
        self.assertNotIn('native-driver-', json.dumps(status))

    def test_status_list_and_browser_preview_remain_readable_during_mobile_start(self):
        entered, release, reads_done = threading.Event(), threading.Event(), threading.Event()
        results, errors, threads = {}, [], []
        browser_id = '12345678-1234-1234-1234-123456789abc'
        browser = {'session_id':browser_id,'browser':'chromium','width':800,'height':600}
        with tempfile.TemporaryDirectory() as temporary:
            engine = Engine(Settings(state_dir=Path(temporary)/'state', roots=[Path(temporary)],
                browser_backend='disabled', mobile_profiles=self.profiles))
            original_http = engine.adapters.mobile._http
            def gated_http(profile, method, path, body=None, timeout=35):
                if method == 'POST' and path == '/session':
                    entered.set()
                    if not release.wait(10): raise RuntimeError('Fixture driver gate timed out')
                return original_http(profile, method, path, body, timeout)
            def start():
                try: results['start'] = engine.owner_call('rdc_mobile_start', {'profile':'phone'})
                except Exception as exc: errors.append(exc)
            def read():
                try:
                    results['status'] = engine.status()['adapters']['mobile']
                    results['list'] = engine.call('rdc_mobile_list', {})
                    results['preview'] = engine.call('rdc_preview_open', {'session_id':browser_id})
                except Exception as exc: errors.append(exc)
                finally: reads_done.set()
            try:
                # The synthetic browser owner also publishes its current metadata,
                # as real browser work does before preview reads the cached view.
                engine.adapters._publish_browser_status(SimpleNamespace(status=lambda:{'sessions':[browser]}),busy=False)
                with patch.object(engine.adapters.mobile, '_http', side_effect=gated_http), \
                        patch.object(engine.adapters, '_browser', return_value={'sessions':[browser]}):
                    threads.append(threading.Thread(target=start)); threads[-1].start()
                    self.assertTrue(entered.wait(5), 'The native request must begin before timing status reads')
                    threads.append(threading.Thread(target=read)); threads[-1].start()
                    self.assertTrue(reads_done.wait(2), 'Status/list/browser preview waited on native driver I/O')
                    self.assertEqual([], errors)
                    for status in (results['status'], results['list']):
                        self.assertTrue(status['busy'])
                        self.assertTrue(status['status_stale'])
                        self.assertEqual([], status['sessions'])
                        self.assertNotIn('PRIVATE_DEVICE_ID', json.dumps(status))
                        self.assertNotIn(self.endpoint, json.dumps(status))
                    self.assertEqual(browser_id, results['preview']['session_id'])
                    self.assertEqual([browser_id], [s['session_id'] for s in results['preview']['sessions']])
                    self.assertEqual([], self.driver.requests, 'Status reads must not start another native request')
                    release.set()
                    for thread in threads: thread.join(5)
                self.assertTrue(all(not thread.is_alive() for thread in threads))
                self.assertTrue(results['start']['ok'], results['start'])
                final = engine.call('rdc_mobile_list', {})
                self.assertFalse(final['busy'])
                self.assertFalse(final['status_stale'])
                self.assertEqual(results['start']['session_id'], final['sessions'][0]['session_id'])
                self.assertEqual(1, self.driver.created)
            finally:
                release.set()
                for thread in threads: thread.join(5)
                engine.close()

    def test_status_snapshot_is_copied_and_tracks_failed_cleanup_and_shutdown(self):
        sid = self.start()
        observed = self.observe(sid)
        cached = self.mobile.status()
        self.assertFalse(cached['busy'])
        self.assertFalse(cached['status_stale'])
        self.assertIsInstance(cached['updated_at'], float)
        copied = self.mobile.call('rdc_mobile_list', {})
        copied['profiles'][0]['profile'] = 'changed-copy'
        copied['sessions'][0]['session_id'] = 'changed-copy'
        copied['sessions'][0]['cursor']['x'] = -999
        self.assertEqual(cached, self.mobile.status())
        self.assertEqual(observed['observation_id'], self.mobile.status()['sessions'][0]['observation_id'])
        self.driver.fail_delete = 1
        with self.assertRaises(RDCError) as error:
            self.mobile.call('rdc_mobile_close', {'session_id':sid})
        self.assertEqual('mobile_cleanup_required', error.exception.code)
        failed = self.mobile.status()
        self.assertFalse(failed['busy'])
        self.assertFalse(failed['status_stale'])
        self.assertEqual(sid, failed['sessions'][0]['session_id'])
        self.assertIsNone(failed['sessions'][0]['observation_id'])
        self.assertEqual('cleanup_required', failed['sessions'][0]['setup_status'])
        self.mobile.call('rdc_mobile_close', {'session_id':sid})
        self.assertEqual([], self.mobile.status()['sessions'])
        self.mobile.close()
        self.assertTrue(self.mobile.status()['closed'])
        self.assertEqual([], self.mobile.status()['sessions'])
        with self.assertRaises(RDCError) as error: self.mobile.call('rdc_mobile_list', {})
        self.assertEqual('closed', error.exception.code)

    def test_snapshot_status_is_nonblocking_while_native_input_stays_serialized(self):
        sid = self.start()
        observed = self.observe(sid)
        button = next(control for control in observed['controls'] if control['name']=='Save')
        entered, release, read_done, input_started, input_done = (threading.Event() for _ in range(5))
        results, errors, threads = {}, [], []
        original_wd = self.mobile._wd
        def gated_wd(session, method, path, body=None):
            if method=='GET' and path=='/screenshot':
                entered.set()
                if not release.wait(10): raise RuntimeError('Fixture capture gate timed out')
            return original_wd(session, method, path, body)
        def capture():
            try: results['frame'] = self.snapshot(sid)
            except Exception as exc: errors.append(exc)
        def read():
            try: results['status'] = self.mobile.status()
            except Exception as exc: errors.append(exc)
            finally: read_done.set()
        def tap():
            input_started.set()
            try: results['tap'] = self.mobile.call('rdc_mobile_tap', {'session_id':sid,
                'observation_id':observed['observation_id'],'handle':button['handle']})
            except Exception as exc: errors.append(exc)
            finally: input_done.set()
        try:
            with patch.object(self.mobile, '_wd', side_effect=gated_wd):
                threads.append(threading.Thread(target=capture)); threads[-1].start()
                self.assertTrue(entered.wait(5))
                threads.append(threading.Thread(target=read)); threads[-1].start()
                self.assertTrue(read_done.wait(2), 'A direct preview capture blocked status')
                self.assertTrue(results['status']['busy'])
                self.assertTrue(results['status']['status_stale'])
                self.assertEqual(sid, results['status']['sessions'][0]['session_id'])
                self.assertEqual(observed['observation_id'], results['status']['sessions'][0]['observation_id'])
                threads.append(threading.Thread(target=tap)); threads[-1].start()
                self.assertTrue(input_started.wait(2))
                self.assertFalse(input_done.wait(.1), 'Native input crossed an in-flight capture')
                self.assertFalse(any(path.endswith('/click') for _,path,_ in self.driver.requests))
                release.set()
                for thread in threads: thread.join(5)
            self.assertTrue(all(not thread.is_alive() for thread in threads))
            self.assertEqual([], errors)
            self.assertEqual(sid, results['frame']['session_id'])
            self.assertEqual('tap', results['tap']['performed'])
            self.assertEqual(1, sum(path.endswith('/click') for _,path,_ in self.driver.requests))
            final = self.mobile.status()
            self.assertFalse(final['busy'])
            self.assertFalse(final['status_stale'])
            self.assertIsNone(final['sessions'][0]['observation_id'])
        finally:
            release.set()
            for thread in threads: thread.join(5)

    def test_agent_cannot_override_endpoint_capabilities_or_choose_unknown_profile(self):
        for extra in ({'endpoint':'http://other/'}, {'capabilities':{}}, {'script':'return true'}):
            with self.assertRaises(RDCError):
                self.mobile.call('rdc_mobile_start', {'profile': 'phone', **extra})
        with self.assertRaises(RDCError):
            self.mobile.call('rdc_mobile_start', {'profile': 'unknown'})
        self.assertEqual([], self.driver.requests)

    def test_one_session_per_profile_and_close_releases_exact_driver(self):
        sid = self.start()
        with self.assertRaises(RDCError): self.start()
        self.assertEqual(1, self.driver.created)
        self.assertTrue(self.mobile.call('rdc_mobile_close', {'session_id':sid})['closed'])
        self.assertEqual(set(), self.driver.active)
        self.assertEqual([], self.mobile.call('rdc_mobile_list', {})['sessions'])
        self.assertIn(('DELETE', '/session/native-driver-1', {}), self.driver.requests)

    def test_setup_failure_releases_already_created_session(self):
        self.driver.fail_setup = True
        with self.assertRaises(RDCError) as error: self.start()
        self.assertNotIn('PRIVATE_DRIVER_ERROR', str(error.exception))
        self.assertEqual(set(), self.driver.active)
        self.assertEqual([], self.mobile.status()['sessions'])

    def test_failed_cleanup_retains_session_and_blocks_profile_until_explicit_close(self):
        self.driver.fail_setup = True
        self.driver.fail_delete = 1
        with self.assertRaises(RDCError) as error: self.start()
        self.assertEqual('mobile_cleanup_required', error.exception.code)
        session = self.mobile.status()['sessions'][0]
        self.assertEqual('cleanup_required', session['setup_status'])
        before = len(self.driver.requests)
        with self.assertRaises(RDCError): self.observe(session['session_id'])
        with self.assertRaises(RDCError): self.start()
        self.assertEqual(before, len(self.driver.requests))
        self.mobile.call('rdc_mobile_close', {'session_id': session['session_id']})
        self.assertEqual(set(), self.driver.active)

    def test_non_native_context_and_malformed_capabilities_are_cleaned_up(self):
        self.driver.context = 'WEBVIEW_test'
        with self.assertRaises(RDCError): self.start()
        self.assertEqual(set(), self.driver.active)
        self.driver.context = 'NATIVE_APP'
        self.driver.malformed_caps = True
        with self.assertRaises(RDCError): self.start()
        self.assertEqual(set(), self.driver.active)

    def test_unsafe_profiles_fail_without_exposing_configuration_or_network_requests(self):
        bad = [
            {'endpoint': 'http://example.test:4723'}, {'endpoint': 'https://name:PRIVATE_PASSWORD@example.test'},
            {'endpoint': self.endpoint + '?PRIVATE_QUERY'}, {'endpoint': self.endpoint + '#fragment'},
            {'platformName':'iOS'}, {'automationName':'OtherDriver'},
            {'capabilities':{'platformName':'iOS'}},
            {'capabilities':{'appium:options':{'automationName':'OtherDriver'}}},
            {'capabilities':{'browserName':'Safari'}},
            {'capabilities':{'appium:autoAcceptAlerts':True}},
            {'capabilities':{'appium:autoGrantPermissions':True}},
            {'capabilities':{'autoAcceptAlerts':True}},
            {'capabilities':{'appium:platformName':'iOS'}},
            {'capabilities':{}},
            {'capabilities':{'appium:udid':'OWNER_DEVICE','unhandledPromptBehavior':'accept'}},
        ]
        for change in bad:
            with self.subTest(change=list(change)):
                with self.assertRaises(RDCError) as error:
                    validate_mobile_profiles({'phone': self.profiles['phone'] | change})
                self.assertEqual('invalid_config', error.exception.code)
                self.assertNotIn('PRIVATE_', str(error.exception))
        self.assertEqual([], self.driver.requests)

    def test_ios_and_ipad_profiles_use_xcuitest_pair(self):
        validate_mobile_profiles({'tablet': {'platformName':'iOS', 'automationName':'XCUITest',
            'endpoint':'http://localhost:4723', 'capabilities':{'appium:udid':'OWNER_IPAD',
            'appium:bundleId':'test.example', 'appium:noReset':True}}})

    def test_observe_android_and_ios_redacts_all_editable_values_and_bounds_handles(self):
        sid = self.start()
        observed = self.observe(sid)
        self.assertIn('Example', observed['text'])
        self.assertNotIn('PRIVATE_INPUT_VALUE', json.dumps(observed))
        self.assertNotIn('<?xml', json.dumps(observed))
        fields = [c for c in observed['controls'] if c['editable']]
        self.assertEqual(1, len(fields))
        self.assertEqual('Text field', fields[0]['name'])
        self.assertEqual('[redacted]', fields[0]['value'])
        self.assertTrue(fields[0]['can_fill'])
        self.assertEqual({'x':10,'y':60,'width':290,'height':50}, fields[0]['bounds'])
        self.mobile.call('rdc_mobile_close', {'session_id':sid})
        self.profiles['phone'].update(platformName='iOS', automationName='XCUITest')
        self.mobile.close()
        self.mobile = Mobile(settings(mobile_profiles=self.profiles))
        self.driver.source = IOS_XML
        observed = self.observe(self.start())
        self.assertIn('Example', observed['text'])
        self.assertNotIn('PRIVATE_', json.dumps(observed))
        self.assertTrue(any(c['name'] == 'Save' for c in observed['controls']))

    def test_android_private_field_descendants_do_not_export_labels_or_handles(self):
        sid = self.start()
        for secure in (False, True):
            with self.subTest(secure=secure):
                self.driver.source = '''<hierarchy><node class="android.widget.FrameLayout" content-desc="PRIVATE_AGGREGATE" bounds="[0,0][400,800]">
                  <node class="android.widget.TextView" text="Public sibling" bounds="[10,10][200,40]"/>
                  <node class="android.widget.EditText" text="PRIVATE_PARENT" password="%s" bounds="[10,60][300,110]">
                    <node class="android.widget.FrameLayout" content-desc="PRIVATE_CONTAINER" bounds="[10,60][300,110]">
                      <node class="android.widget.TextView" text="PRIVATE_STATIC_CHILD" bounds="[10,60][100,90]"/>
                      <node class="android.widget.Button" text="PRIVATE_BUTTON_CHILD" clickable="true" bounds="[100,60][200,90]"/>
                      <node class="android.widget.EditText" text="PRIVATE_EDITABLE_CHILD" password="false" bounds="[200,60][300,90]"/>
                    </node>
                  </node>
                  <node class="android.widget.Button" text="Save" clickable="true" bounds="[10,130][100,180]"/>
                </node></hierarchy>''' % str(secure).lower()
                observed = self.observe(sid)
                self.assertNotIn('PRIVATE_', json.dumps(observed))
                self.assertIn('Public sibling', observed['text'])
                self.assertIn('Save', observed['text'])
                self.assertEqual(['Secure field' if secure else 'Text field', 'Save'],
                                 [control['name'] for control in observed['controls']])
                field, save = observed['controls']
                self.assertEqual(not secure, field['can_fill'])
                self.assertEqual('[redacted]', field['value'])
                self.mobile.call('rdc_mobile_tap', {'session_id':sid,
                    'observation_id':observed['observation_id'],'handle':save['handle']})
                self.assertEqual(('POST','/session/native-driver-1/element',
                    {'using':'xpath','value':'/*[1]/*[1]/*[3]'}),
                    next(request for request in reversed(self.driver.requests) if request[1].endswith('/element')))

    def test_ios_private_field_descendants_do_not_export_labels_or_handles(self):
        self.mobile.close()
        self.profiles['phone'].update(platformName='iOS', automationName='XCUITest')
        self.mobile = Mobile(settings(mobile_profiles=self.profiles))
        sid = self.start()
        for kind in ('XCUIElementTypeTextField', 'XCUIElementTypeSecureTextField'):
            with self.subTest(kind=kind):
                self.driver.source = '''<AppiumAUT><XCUIElementTypeApplication label="PRIVATE_AGGREGATE" x="0" y="0" width="400" height="800">
                  <XCUIElementTypeStaticText label="Public sibling" x="10" y="10" width="190" height="30"/>
                  <%s label="PRIVATE_PARENT" value="PRIVATE_VALUE" x="10" y="60" width="290" height="50">
                    <XCUIElementTypeOther label="PRIVATE_CONTAINER" x="10" y="60" width="290" height="50">
                      <XCUIElementTypeStaticText label="PRIVATE_STATIC_CHILD" x="10" y="60" width="90" height="30"/>
                      <XCUIElementTypeButton label="PRIVATE_BUTTON_CHILD" x="100" y="60" width="100" height="30"/>
                      <XCUIElementTypeTextField label="PRIVATE_EDITABLE_CHILD" value="PRIVATE_CHILD_VALUE" x="200" y="60" width="100" height="30"/>
                    </XCUIElementTypeOther>
                  </%s>
                  <XCUIElementTypeButton label="Save" x="10" y="130" width="90" height="50"/>
                </XCUIElementTypeApplication></AppiumAUT>''' % (kind, kind)
                observed = self.observe(sid)
                self.assertNotIn('PRIVATE_', json.dumps(observed))
                self.assertIn('Public sibling', observed['text'])
                self.assertIn('Save', observed['text'])
                secure = kind == 'XCUIElementTypeSecureTextField'
                self.assertEqual(['Secure field' if secure else 'Text field', 'Save'],
                                 [control['name'] for control in observed['controls']])
                field, save = observed['controls']
                self.assertEqual(not secure, field['can_fill'])
                self.assertEqual('[redacted]', field['value'])
                self.mobile.call('rdc_mobile_tap', {'session_id':sid,
                    'observation_id':observed['observation_id'],'handle':save['handle']})
                self.assertEqual(('POST','/session/native-driver-1/element',
                    {'using':'xpath','value':'/*[1]/*[1]/*[3]'}),
                    next(request for request in reversed(self.driver.requests) if request[1].endswith('/element')))

    def test_native_tap_and_fill_use_internal_selector_then_invalidate_observation(self):
        sid = self.start()
        observed = self.observe(sid)
        field = next(c for c in observed['controls'] if c['can_fill'])
        args = {'session_id':sid,'observation_id':observed['observation_id'],'handle':field['handle'],'text':'sample text'}
        self.mobile.call('rdc_mobile_fill', args)
        self.assertIn(('POST','/session/native-driver-1/element',{'using':'xpath','value':'/*[1]/*[1]/*[2]'}), self.driver.requests)
        self.assertIn(('POST','/session/native-driver-1/element/native-element/clear',{}), self.driver.requests)
        self.assertIn(('POST','/session/native-driver-1/element/native-element/value',{'text':'sample text'}), self.driver.requests)
        before = len(self.driver.requests)
        with self.assertRaises(RDCError) as stale: self.mobile.call('rdc_mobile_fill', args)
        self.assertEqual('stale_observation', stale.exception.code)
        self.assertEqual(before, len(self.driver.requests))
        observed = self.observe(sid)
        button = next(c for c in observed['controls'] if c['name'] == 'Save')
        self.mobile.call('rdc_mobile_tap', {'session_id':sid,'observation_id':observed['observation_id'],'handle':button['handle']})
        self.assertIn(('POST','/session/native-driver-1/element/native-element/click',{}), self.driver.requests)

    def test_changed_native_tree_blocks_input_before_element_lookup(self):
        sid = self.start()
        observed = self.observe(sid)
        self.driver.source = ANDROID_XML.replace('Save', 'Delete')
        before = len(self.driver.requests)
        with self.assertRaises(RDCError) as error:
            self.mobile.call('rdc_mobile_tap', {'session_id':sid,'observation_id':observed['observation_id'],
                'handle':observed['controls'][0]['handle']})
        self.assertEqual('stale_observation', error.exception.code)
        self.assertFalse(any(method == 'POST' for method,_,_ in self.driver.requests[before:]))

    def test_secure_field_cannot_be_filled_and_revealing_it_does_not_enable_capture(self):
        sid = self.start()
        self.driver.source = ANDROID_XML.replace('password="false"', 'password="true"', 1)
        observed = self.observe(sid)
        field = next(c for c in observed['controls'] if c['secure'])
        self.assertFalse(field['can_fill'])
        self.assertEqual('Secure field', field['name'])
        self.assertNotIn('PRIVATE_INPUT_VALUE', json.dumps(observed))
        with self.assertRaises(RDCError) as error:
            self.mobile.call('rdc_mobile_fill', {'session_id':sid,'observation_id':observed['observation_id'],
                'handle':field['handle'],'text':'DO_NOT_SEND'})
        self.assertEqual('secure_input_required', error.exception.code)
        self.assertFalse(any('DO_NOT_SEND' in json.dumps(body) for _,_,body in self.driver.requests))
        self.driver.source = ANDROID_XML
        self.observe(sid)
        with self.assertRaises(RDCError) as screenshot: self.snapshot(sid)
        self.assertEqual('screenshot_redaction_required', screenshot.exception.code)
        self.assertFalse(any(path.endswith('/screenshot') for _,path,_ in self.driver.requests))

    def test_snapshot_probes_secure_fields_before_any_observe(self):
        sid = self.start()
        self.driver.source = ANDROID_XML.replace('password="false"', 'password="true"', 1)
        with self.assertRaises(RDCError) as error: self.snapshot(sid)
        self.assertEqual('screenshot_redaction_required', error.exception.code)
        self.assertFalse(any(path.endswith('/screenshot') for _,path,_ in self.driver.requests))

    def test_snapshot_returns_native_coordinate_scale_and_refuses_screen_changed_during_capture(self):
        sid = self.start()
        shot = self.snapshot(sid)
        self.assertEqual((400,800), (shot['width'],shot['height']))
        self.assertEqual((800,1600), (shot['source_width'],shot['source_height']))
        self.assertEqual((.5,.5), (shot['input_scale_x'],shot['input_scale_y']))
        self.assertEqual('native logical pixels', shot['coordinate_system'])
        self.assertEqual(png(), base64.b64decode(shot['data']))
        self.driver.sources = [ANDROID_XML, ANDROID_XML.replace('Save','Changed')]
        with self.assertRaises(RDCError) as error: self.snapshot(sid)
        self.assertEqual('screenshot_failed', error.exception.code)
        self.assertNotIn('PRIVATE_INPUT_VALUE', str(error.exception))

    def test_malformed_oversized_deep_or_entity_xml_fails_closed_before_capture(self):
        sid = self.start()
        malformed = [
            '<hierarchy><node', '<html><input value="PRIVATE_INPUT_VALUE"/></html>',
            '<!DOCTYPE hierarchy [<!ENTITY x "PRIVATE_INPUT_VALUE">]><hierarchy>&x;</hierarchy>',
            '<hierarchy>' + '<node class="android.widget.FrameLayout">' * 70 + '</node>' * 70 + '</hierarchy>',
            '<hierarchy>' + '<node class="android.widget.TextView"/>' * 5001 + '</hierarchy>',
            '<hierarchy>' + 'x' * (1024*1024) + '</hierarchy>',
        ]
        for source in malformed:
            self.driver.source = source
            with self.assertRaises(RDCError) as observation: self.observe(sid)
            self.assertEqual('observation_failed', observation.exception.code)
            with self.assertRaises(RDCError) as screenshot: self.snapshot(sid)
            self.assertEqual('screenshot_failed', screenshot.exception.code)
        self.assertFalse(any(path.endswith('/screenshot') for _,path,_ in self.driver.requests))

    def test_control_text_bounds_still_scan_late_secure_field(self):
        sid = self.start()
        nodes = ''.join('<node class="android.widget.Button" text="' + ('X'*300) + '" clickable="true" bounds="[0,0][20,20]"/>' for _ in range(180))
        self.driver.source = '<hierarchy>' + nodes + '<node class="android.widget.EditText" password="true" text="PRIVATE_LATE_SECRET" bounds="[0,0][20,20]"/></hierarchy>'
        observed = self.observe(sid)
        self.assertEqual(150, len(observed['controls']))
        self.assertTrue(observed['controls_truncated'])
        self.assertTrue(observed['text_truncated'])
        self.assertLessEqual(len(observed['text']), 24000)
        self.assertTrue(observed['controls'][0]['name_truncated'])
        self.assertEqual(240, len(observed['controls'][0]['name']))
        with self.assertRaises(RDCError) as screenshot: self.snapshot(sid)
        self.assertEqual('screenshot_redaction_required', screenshot.exception.code)

    def test_swipe_emits_touch_actions_and_never_replays_after_driver_failure(self):
        sid = self.start()
        observed = self.observe(sid)
        args = {'session_id':sid,'observation_id':observed['observation_id'],
            'start_x':100,'start_y':600,'end_x':100,'end_y':200,'duration_ms':450}
        self.mobile.call('rdc_mobile_swipe', args)
        actions = next(body['actions'] for method,path,body in self.driver.requests if method == 'POST' and path.endswith('/actions'))
        self.assertEqual([{'type':'pointer','id':'rdc-touch','parameters':{'pointerType':'touch'},'actions':[
            {'type':'pointerMove','duration':0,'origin':'viewport','x':100,'y':600},
            {'type':'pointerDown','button':0},{'type':'pause','duration':50},
            {'type':'pointerMove','duration':450,'origin':'viewport','x':100,'y':200},
            {'type':'pointerUp','button':0}]}], actions)
        observed = self.observe(sid)
        args['observation_id'] = observed['observation_id']
        self.driver.fail_path = '/actions'
        before = len(self.driver.requests)
        with self.assertRaises(RDCError) as error: self.mobile.call('rdc_mobile_swipe', args)
        self.assertNotIn('PRIVATE_DRIVER_ERROR', str(error.exception))
        failed = self.driver.requests[before:]
        self.assertEqual(1, sum(method=='POST' and path.endswith('/actions') for method,path,_ in failed))
        self.assertEqual(1, sum(method=='DELETE' and path.endswith('/actions') for method,path,_ in failed))

    def test_fill_failure_never_returns_driver_echo_or_retries_input(self):
        sid = self.start()
        observed = self.observe(sid)
        field = next(c for c in observed['controls'] if c['can_fill'])
        self.driver.fail_path = '/value'
        with self.assertRaises(RDCError) as error:
            self.mobile.call('rdc_mobile_fill', {'session_id':sid,'observation_id':observed['observation_id'],
                'handle':field['handle'],'text':'PRIVATE_SENT_TEXT'})
        self.assertNotIn('PRIVATE_', str(error.exception))
        self.assertEqual(1, sum(path.endswith('/value') for _,path,_ in self.driver.requests))
        self.assertIsNone(self.mobile.status()['sessions'][0]['observation_id'])

    def test_adapters_keep_mobile_out_of_browser_list_and_close_without_browser_thread(self):
        adapter = Adapters(settings(mobile_profiles=self.profiles))
        try:
            self.assertIn('rdc_mobile_start', {row['name'] for row in adapter.catalog()})
            started = adapter.call('rdc_mobile_start', {'profile':'phone'})
            self.assertTrue(started['session_id'].startswith('mobile-'))
            self.assertEqual([], adapter.call('rdc_browser_list', {})['sessions'])
            self.assertEqual(started['session_id'], adapter.status()['mobile']['sessions'][0]['session_id'])
            self.assertEqual(started['session_id'], adapter.snapshot(started['session_id'])['session_id'])
        finally:
            adapter.close()
        self.assertEqual(set(), self.driver.active)
        adapter = Adapters(settings(mobile_profiles=self.profiles))
        adapter.call('rdc_mobile_start', {'profile':'phone'})
        self.assertIsNone(adapter._thread)
        adapter.close()
        self.assertEqual(set(), self.driver.active)

    def test_expired_driver_session_can_be_closed_without_stranding_profile(self):
        sid = self.start()
        self.driver.active.clear()
        self.driver.expired = True
        with self.assertRaises(RDCError) as expired_observe: self.observe(sid)
        self.assertEqual('mobile_session_gone',expired_observe.exception.code)
        with self.assertRaises(RDCError) as expired_capture: self.snapshot(sid)
        self.assertEqual('mobile_session_gone',expired_capture.exception.code)
        self.assertTrue(self.mobile.call('rdc_mobile_close', {'session_id':sid})['closed'])
        self.assertEqual([],self.mobile.status()['sessions'])
        self.driver.expired = False
        self.assertNotEqual(sid,self.start())

    def test_creation_without_confirmed_id_stays_visible_and_cannot_be_blindly_retried(self):
        self.driver.fail_path = '/session'
        with self.assertRaises(RDCError) as failure: self.start()
        self.assertEqual('mobile_creation_unknown',failure.exception.code)
        self.assertNotIn('PRIVATE_',str(failure.exception))
        retained = self.mobile.status()['sessions'][0]
        self.assertEqual('creation_unknown',retained['setup_status'])
        before = len(self.driver.requests)
        with self.assertRaises(RDCError): self.start()
        with self.assertRaises(RDCError):
            self.mobile.call('rdc_mobile_close',{'session_id':retained['session_id']})
        self.assertEqual(before,len(self.driver.requests))

    def test_ios_secure_field_has_no_exported_labels_or_values_and_no_screenshot(self):
        self.mobile.close()
        self.profiles['phone'].update(platformName='iOS',automationName='XCUITest')
        self.mobile = Mobile(settings(mobile_profiles=self.profiles))
        self.driver.source = IOS_XML.replace('XCUIElementTypeTextField','XCUIElementTypeSecureTextField')
        sid = self.start()
        observed = self.observe(sid)
        secure = next(control for control in observed['controls'] if control['secure'])
        self.assertEqual(('Secure field','[redacted]',False),(secure['name'],secure['value'],secure['can_fill']))
        self.assertNotIn('PRIVATE_',json.dumps(observed))
        with self.assertRaises(RDCError) as failure: self.snapshot(sid)
        self.assertEqual('screenshot_redaction_required',failure.exception.code)

    def test_unknown_transport_exception_is_sanitized_before_leaving_adapter(self):
        sid = self.start()
        observed = self.observe(sid)
        button = next(c for c in observed['controls'] if c['name']=='Save')
        with patch('rdc.mobile.urllib.request.build_opener', side_effect=RuntimeError('PRIVATE_TRANSPORT_PAYLOAD')):
            with self.assertRaises(RDCError) as failure:
                self.mobile.call('rdc_mobile_tap',{'session_id':sid,'observation_id':observed['observation_id'],'handle':button['handle']})
        self.assertNotIn('PRIVATE_',str(failure.exception))

    def test_two_profile_aliases_cannot_start_competing_sessions_on_same_device(self):
        self.mobile.close()
        self.profiles['second_app'] = json.loads(json.dumps(self.profiles['phone']))
        self.profiles['second_app']['capabilities']['appium:appPackage'] = 'test.another'
        self.mobile = Mobile(settings(mobile_profiles=self.profiles))
        self.start()
        with self.assertRaises(RDCError) as failure:
            self.mobile.call('rdc_mobile_start',{'profile':'second_app'})
        self.assertEqual('profile_in_use',failure.exception.code)
        self.assertEqual(1,self.driver.created)


class AndroidTests(unittest.TestCase):
    def setUp(self):
        self.adapter = Adapters(settings(adb_serial='authorized-phone'))

    def tearDown(self):
        self.adapter.close()

    def test_swipe_long_press_and_launch_use_fixed_authorized_arguments(self):
        names = {tool['name'] for tool in self.adapter.catalog()}
        self.assertTrue({'rdc_android_swipe','rdc_android_long_press','rdc_android_launch_app'} <= names)
        with patch('rdc.adapters.subprocess.run', return_value=SimpleNamespace(returncode=0,stdout=b'',stderr=b'')) as run:
            self.adapter.call('rdc_android_swipe', {'start_x':10,'start_y':700,'end_x':10,'end_y':200,'duration_ms':400})
            self.assertEqual(['adb','-s','authorized-phone','shell','input','swipe','10','700','10','200','400'], run.call_args.args[0])
            self.assertEqual(subprocess.DEVNULL, run.call_args.kwargs.get('stdin'), 'ADB must never consume worker/MCP stdin')
            self.adapter.call('rdc_android_long_press', {'x':90,'y':80,'duration_ms':900})
            self.assertEqual(['adb','-s','authorized-phone','shell','input','swipe','90','80','90','80','900'], run.call_args.args[0])
            self.adapter.call('rdc_android_launch_app', {'package':'org.example.app','activity':'.MainActivity'})
            self.assertEqual(['adb','-s','authorized-phone','shell','am','start','-n','org.example.app/.MainActivity'], run.call_args.args[0])
            before = run.call_count
            for name,args in [
                ('rdc_android_launch_app',{'package':'org.example.app;reboot','activity':'.Main'}),
                ('rdc_android_launch_app',{'package':'org.example.app','activity':'.$EVIL'}),
                ('rdc_android_swipe',{'start_x':1.5,'start_y':5,'end_x':4,'end_y':2}),
                ('rdc_android_long_press',{'x':1,'y':2,'duration_ms':10001}),
                ('rdc_android_tap',{'x':1,'y':2,'serial':'unapproved'}),
            ]:
                with self.assertRaises(RDCError): self.adapter.call(name,args)
            self.assertEqual(before,run.call_count)

    def test_adb_failure_and_success_never_export_device_command_output(self):
        with patch('rdc.adapters.subprocess.run') as run:
            run.return_value = SimpleNamespace(returncode=1,stdout=b'PRIVATE_STDOUT',stderr=b'PRIVATE_STDERR')
            with self.assertRaises(RDCError) as failure:
                self.adapter.call('rdc_android_input', {'text':'sample text'})
            self.assertNotIn('PRIVATE_', str(failure.exception))
            run.return_value = SimpleNamespace(returncode=0,stdout=b'PRIVATE_STDOUT',stderr=b'')
            result = self.adapter.call('rdc_android_input', {'text':'sample text'})
            self.assertNotIn('PRIVATE_', json.dumps(result))

    def test_adb_screenshot_checks_hierarchy_before_and_after_capture(self):
        calls = []
        def run(cmd, **kwargs):
            calls.append(cmd)
            if cmd[-2:] == ['screencap','-p']:
                raw = png(400,800)
            else:
                if cmd[3:6] != ['shell','-tt','-n']:
                    return SimpleNamespace(returncode=1,stdout=b'',stderr=b'No terminal for /dev/tty')
                raw = ANDROID_XML.encode() + b'\nUI hierchary dumped to: /dev/tty\n'
            return SimpleNamespace(returncode=0,stdout=raw,stderr=b'')
        with patch('rdc.adapters.subprocess.run', side_effect=run):
            shot = self.adapter.call('rdc_android_screenshot', {})
        self.assertEqual(png(400,800), base64.b64decode(shot['data']))
        self.assertEqual(2, sum('uiautomator' in cmd for cmd in calls))
        self.assertEqual(1, sum('screencap' in cmd for cmd in calls))
        self.assertEqual((400,800), (shot['width'],shot['height']))
        self.assertNotIn('PRIVATE_INPUT_VALUE',json.dumps({k:v for k,v in shot.items() if k!='data'}))

    def test_adb_secure_or_unverifiable_hierarchy_never_runs_screencap(self):
        with patch('rdc.adapters.subprocess.run') as run:
            run.return_value=SimpleNamespace(returncode=0,stdout=ANDROID_XML.replace('password="false"','password="true"',1).encode(),stderr=b'')
            with self.assertRaises(RDCError) as failure: self.adapter.call('rdc_android_screenshot', {})
            self.assertEqual('screenshot_redaction_required',failure.exception.code)
            self.assertFalse(any('screencap' in row.args[0] for row in run.call_args_list))
            run.reset_mock()
            run.return_value=SimpleNamespace(returncode=0,stdout=ANDROID_XML.encode(),stderr=b'')
            with self.assertRaises(RDCError): self.adapter.call('rdc_android_screenshot', {})
            self.assertEqual(0,run.call_count,'A known private ADB screen stays private for this worker')
        other = Adapters(settings(adb_serial='authorized-phone'))
        try:
            with patch('rdc.adapters.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=b'PRIVATE_BROKEN_TREE',stderr=b'')) as run:
                with self.assertRaises(RDCError) as failure: other.call('rdc_android_screenshot', {})
                self.assertEqual('screenshot_failed',failure.exception.code)
                self.assertNotIn('PRIVATE_',str(failure.exception))
                self.assertFalse(any('screencap' in row.args[0] for row in run.call_args_list))
        finally:
            other.close()

