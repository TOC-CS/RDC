"""Credential consent and private fill contracts. Native vaults are never read."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
import json
import os
import shutil
import sqlite3
import subprocess
from pathlib import Path, PurePosixPath
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.server import SimpleHTTPRequestHandler
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import patch

from rdc.config import Settings
from rdc.engine import Engine
from rdc.errors import RDCError
from rdc.adapters import Adapters
from tests.ui_artifacts import artifact_path

ALIAS = '5fa92907-4a83-4fe4-81a4-3a2af7267cef'
SESSION = '147472fb-e594-4bdd-a937-37f8c751afff'
OBSERVATION = '924458f3-f5ae-479f-97d6-a1b6c4d14c76'
SECRET = 'synthetic-RDC-only-7d9f5a!'


def macos_locator(server='example.test', account='private-account'):
    return {'version': 2, 'keychain': '/synthetic/rdc-tests.keychain-db', 'server': server, 'account': account}


class BrowserFixture:
    """Only the external browser boundary is replaced for broker unit tests."""
    def __init__(self):
        self.origin = 'https://example.test'
        self.observation = OBSERVATION
        self.values = []
        self.error = None

    def credentials_validate(self, target):
        if target['session_id'] != SESSION or target['observation_id'] != self.observation:
            raise RDCError('stale_observation', 'Observe again.')
        if target['password_handle'] != '1':
            raise RDCError('credential_target_invalid', 'Password input required.')
        return {'origin': self.origin}

    def credentials_fill(self, target, origin, deliver):
        current = self.credentials_validate(target)
        if current['origin'] != origin:
            raise RDCError('credential_origin_mismatch', 'Origin changed.')
        def fill(value):
            if self.error:
                raise self.error
            self.values.append(value)
            self.observation = str(uuid.uuid4())
        deliver(fill)
        return {'session_id': SESSION, 'filled': True}

    def status(self): return {'browser': {'sessions': []}}
    def close(self): pass


class CredentialsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.settings = Settings(self.root / 'private', [self.root], approval_mode='trusted', browser_backend='disabled')
        self.engine = Engine(self.settings)
        self.addCleanup(self.engine.close)

    def configure(self):
        self.mapping = {'version': 1, 'credentials': [{'id': ALIAS, 'label': 'Example account',
            'origins': ['https://example.test'], 'provider': 'macos-keychain',
            'locator': macos_locator()}]}
        path = self.settings.state_dir / 'credential-locators.json'
        path.write_text(json.dumps(self.mapping))
        path.chmod(0o600)
        self.engine.adapters.close()
        self.browser = BrowserFixture()
        self.engine.adapters = self.browser
        self.reads = []
        from rdc.credentials import Secret
        def read(entry):
            self.reads.append(entry['id'])
            return Secret(SECRET.encode())
        self.engine.credentials.provider.read = read

    def request(self, key=None):
        return self.engine.call('rdc_credentials_request', {'credential_id': ALIAS,
            'session_id': SESSION, 'observation_id': self.browser.observation,
            'password_handle': '1', 'idempotency_key': key or str(uuid.uuid4())})

    def terminal(self, identifier):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            result = self.engine.call('rdc_credentials_status', {'request_id': identifier})
            if result['request']['status'] not in ('pending', 'executing', 'filling'):
                return result['request']
            time.sleep(.01)
        self.fail('Credential request did not finish')

    def test_catalog_has_only_request_list_status_no_agent_authorization(self):
        tools = {item['name'] for item in self.engine.catalog()}
        self.assertEqual({name for name in tools if name.startswith('rdc_credentials_')},
            {'rdc_credentials_list', 'rdc_credentials_request', 'rdc_credentials_status'})
        result = self.engine.call('rdc_credentials_list')
        self.assertTrue(result['ok'])
        self.assertEqual(result['credentials'], [])

    def test_trusted_mode_still_requires_consent_and_once_cannot_replay(self):
        self.configure()
        response = self.request('one-request')
        self.assertTrue(response['ok'], response)
        request = response['request']
        self.assertEqual(request['status'], 'pending')
        self.assertEqual(self.reads, [])
        self.assertEqual(self.engine.store.approvals(), [])
        self.engine.credentials.decide(request['id'], 'once')
        self.assertEqual(self.terminal(request['id'])['status'], 'filled')
        self.assertEqual(self.browser.values, [SECRET])
        # Repeating the exact original arguments returns recorded outcome.
        replay = self.engine.call('rdc_credentials_request', {'credential_id': ALIAS,
            'session_id': SESSION, 'observation_id': OBSERVATION, 'password_handle': '1', 'idempotency_key': 'one-request'})
        self.assertEqual(replay['request']['id'], request['id'])
        self.assertEqual(self.reads, [ALIAS])
        with self.assertRaises(RDCError): self.engine.credentials.decide(request['id'], 'once')
        serialized = json.dumps([response, replay, self.engine.credentials.owner_snapshot(), self.engine.status(summary=True)])
        self.assertNotIn(SECRET, serialized)
        self.assertNotIn('private-account', serialized)
        self.assertNotIn(SECRET.encode(), self.engine.store.path.read_bytes())
        self.assertEqual(self.engine.call('rdc_file_read', {'file_path': str(self.settings.state_dir / 'credential-locators.json')})['error']['code'], 'path_denied')

    def test_origin_and_field_rejected_before_provider_or_consent(self):
        self.configure()
        self.browser.origin = 'https://other.test'
        self.assertEqual(self.request()['error']['code'], 'credential_origin_mismatch')
        self.assertEqual(self.reads, [])
        self.browser.origin = 'https://example.test'
        result = self.engine.call('rdc_credentials_request', {'credential_id': ALIAS, 'session_id': SESSION,
            'observation_id': OBSERVATION, 'password_handle': '2', 'idempotency_key': 'wrong-field'})
        self.assertEqual(result['error']['code'], 'credential_target_invalid')
        self.assertEqual(self.reads, [])

    def test_always_grant_revoke_and_mapping_change(self):
        self.configure()
        first = self.request()['request']
        self.engine.credentials.decide(first['id'], 'always')
        self.assertEqual(self.terminal(first['id'])['status'], 'filled')
        second = self.request()['request']
        self.assertEqual(self.terminal(second['id'])['status'], 'filled')
        grants = self.engine.credentials.owner_snapshot()['grants']
        self.assertEqual(len(grants), 1)
        self.engine.credentials.revoke(grants[0]['id'])
        third = self.request()['request']
        self.assertEqual(third['status'], 'pending')
        self.engine.credentials.decide(third['id'], 'always')
        self.assertEqual(self.terminal(third['id'])['status'], 'filled')
        self.mapping['credentials'][0]['locator']['account'] = 'different-private-account'
        (self.settings.state_dir / 'credential-locators.json').write_text(json.dumps(self.mapping))
        self.assertEqual(self.request()['request']['status'], 'pending')

    def test_navigation_or_pause_while_provider_waits_prevents_fill(self):
        self.configure()
        from rdc.credentials import Secret
        ready, release = threading.Event(), threading.Event()
        def read(entry):
            ready.set(); release.wait(5)
            return Secret(SECRET.encode())
        self.engine.credentials.provider.read = read
        for failure in ('navigate', 'pause'):
            with self.subTest(failure=failure):
                self.browser.origin = 'https://example.test'
                self.engine.pause(False)
                ready.clear(); release.clear()
                request = self.request()['request']
                self.engine.credentials.decide(request['id'], 'once')
                self.assertTrue(ready.wait(2))
                if failure == 'navigate': self.browser.origin = 'https://other.test'
                else: self.engine.pause(True)
                release.set()
                self.assertEqual(self.terminal(request['id'])['status'], 'failed')
                self.assertEqual(self.browser.values, [])

    def test_denial_and_concurrent_decisions_never_duplicate_fill(self):
        self.configure()
        denied = self.request()['request']
        self.engine.credentials.decide(denied['id'], 'deny')
        self.assertEqual(self.terminal(denied['id'])['status'], 'denied')
        self.assertEqual(self.reads, [])
        request = self.request()['request']
        def decide():
            try: return self.engine.credentials.decide(request['id'], 'once')
            except RDCError: return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: decide(), range(2)))
        self.assertEqual(self.terminal(request['id'])['status'], 'filled')
        self.assertEqual(self.browser.values, [SECRET])

    def test_provider_and_fill_exceptions_do_not_disclose_secret(self):
        self.configure()
        for source in ('provider', 'fill'):
            with self.subTest(source=source):
                from rdc.credentials import Secret
                if source == 'provider':
                    def read(entry): raise RuntimeError(SECRET)
                    self.engine.credentials.provider.read = read
                else:
                    self.engine.credentials.provider.read = lambda entry: Secret(SECRET.encode())
                    self.browser.error = RuntimeError(SECRET)
                request = self.request()['request']
                self.engine.credentials.decide(request['id'], 'once')
                final = self.terminal(request['id'])
                self.assertEqual(final['status'], 'failed')
                self.assertNotIn(SECRET, json.dumps(self.engine.credentials.owner_snapshot()))
                self.assertNotIn(SECRET.encode(), self.engine.store.path.read_bytes())

    def test_revoked_grant_while_provider_waits_and_restart_never_replay(self):
        self.configure()
        first = self.request()['request']
        self.engine.credentials.decide(first['id'], 'always')
        self.assertEqual(self.terminal(first['id'])['status'], 'filled')
        from rdc.credentials import Secret
        ready, release = threading.Event(), threading.Event()
        def read(entry):
            ready.set(); release.wait(5); return Secret(SECRET.encode())
        self.engine.credentials.provider.read = read
        second = self.request()['request']
        self.assertTrue(ready.wait(2))
        self.engine.credentials.revoke(self.engine.credentials.owner_snapshot()['grants'][0]['id'])
        release.set()
        self.assertEqual(self.terminal(second['id'])['error']['code'], 'credential_revoked')
        self.assertEqual(self.browser.values, [SECRET])
        pending = self.request()['request']
        self.engine.close()
        restarted = Engine(self.settings)
        try:
            self.assertEqual(restarted.call('rdc_credentials_status', {'request_id': pending['id']})['request']['status'], 'interrupted')
        finally: restarted.close()

    def test_http_owner_decisions_reject_agent_and_no_secrets_in_mcp(self):
        self.configure()
        from starlette.testclient import TestClient
        from rdc.server import create_app
        request = self.request()['request']
        with TestClient(create_app(self.engine, 'agent-test', 'owner-test'), base_url='http://127.0.0.1') as client:
            owner = {'Authorization': 'Bearer owner-test'}
            agent = {'Authorization': 'Bearer agent-test'}
            self.assertEqual(client.get('/api/credentials', headers=agent).status_code, 403)
            self.assertEqual(client.post('/api/credentials/decision', headers=agent,
                json={'request_id': request['id'], 'decision': 'always'}).status_code, 403)
            self.assertEqual(self.reads, [])
            result = client.post('/api/credentials/decision', headers=owner,
                json={'request_id': request['id'], 'decision': 'once'})
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(self.terminal(request['id'])['status'], 'filled')
            snapshot = client.get('/api/credentials', headers=owner)
            self.assertEqual(snapshot.status_code, 200)
            self.assertNotIn(SECRET, snapshot.text)
            self.assertNotIn('private-account', snapshot.text)

    def test_request_does_not_hold_broker_lock_while_waiting_for_browser_thread(self):
        self.configure()
        validate = self.browser.credentials_validate
        with ThreadPoolExecutor(max_workers=1) as browser_thread:
            def on_browser(target):
                # A prior credential fill on the browser owner thread may need
                # this lock for its final consent check before the next queued read.
                acquired = self.engine.credentials.lock.acquire(timeout=.25)
                if not acquired:
                    raise RDCError('browser_blocked', 'Browser thread blocked on broker admission.')
                try: return validate(target)
                finally: self.engine.credentials.lock.release()
            self.browser.credentials_validate = lambda target: browser_thread.submit(on_browser, target).result()
            result = self.request()
            self.assertTrue(result['ok'], result)

    def test_pause_during_browser_validation_prevents_provider_read(self):
        self.configure()
        request = self.request()['request']
        validate = self.browser.credentials_validate
        def pause_during_validation(target):
            result = validate(target)
            self.engine.pause(True)
            return result
        self.browser.credentials_validate = pause_during_validation
        self.engine.credentials.decide(request['id'], 'once')
        self.assertEqual(self.terminal(request['id'])['error']['code'], 'paused')
        self.assertEqual(self.reads, [])

    def test_initial_validation_exception_does_not_disclose_driver_text(self):
        self.configure()
        def broken_validation(target):
            raise RDCError('webdriver_error', SECRET)
        self.browser.credentials_validate = broken_validation
        result = self.request()
        self.assertFalse(result['ok'])
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertEqual(self.reads, [])

    def test_enrollment_writes_private_mapping_without_reading_provider(self):
        self.assertTrue(hasattr(self.engine.credentials, 'enroll'), 'Owner enrollment is required')
        self.engine.credentials.provider.read = lambda _: self.fail('Enrollment must not read the native provider')
        result = self.engine.credentials.enroll(label='Personal example', origin='https://example.test',
            provider='macos-keychain', locator=macos_locator())
        alias = result['credential']
        self.assertEqual(str(uuid.UUID(alias['credential_id'])), alias['credential_id'])
        self.assertEqual(alias['origins'], ['https://example.test'])
        self.assertNotIn('private-account', json.dumps(result))
        path = self.settings.state_dir / 'credential-locators.json'
        saved = json.loads(path.read_text())
        self.assertEqual(saved['credentials'][0]['id'], alias['credential_id'])
        self.assertEqual(saved['credentials'][0]['locator']['account'], 'private-account')
        if os.name != 'nt': self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.engine.credentials.list()['credentials'], [alias])
        windows = self.engine.credentials.enroll(label='Windows example', origin='https://windows.test',
            provider='windows-credential-manager', locator={'target': 'RDC synthetic target'})
        self.assertNotEqual(windows['credential']['credential_id'], alias['credential_id'])
        self.assertEqual(len(self.engine.credentials.list()['credentials']), 2)
        self.assertEqual(self.engine.credentials.owner_snapshot()['grants'], [])

    def test_enrollment_preserves_existing_mapping_on_invalid_input_or_atomic_write_failure(self):
        self.configure()
        self.assertTrue(hasattr(self.engine.credentials, 'enroll'), 'Owner enrollment is required')
        path = self.settings.state_dir / 'credential-locators.json'
        original = path.read_bytes()
        valid = {'label': 'Second account', 'origin': 'https://second.test', 'provider': 'macos-keychain',
                 'locator': macos_locator('second.test', 'private-second')}
        for change in ({'origin': 'http://second.test'}, {'origin': 'https://second.test/login'},
                       {'locator': macos_locator('other.test', 'private-second')},
                       {'label': ''}, {'locator': macos_locator('second.test', 'x') | {'password': SECRET}}):
            with self.subTest(change=tuple(change)):
                with self.assertRaises(RDCError): self.engine.credentials.enroll(**(valid | change))
                self.assertEqual(path.read_bytes(), original)
        observed = []
        def fail_replace(source, destination):
            observed.append(Path(source))
            self.assertEqual(Path(destination), path)
            self.assertEqual(path.read_bytes(), original)
            if os.name != 'nt': self.assertEqual(Path(source).stat().st_mode & 0o777, 0o600)
            raise OSError('synthetic atomic write failure')
        with patch('rdc.credentials.os.replace', side_effect=fail_replace):
            with self.assertRaises(RDCError): self.engine.credentials.enroll(**valid)
        self.assertEqual(len(observed), 1)
        self.assertFalse(observed[0].exists())
        self.assertEqual(path.read_bytes(), original)
        path.write_text('{malformed existing configuration')
        with self.assertRaises(RDCError): self.engine.credentials.enroll(**valid)
        self.assertEqual(path.read_text(), '{malformed existing configuration')
        self.assertEqual(self.reads, [])

    def test_enrollment_and_removal_routes_require_owner_token(self):
        from starlette.testclient import TestClient
        from rdc.server import create_app
        payload = {'label': 'Example account', 'origin': 'https://example.test', 'provider': 'macos-keychain',
                   'locator': macos_locator()}
        self.engine.credentials.provider.read = lambda _: self.fail('Mapping endpoints must not read a provider')
        with TestClient(create_app(self.engine, 'agent-test', 'owner-test'), base_url='http://127.0.0.1') as client:
            agent, owner = {'Authorization': 'Bearer agent-test'}, {'Authorization': 'Bearer owner-test'}
            self.assertEqual(client.post('/api/credentials/enroll', headers=agent, json=payload).status_code, 403)
            self.assertFalse((self.settings.state_dir / 'credential-locators.json').exists())
            response = client.post('/api/credentials/enroll', headers=owner, json=payload)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertNotIn('private-account', response.text)
            identifier = response.json()['credential']['credential_id']
            self.assertEqual(client.post('/api/credentials/remove', headers=agent,
                json={'credential_id': identifier}).status_code, 403)
            self.assertEqual(len(self.engine.credentials.list()['credentials']), 1)
            response = client.post('/api/credentials/remove', headers=owner, json={'credential_id': identifier})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(self.engine.credentials.list()['credentials'], [])

    def test_removing_alias_invalidates_grants_and_unadmitted_fill(self):
        self.configure()
        self.assertTrue(hasattr(self.engine.credentials, 'remove'), 'Owner removal is required')
        first = self.request()['request']
        self.engine.credentials.decide(first['id'], 'always')
        self.assertEqual(self.terminal(first['id'])['status'], 'filled')
        from rdc.credentials import Secret
        ready, release = threading.Event(), threading.Event()
        def read(entry):
            ready.set(); release.wait(5); return Secret(SECRET.encode())
        self.engine.credentials.provider.read = read
        second = self.request()['request']
        self.assertTrue(ready.wait(2))
        try:
            self.engine.credentials.remove(ALIAS)
            self.assertEqual(self.engine.credentials.list()['credentials'], [])
            self.assertEqual(self.engine.credentials.owner_snapshot()['grants'], [])
        finally:
            release.set()
            with self.engine.credentials.lock:
                remaining = tuple(self.engine.credentials.threads)
            for thread in remaining: thread.join(5)
        final = self.terminal(second['id'])
        self.assertEqual(final['error']['code'], 'credential_config_changed')
        self.assertEqual(self.browser.values, [SECRET])

    def test_partial_removal_retries_cleanup_without_restoring_mapping(self):
        self.configure()
        first, waiting = self.request('grant-first')['request'], self.request('still-pending')['request']
        self.engine.credentials.decide(first['id'], 'always')
        self.assertEqual(self.terminal(first['id'])['status'], 'filled')
        with patch.object(self.engine.store, 'connection', side_effect=sqlite3.OperationalError(SECRET)):
            with self.assertRaises(RDCError) as caught:
                self.engine.credentials.remove(ALIAS)
        self.assertEqual(caught.exception.code, 'credential_removal_incomplete')
        self.assertNotIn(SECRET, str(caught.exception))
        self.assertEqual(self.engine.credentials.list()['credentials'], [])
        self.assertEqual(len(self.engine.credentials.owner_snapshot()['grants']), 1)
        result = self.engine.credentials.remove(ALIAS)
        self.assertTrue(result['removed'])
        self.assertTrue(result['already_absent'])
        self.assertEqual(self.engine.credentials.owner_snapshot()['grants'], [])
        self.assertEqual(self.terminal(waiting['id'])['error']['code'], 'credential_config_changed')
        self.assertTrue(self.engine.credentials.remove(ALIAS)['removed'])
        self.assertEqual(self.engine.credentials.list()['credentials'], [])
        self.assertEqual(self.browser.values, [SECRET])

    def test_legacy_macos_alias_is_blocked_but_listable_and_removable(self):
        self.configure()
        self.mapping['credentials'][0]['locator'] = {'server': 'example.test', 'account': 'private-account'}
        windows_id = str(uuid.uuid4())
        self.mapping['credentials'].append({'id': windows_id, 'label': 'Windows synthetic',
            'origins': ['https://example.test'], 'provider': 'windows-credential-manager',
            'locator': {'target': 'private-windows-target'}})
        (self.settings.state_dir / 'credential-locators.json').write_text(json.dumps(self.mapping))
        result = self.request()
        self.assertFalse(result['ok'], 'An old ambiguous Keychain locator must not authorize a request')
        self.assertEqual(result['error']['code'], 'credential_reenrollment_required')
        aliases = self.engine.credentials.list()['credentials']
        legacy = next(a for a in aliases if a['credential_id'] == ALIAS)
        self.assertTrue(legacy['requires_reenrollment'])
        self.assertNotIn('private-account', json.dumps(aliases))
        self.assertNotIn('private-windows-target', json.dumps(aliases))
        request = self.engine.call('rdc_credentials_request', {'credential_id': windows_id,
            'session_id': SESSION, 'observation_id': OBSERVATION, 'password_handle': '1',
            'idempotency_key': 'windows-with-legacy-macos'})
        self.assertEqual(request['request']['status'], 'pending', request)
        self.assertEqual(self.reads, [])
        self.engine.credentials.decide(request['request']['id'], 'once')
        self.assertEqual(self.terminal(request['request']['id'])['status'], 'filled')
        self.assertEqual(self.reads, [windows_id])
        self.engine.credentials.remove(ALIAS)
        self.assertEqual([a['credential_id'] for a in self.engine.credentials.list()['credentials']], [windows_id])

    def test_macos_enrollment_requires_selected_keychain_and_expands_owner_home(self):
        from rdc.credentials import CredentialBroker
        self.engine.credentials.provider.read = lambda _: self.fail('Enrollment cannot read a provider')
        # The macOS locator uses POSIX paths even when this test runs on Windows.
        home = PurePosixPath('/Users/rdc-fixture')
        locator = {'version': 2, 'keychain': '~/Library/Keychains/login.keychain-db',
                   'server': 'example.test', 'account': 'private-account'}
        with patch('pathlib.Path.home', return_value=home):
            try:
                result = self.engine.credentials.enroll(label='Explicit keychain', origin='https://example.test:8443',
                    provider='macos-keychain', locator=locator)
            except RDCError as exc:
                self.fail(f'An explicit version-2 native mapping must be enrollable: {exc.code}')
        saved = json.loads((self.settings.state_dir / 'credential-locators.json').read_text())
        selected = saved['credentials'][0]
        self.assertEqual(selected['locator']['keychain'], str(home / 'Library/Keychains/login.keychain-db'))
        self.assertNotIn('keychain', result['credential'])
        self.assertNotIn(str(home), json.dumps(result))
        with patch('pathlib.Path.home', return_value=home):
            self.engine.credentials.enroll(label='Repeated separator', origin='https://example.test',
                provider='macos-keychain', locator=locator | {'keychain': '~//Library/Keychains/login.keychain-db'})
        added = json.loads((self.settings.state_dir / 'credential-locators.json').read_text())['credentials'][-1]
        self.assertEqual(added['locator']['keychain'], str(home / 'Library/Keychains/login.keychain-db'))
        for keychain in ('relative.keychain-db', '~another/Library/Keychains/login.keychain-db'):
            with self.subTest(keychain=keychain), self.assertRaises(RDCError):
                self.engine.credentials.enroll(label='Invalid path', origin='https://example.test',
                    provider='macos-keychain', locator=locator | {'keychain': keychain})
        selected['origins'].append('https://example.test:9443')
        with self.assertRaises(RDCError):
            CredentialBroker._validate_mapping(saved)
        with self.assertRaises(RDCError) as caught:
            self.engine.credentials.enroll(label='Legacy', origin='https://example.test', provider='macos-keychain',
                locator={'server': 'example.test', 'account': 'private-account'})
        self.assertEqual(caught.exception.code, 'credential_reenrollment_required')


class PrivateAdapterTests(unittest.TestCase):
    def setUp(self):
        self.origin = 'https://example.test'
        self.password_type = True
        self.private_values = []
        self.driver_error = False
        fixture = self
        class Driver(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_DELETE(self): self.respond()
            def do_GET(self): self.respond()
            def do_POST(self): self.respond()
            def respond(self):
                body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
                value = None
                if self.path == '/session': value = {'sessionId': 'fixture', 'capabilities': {'browserName': 'safari'}}
                elif self.path.endswith('/url'): value = fixture.origin + '/login'
                elif self.path.endswith('/title'): value = 'Login fixture'
                elif self.path.endswith('/execute/sync'):
                    script = body['script']
                    if 'RDC_OBSERVE' in script:
                        value = {'text': 'Login', 'document_id': 'doc1', 'width': 800, 'height': 600,
                            'controls': [{'element': {'element-6066-11e4-a52e-4f735466cecf': 'pw'},
                                'tag': 'input', 'name': 'Password', 'type': 'password', 'value': '[redacted]'}]}
                    elif 'RDC_DOCUMENT' in script: value = 'doc1'
                    elif 'RDC_CREDENTIAL_VALIDATE' in script:
                        value = {'origin': fixture.origin, 'valid': fixture.password_type, 'form_origin': fixture.origin}
                    elif 'RDC_CREDENTIAL_FILL' in script:
                        if fixture.driver_error:
                            value = {'error': 'javascript error', 'message': SECRET}
                        else:
                            fixture.private_values.append(body['args'][-1]); value = True
                raw = json.dumps({'value': value}).encode()
                self.send_response(200); self.send_header('Content-Type', 'application/json')
                self.end_headers(); self.wfile.write(raw)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Driver)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.temporary = tempfile.TemporaryDirectory()
        settings = Settings(Path(self.temporary.name) / 'state', [Path(self.temporary.name)],
            background_only=False, browser_backend='webdriver', webdriver_url=f'http://127.0.0.1:{self.server.server_port}',
            webdriver_capabilities={'browserName': 'safari'})
        self.adapter = Adapters(settings)
        self.sid = self.adapter.call('rdc_browser_start', {})['session_id']
        self.observation = self.adapter.call('rdc_browser_observe', {'session_id': self.sid})
        self.target = {'session_id': self.sid, 'observation_id': self.observation['observation_id'], 'password_handle': '1'}

    def tearDown(self):
        self.adapter.close(); self.server.shutdown(); self.server.server_close(); self.thread.join(); self.temporary.cleanup()

    def test_private_fill_checks_current_origin_type_and_invalidates_handle(self):
        self.assertTrue(hasattr(self.adapter, 'credentials_validate'), 'Private credential validation is required')
        self.assertEqual(self.adapter.credentials_validate(self.target)['origin'], 'https://example.test')
        self.password_type = False
        with self.assertRaises(RDCError): self.adapter.credentials_validate(self.target)
        self.password_type = True
        self.adapter.credentials_fill(self.target, 'https://example.test', lambda fill: fill(SECRET))
        self.assertEqual(self.private_values, [SECRET])
        with self.assertRaises(RDCError): self.adapter.credentials_fill(self.target, 'https://example.test', lambda fill: fill(SECRET))

    def test_driver_exception_never_returns_secret_and_wrong_origin_does_not_fill(self):
        self.assertTrue(hasattr(self.adapter, 'credentials_fill'), 'Private credential fill is required')
        with self.assertRaises(RDCError):
            self.adapter.credentials_fill(self.target, 'https://other.test', lambda fill: fill(SECRET))
        self.assertEqual(self.private_values, [])
        self.driver_error = True
        with self.assertRaises(RDCError) as caught:
            self.adapter.credentials_fill(self.target, 'https://example.test', lambda fill: fill(SECRET))
        self.assertNotIn(SECRET, str(caught.exception))








class RealCredentialBrowserTests(unittest.TestCase):
    def test_synthetic_secret_reaches_only_selected_password_field(self):
        from rdc.adapters import _Browsers
        from rdc.credentials import Secret
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        with nullcontext(directory.name) as temporary:
            root = Path(temporary)
            settings = Settings(root / 'private', [root], approval_mode='trusted')
            engine = Engine(settings)
            self.addCleanup(engine.close)
            mapping = {'version': 1, 'credentials': [{'id': ALIAS, 'label': 'Synthetic account',
                'origins': ['https://example.test'], 'provider': 'macos-keychain',
                'locator': macos_locator(account='synthetic-only')}]}
            config = settings.state_dir / 'credential-locators.json'
            config.write_text(json.dumps(mapping)); config.chmod(0o600)
            engine.credentials.provider.read = lambda entry: Secret(SECRET.encode())
            html = '<label>Password<input type="password" name="password"></label><button>Check</button><p>Waiting</p><script>' + \
                'document.querySelector("button").onclick=()=>{document.querySelector("p").textContent=' + \
                '(document.querySelector("input").value===' + json.dumps(SECRET) + \
                ')?"Private credential verified":"Wrong value"}</script>'
            original = _Browsers.start
            def start_fixture(worker, arguments):
                result = original(worker, arguments)
                worker.sessions[result['session_id']]['page'].route('https://example.test/**',
                    lambda route: route.fulfill(status=200, content_type='text/html', body=html))
                return result
            if os.path.exists('/usr/bin/chromium'):
                environment = patch.dict(os.environ, {'RDC_CHROMIUM_EXECUTABLE': '/usr/bin/chromium'})
                environment.start(); self.addCleanup(environment.stop)
            with patch.object(_Browsers, 'start', start_fixture):
                result = engine.call('rdc_browser_start')
            if not result['ok']:
                text = result['error']['message']
                if ('Operation not permitted' in text and 'socket() failed' in text) or 'Executable doesn' in text or 'playwright install' in text:
                    self.skipTest(text)
                self.fail(text)
            sid = result['session_id']
            self.assertTrue(engine.call('rdc_browser_navigate', {'session_id': sid, 'url': 'https://example.test/login'})['ok'])
            observed = engine.call('rdc_browser_observe', {'session_id': sid})
            field = next(c for c in observed['controls'] if c['type'] == 'password')
            request = engine.call('rdc_credentials_request', {'credential_id': ALIAS, 'session_id': sid,
                'observation_id': observed['observation_id'], 'password_handle': field['handle'], 'idempotency_key': 'real-browser'})
            self.assertTrue(request['ok'], request)
            identifier = request['request']['id']
            engine.credentials.decide(identifier, 'once')
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                final = engine.call('rdc_credentials_status', {'request_id': identifier})
                if final['request']['status'] not in ('executing', 'filling'): break
                time.sleep(.01)
            self.assertEqual(final['request']['status'], 'filled', final)
            observed = engine.call('rdc_browser_observe', {'session_id': sid})
            self.assertNotIn(SECRET, json.dumps(observed))
            self.assertEqual(next(c for c in observed['controls'] if c['type'] == 'password')['value'], '[redacted]')
            button = next(c for c in observed['controls'] if c['tag'] == 'button')
            engine.call('rdc_browser_click', {'session_id': sid, 'observation_id': observed['observation_id'], 'handle': button['handle']})
            self.assertIn('Private credential verified', engine.call('rdc_browser_observe', {'session_id': sid})['text'])
            self.assertNotIn(SECRET.encode(), engine.store.path.read_bytes())
            engine.close()


if __name__ == '__main__': unittest.main()
