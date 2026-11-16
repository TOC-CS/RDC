"""Mobile configuration and engine integration, with no live device endpoint."""
import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rdc.config import Settings
from rdc.engine import Engine, tool

BROWSER = '12345678-1234-1234-1234-123456789abc'
MOBILE = 'mobile-87654321-4321-4321-4321-cba987654321'
OBSERVATION = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
PROFILES = {'fixture-phone': {'platformName': 'Android', 'automationName': 'UiAutomator2',
    'endpoint': 'http://127.0.0.1:4723',
    'capabilities': {'appium:deviceName': 'Fixture phone', 'appium:udid': 'private-fixture-device'}}}


class CombinedAdapters:
    def __init__(self, settings):
        self.calls = []
        self.browser = {'session_id': BROWSER, 'backend': 'playwright', 'browser': 'chromium',
            'url': 'https://example.test/', 'title': 'Browser fixture', 'width': 800, 'height': 600}
        self.mobile = {'session_id': MOBILE, 'backend': 'appium', 'kind': 'mobile', 'profile': 'fixture-phone',
            'platform': 'Android', 'automation': 'UiAutomator2', 'title': 'fixture-phone', 'width': 390,
            'height': 844, 'observation_id': OBSERVATION, 'cursor': {'x': 20, 'y': 40},
            'input_notice': 'Input is shared with the configured mobile device.'}
        self.mobile_sessions = [self.mobile]

    def catalog(self):
        return [tool('rdc_mobile_start', 'Start configured fixture', {'profile': {'type': 'string'}}, ['profile'], True),
            tool('rdc_mobile_tap', 'Tap fixture', {name: {'type': 'string'} for name in ('session_id', 'observation_id', 'handle')},
                 ['session_id', 'observation_id', 'handle'], True),
            tool('rdc_mobile_close', 'Close fixture', {'session_id': {'type': 'string'}}, ['session_id'], True)]

    def status(self):
        return {'browser': {'backend': 'playwright', 'sessions': [self.browser]},
            'mobile': {'available': True, 'profiles': [{'profile': 'fixture-phone', 'platform': 'Android',
                'automation': 'UiAutomator2'}], 'sessions': self.mobile_sessions, 'independent_input': False}}

    def call(self, name, args):
        self.calls.append((name, args))
        if name == 'rdc_browser_list':
            return {'sessions': [self.browser]}
        if name == 'rdc_mobile_start':
            return dict(self.mobile)
        if name == 'rdc_mobile_tap':
            return dict(self.mobile)
        if name == 'rdc_mobile_close':
            self.mobile_sessions.clear()
            return {'session_id': MOBILE, 'closed': True}
        raise AssertionError(f'Unexpected dispatch: {name}')

    def snapshot(self, session_id=None):
        self.calls.append(('snapshot', session_id))
        item = self.mobile if session_id == MOBILE else self.browser
        return dict(item, mime_type='image/png', data=base64.b64encode(b'fixture-png').decode(),
                    source_width=item['width']*2, source_height=item['height']*2)

    def close(self):
        pass


class MobileIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.engines = []

    def tearDown(self):
        for engine in self.engines:
            engine.close()
        self.tmp.cleanup()

    def settings(self, **kwargs):
        return Settings(state_dir=self.base/'state', roots=[self.base], **kwargs)

    def engine(self, **kwargs):
        with patch('rdc.adapters.Adapters', CombinedAdapters):
            engine = Engine(self.settings(**kwargs))
        self.engines.append(engine)
        return engine

    def test_mobile_profiles_default_disabled_and_private_roundtrip(self):
        self.assertEqual(self.settings().mobile_profiles, {})
        settings = self.settings(mobile_profiles=PROFILES)
        path = self.base/'config.json'
        settings.save(path)
        loaded = Settings.load(path)
        self.assertEqual(loaded.mobile_profiles, PROFILES)
        public = loaded.public()
        self.assertNotIn('mobile_profiles', public)
        self.assertNotIn('private-fixture-device', json.dumps(public))
        self.assertNotIn('4723', json.dumps(public))

    def test_mixed_preview_retains_mobile_identity_and_routes_read_only_capture(self):
        engine = self.engine()
        engine.pause(True)
        opened = engine.call('rdc_preview_open', {'session_id': MOBILE})
        self.assertTrue(opened['ok'], opened)
        self.assertEqual(opened['session_id'], MOBILE)
        self.assertEqual({s['session_id'] for s in opened['sessions']}, {MOBILE})
        selected = next(s for s in opened['sessions'] if s['session_id'] == MOBILE)
        self.assertEqual(selected['viewport'], {'width': 390, 'height': 844})
        self.assertEqual(selected['kind'], 'mobile')
        frame = engine.call('rdc_preview_frame', {'session_id': MOBILE})
        self.assertTrue(frame['ok'], frame)
        self.assertEqual(frame['viewport'], {'width': 390, 'height': 844})
        self.assertEqual(frame['source_width'], 780)
        self.assertEqual(engine.adapters.calls, [('snapshot', MOBILE)])
        self.assertEqual(engine.store.approvals(), [])

    def test_unknown_mobile_selection_never_switches_to_browser(self):
        engine = self.engine()
        engine.adapters.mobile_sessions.clear()
        result = engine.call('rdc_preview_open', {'session_id': MOBILE})
        self.assertFalse(result['ok'])
        self.assertEqual(result['error']['code'], 'session_not_found')
        self.assertEqual(engine.adapters.calls, [])

    def test_mobile_mutation_uses_review_pause_and_stopping_contracts(self):
        engine = self.engine()
        queued = engine.call('rdc_mobile_start', {'profile': 'fixture-phone'})
        self.assertEqual(queued['status'], 'pending_approval')
        self.assertEqual(engine.adapters.calls, [])
        engine.pause(True)
        blocked = engine.call('rdc_mobile_tap', {'session_id': MOBILE, 'observation_id': OBSERVATION, 'handle': '1'})
        self.assertEqual(blocked['error']['code'], 'paused')
        closed = engine.call('rdc_mobile_close', {'session_id': MOBILE})
        self.assertTrue(closed['ok'], closed)
        self.assertTrue(closed['closed'])
        self.assertEqual(engine.adapters.calls, [('rdc_mobile_close', {'session_id': MOBILE})])

    def test_mobile_preview_ids_do_not_expand_browser_credential_schema(self):
        engine = self.engine()
        result = engine.call('rdc_credentials_request', {'credential_id': OBSERVATION,
            'session_id': MOBILE, 'observation_id': OBSERVATION, 'password_handle': '1',
            'idempotency_key': 'native-mobile-is-unsupported'})
        self.assertFalse(result['ok'])
        self.assertEqual(result['error']['code'], 'invalid_arguments')
        invalid = engine.call('rdc_mobile_start', {'profile': 'fixture-phone', 'endpoint': 'https://untrusted.test'})
        self.assertFalse(invalid['ok'])
        self.assertEqual(invalid['error']['code'], 'invalid_arguments')
        self.assertEqual(engine.adapters.calls, [])


if __name__ == '__main__':
    unittest.main()
