"""Browser UI checks against a clearly test-only API fixture.

These prove dashboard behavior, not device/adapter compatibility. Real adapter
integration belongs to test_adapters.py and test_transport.py.
"""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse, parse_qs
import json
import shutil
import unittest

WEB = Path(__file__).resolve().parents[1] / 'rdc' / 'web'


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch(headless=True, executable_path=shutil.which('chromium'), args=['--no-sandbox'])
        except Exception as exc:
            cls.playwright.stop()
            raise unittest.SkipTest(f'Chromium unavailable: {exc}')

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.calls = []
        self.auth = []
        self.preview_requests = 0
        self.paused = False
        self.mobile_enabled = False
        self.mobile_started = False
        self.mobile_private = False
        self.mobile = {'session_id': 'mobile-87654321-4321-4321-4321-cba987654321',
            'kind': 'mobile', 'platform': 'Android', 'backend': 'appium', 'profile': 'fixture-phone',
            'title': 'fixture-phone', 'width': 390, 'height': 844,
            'input_notice': 'Input is shared with anyone using the configured device.'}
        fixture = self
        page = self.browser.new_page(viewport={'width': 900, 'height': 560})
        page.set_content('<style>body{font:28px sans-serif;background:#edf6f5;padding:50px}button{padding:12px}</style><h1>Adapter test workspace</h1><button>Continue</button>')
        self.png = page.screenshot()
        page.close()

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(WEB), **kwargs)
            def log_message(self, *args):
                pass
            def send_json(self, data, status=200):
                payload = json.dumps(data).encode()
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            def authorized(self):
                fixture.auth.append(self.headers.get('Authorization'))
                if fixture.auth[-1] != 'Bearer owner-test-secret':
                    self.send_json({'ok': False, 'error': {'message': 'Owner token required'}}, 401)
                    return False
                return True
            def do_GET(self):
                path = urlparse(self.path).path
                if not path.startswith('/api/'):
                    return super().do_GET()
                if not self.authorized():
                    return
                if path == '/api/status':
                    self.send_json({'ok': True, 'device_id': 'test-device', 'paused': fixture.paused,
                        'settings': {'desktop_mode': 'disabled', 'browser_backend': 'playwright'},
                        'adapters': {'browser': {'backend': 'playwright', 'sessions': [
                            {'session_id': 'session-test', 'url': 'https://example.test/', 'title': 'Test workspace', 'browser': 'chromium', 'width': 900, 'height': 560, 'cursor': {'x': 120, 'y': 90}}]}, 'desktop': {'mode': 'disabled'},
                            'mobile': {'available': fixture.mobile_enabled,
                                'profiles': [{'profile': 'fixture-phone', 'platform': 'Android', 'automation': 'UiAutomator2'}] if fixture.mobile_enabled else [],
                                'sessions': [fixture.mobile] if fixture.mobile_started else []}},
                        'jobs': [{'id': 'job-test', 'argv': ['python', 'fixture.py'], 'status': 'completed', 'exit_code': 0}, {'id': 'job-running', 'argv': ['python', 'worker.py'], 'status': 'running', 'exit_code': None}],
                        'approvals': [{'id': 'review-test', 'name': 'rdc_write_file', 'arguments': {'file_path': '/workspace/example.txt'}}]})
                elif path == '/api/preview':
                    fixture.preview_requests += 1
                    query = parse_qs(urlparse(self.path).query)
                    if fixture.mobile_private and query.get('session_id') == [fixture.mobile['session_id']]:
                        self.send_json({'ok': False, 'error': {'code': 'screenshot_redaction_required', 'message': 'Synthetic private device screen'}}, 409)
                        return
                    self.send_response(200)
                    self.send_header('Content-Type', 'image/png')
                    self.end_headers()
                    self.wfile.write(fixture.png)
                elif path == '/api/jobs/job-test/output':
                    query = parse_qs(urlparse(self.path).query)
                    fixture.calls.append(('output', query))
                    self.send_json({'ok': True, 'text': 'fixture output\n', 'offset': 0, 'next_offset': 15, 'complete': True})
                else:
                    self.send_json({'ok': False}, 404)
            def do_POST(self):
                if not self.authorized():
                    return
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                fixture.calls.append((self.path, data))
                if self.path == '/api/pause':
                    fixture.paused = data['paused']
                if self.path == '/api/call' and data['name'] == 'rdc_browser_observe':
                    self.send_json({'ok': True, 'session_id': 'session-test', 'observation_id': 'obs-test', 'width': 900, 'height': 560, 'cursor': {'x': 120, 'y': 90}, 'text': 'Test workspace', 'controls': [{'handle': 'control-test', 'tag': 'button', 'name': 'Continue'}]})
                elif self.path == '/api/call' and data['name'] == 'rdc_mobile_start':
                    fixture.mobile_started = True
                    self.send_json({'ok': True, **fixture.mobile})
                elif self.path == '/api/call' and data['name'] == 'rdc_mobile_observe':
                    self.send_json({'ok': True, **fixture.mobile, 'observation_id': 'mobile-observation',
                        'text': 'Synthetic native controls', 'controls': [
                            {'handle': 'native-text', 'name': 'Text field', 'type': 'text', 'editable': True, 'can_fill': True, 'value': '[redacted]'},
                            {'handle': 'native-secure', 'name': 'Secure field', 'type': 'password', 'secure': True, 'can_fill': False, 'value': '[redacted]'},
                            {'handle': 'native-button', 'name': 'Continue', 'type': 'button', 'can_tap': True}]})
                elif self.path == '/api/call' and data['name'] == 'rdc_mobile_close':
                    fixture.mobile_started = False
                    self.send_json({'ok': True, 'session_id': fixture.mobile['session_id'], 'closed': True})
                else:
                    self.send_json({'ok': True})

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.page = self.browser.new_page(viewport={'width': 1440, 'height': 1000})
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.goto(f'http://127.0.0.1:{self.server.server_port}')

    def tearDown(self):
        self.page.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def connect(self):
        self.page.get_by_label('Owner access token').fill('owner-test-secret')
        self.page.get_by_role('button', name='Connect', exact=True).click()
        self.page.get_by_text('Connected', exact=True).wait_for()

    def test_owner_control_preview_and_explicit_log_offset(self):
        self.connect()
        self.assertTrue(self.page.get_by_role('button', name='Start mobile', exact=True).is_disabled())
        self.page.get_by_role('img', name='Live browser workspace').wait_for()
        self.page.get_by_role('button', name='Pause agent input', exact=True).click()
        self.page.get_by_role('button', name='Resume agent input', exact=True).wait_for()
        self.page.get_by_role('button', name='Observe page', exact=True).click()
        self.page.get_by_role('button', name='Continue', exact=True).click()
        self.page.get_by_role('button', name='Approve', exact=True).click()
        self.page.get_by_role('button', name='View output', exact=True).first.click()
        self.page.get_by_text('fixture output', exact=False).wait_for()
        self.assertTrue(any(path == '/api/pause' and data == {'paused': True} for path, data in self.calls))
        self.assertTrue(any(path == '/api/decision' and data == {'request_id': 'review-test', 'approve': True} for path, data in self.calls))
        self.assertTrue(any(path == 'output' and data['offset'] == ['0'] for path, data in self.calls))
        with self.page.expect_response(lambda response: response.url.endswith('/api/call') and response.request.post_data_json.get('name') == 'rdc_job_cancel'):
            self.page.get_by_role('button', name='Cancel job', exact=True).click()
        self.assertTrue(any(path == '/api/call' and data == {'name': 'rdc_job_cancel', 'arguments': {'job_id': 'job-running'}} for path, data in self.calls))
        self.assertGreater(self.preview_requests, 0)
        self.assertEqual(self.page.evaluate('Object.keys(localStorage)'), [])
        self.assertNotIn('owner-test-secret', self.page.url)
        self.assertEqual(self.errors, [])
        out = WEB.parents[1] / 'test-results'
        out.mkdir(exist_ok=True)
        self.page.screenshot(path=str(out / 'dashboard-desktop.png'), full_page=True)

    def test_phone_layout_and_disconnect_clear_private_content(self):
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.connect()
        self.page.get_by_role('img', name='Live browser workspace').wait_for()
        self.assertFalse(self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
        out = WEB.parents[1] / 'test-results'
        out.mkdir(exist_ok=True)
        self.page.screenshot(path=str(out / 'dashboard-phone.png'), full_page=True)
        self.page.get_by_role('button', name='Disconnect', exact=True).click()
        self.page.get_by_text('Disconnected', exact=True).wait_for()
        self.assertEqual(self.page.get_by_label('Owner access token').input_value(), '')
        self.assertEqual(self.page.locator('#sessions').inner_text(), 'Connect to see workspace sessions.')
        self.assertEqual(self.errors, [])

    def test_configured_mobile_controls_and_private_preview(self):
        from playwright.sync_api import expect
        self.mobile_enabled = True
        self.connect()
        self.page.get_by_label('Configured mobile device').select_option('fixture-phone')
        self.page.get_by_role('button', name='Start mobile', exact=True).click()
        self.page.get_by_role('heading', name='Android · fixture-phone', exact=True).wait_for()
        self.assertTrue(self.page.locator('#navigate-form').is_hidden())
        self.assertTrue(self.page.locator('#keys-form').is_hidden())
        self.assertTrue(self.page.get_by_label('Owner control', exact=True).is_disabled())
        self.assertIn('shared', self.page.locator('#input-note').inner_text())
        self.page.get_by_role('button', name='Observe device', exact=True).click()
        self.page.get_by_text('Secure field', exact=True).wait_for()
        self.assertEqual(self.page.locator('#observation form').count(), 1)
        self.assertEqual(self.page.locator('#observation select').count(), 0)
        field = self.page.get_by_label('Text field', exact=True)
        self.assertEqual(field.input_value(), '')
        field.fill('Synthetic entry')
        self.page.locator('#observation').get_by_role('button', name='Fill', exact=True).click()
        expect(self.page.get_by_role('button', name='Observe device', exact=True)).to_be_enabled()
        self.page.locator('#observation').get_by_role('button', name='Continue', exact=True).click()
        expect(self.page.get_by_role('button', name='Observe device', exact=True)).to_be_enabled()
        self.page.get_by_role('button', name='Up', exact=True).click()
        expect(self.page.get_by_role('button', name='Observe device', exact=True)).to_be_enabled()
        self.mobile_private = True
        self.page.get_by_text('Privacy protected', exact=True).wait_for(timeout=10000)
        self.assertTrue(self.page.locator('#preview').is_hidden())
        self.assertEqual(self.page.locator('#connection-status').inner_text(), 'Connected')
        self.assertFalse(self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
        dispatched = [data for path, data in self.calls if path == '/api/call']
        self.assertIn({'name': 'rdc_mobile_start', 'arguments': {'profile': 'fixture-phone'}}, dispatched)
        for name in ('rdc_mobile_fill', 'rdc_mobile_tap', 'rdc_mobile_swipe'):
            action = next(data for data in dispatched if data['name'] == name)
            self.assertEqual(action['arguments']['session_id'], self.mobile['session_id'])
            self.assertEqual(action['arguments']['observation_id'], 'mobile-observation')
        self.assertFalse(any(data['name'].startswith('rdc_browser_') or data['name'] == 'rdc_credentials_request' for data in dispatched))
        self.assertEqual(self.errors, [])


if __name__ == '__main__':
    unittest.main()
