"""Owner-authorized, origin-bound password filling. No secret-read agent API.

Native provider output stays in a private callback path, outside ordinary tool
arguments, job logs and approval records. Full-host code remains outside this
application-level boundary. See docs/CREDENTIALS.md.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
from pathlib import Path
import stat
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from urllib.parse import urlsplit

from .errors import RDCError

MAX_CONFIG = 131072
MAX_SECRET = 65536
REQUEST_TTL = 900
MESSAGES = {
    'paused': 'Agent input is paused. Submit a fresh request after the owner resumes it.',
    'stale_observation': 'The page observation changed. Observe again and submit a fresh request.',
    'session_not_found': 'The selected browser session is no longer active.',
    'credential_origin_mismatch': 'The current website does not match the authorized credential origin.',
    'credential_target_invalid': 'Select an enabled, visible password input in the current top-level document.',
    'credential_validation_failed': 'The worker could not validate the password field. Observe the page and submit a fresh request.',
    'credential_transport_unsafe': 'Credential filling requires a local or HTTPS WebDriver connection.',
    'credential_config_changed': 'The credential mapping changed. Submit a fresh request for owner review.',
    'credential_config_invalid': 'The owner credential mapping is invalid or is not a private regular file.',
    'credential_mapping_invalid': 'Use a name, an exact HTTPS origin, and a matching supported native credential locator.',
    'credential_reenrollment_required': 'This older macOS mapping needs an explicit Keychain selection. Remove it and enroll it again before requesting a fill.',
    'credential_item_not_found': 'No matching saved item was found in the selected Keychain. Check the owner mapping.',
    'credential_item_ambiguous': 'More than one saved item matches the selected Keychain, server and account. No password was read. Use a Keychain and account with one matching item.',
    'credential_item_mismatch': 'The selected saved item does not match the configured HTTPS server, account, or port. No password was read.',
    'credential_write_failed': 'The private credential mapping could not be saved. Existing mappings were retained.',
    'credential_removal_incomplete': 'The mapping is unavailable, but saved permission cleanup failed. Retry removal with the same credential ID. No mapping was restored.',
    'credential_provider_unavailable': 'This credential provider is unavailable on this worker.',
    'credential_provider_denied': 'The operating system did not release this credential. Owner authentication may be required.',
    'credential_provider_timeout': 'The native credential request timed out. It was not retried.',
    'credential_provider_failed': 'The credential provider failed. No provider output is disclosed.',
    'credential_fill_failed': 'The private fill failed or its outcome is uncertain. Inspect the page before requesting another fill.',
    'credential_revoked': 'This credential authorization was revoked before input was admitted.',
    'credential_interrupted': 'The worker stopped before the request completed. No automatic retry is allowed.',
    'credential_expired': 'The credential request expired. Submit a fresh request.',
}


def fail(code):
    raise RDCError(code, MESSAGES[code])


def origin(value):
    """Canonical HTTPS origin from an actual browser URL; no wildcard matching."""
    try:
        if not isinstance(value, str) or any(ord(c) < 32 for c in value):
            raise ValueError
        parsed = urlsplit(value)
        if parsed.scheme.lower() != 'https' or parsed.username is not None or parsed.password is not None:
            raise ValueError
        host = parsed.hostname
        if not host or '%' in host or '\\' in host:
            raise ValueError
        try:
            address = ipaddress.ip_address(host)
            host = '[' + str(address) + ']' if address.version == 6 else str(address)
        except ValueError:
            host = host.rstrip('.').encode('idna').decode('ascii').lower()
            if not host or '*' in host or any(not part or len(part) > 63 or part.startswith('-') or part.endswith('-') or
                    any(not (c.isascii() and (c.isalnum() or c == '-')) for c in part) for part in host.split('.')):
                raise ValueError
        port = parsed.port
        if port is not None and not 1 <= port <= 65535:
            raise ValueError
        return 'https://' + host + (':' + str(port) if port not in (None, 443) else '')
    except (ValueError, UnicodeError):
        fail('credential_origin_mismatch')


class Secret:
    """Short-lived byte buffer; Python/browser temporary strings are not zeroizable."""
    def __init__(self, value, encoding='utf-8'):
        if not isinstance(value, (bytes, bytearray)) or not 0 < len(value) <= MAX_SECRET:
            fail('credential_provider_failed')
        self.value = bytearray(value)
        self.encoding = encoding

    def text(self):
        try:
            value = self.value.decode(self.encoding)
            if '\0' in value:
                fail('credential_provider_failed')
            return value
        except (UnicodeError, LookupError):
            fail('credential_provider_failed')

    def clear(self):
        self.value[:] = b'\0' * len(self.value)

    def __repr__(self):
        return '<RDC private credential buffer>'


class NativeProvider:
    def read(self, entry):
        provider, locator = entry['provider'], entry['locator']
        if provider == 'macos-keychain' and sys.platform == 'darwin':
            return self._macos(entry)
        if provider == 'windows-credential-manager' and sys.platform == 'win32':
            return self._windows(locator)
        fail('credential_provider_unavailable')

    def _macos(self, entry):
        from ._keychain_helper import EXIT_ERRORS, KeychainError, validate_locator
        locator, origins = entry['locator'], entry.get('origins', [])
        if locator.get('version') != 2:
            fail('credential_reenrollment_required')
        if len(origins) != 1:
            fail('credential_config_invalid')
        try:
            validate_locator(locator, origins[0])
        except KeychainError:
            fail('credential_config_invalid')
        # Private stdin contains locators only. Only the fixed helper path enters
        # argv; isolated Python excludes caller-controlled import search paths.
        command = [sys.executable, '-I', str(Path(__file__).resolve().with_name('_keychain_helper.py'))]
        request = json.dumps({'locator': locator, 'origin': origins[0]}).encode('utf-8')
        try:
            result = subprocess.run(command, input=request, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, timeout=90, check=False)
        except subprocess.TimeoutExpired:
            fail('credential_provider_timeout')
        except OSError:
            fail('credential_provider_unavailable')
        if result.returncode:
            fail(EXIT_ERRORS.get(result.returncode, 'credential_provider_failed'))
        return Secret(result.stdout)

    def _windows(self, locator):
        import ctypes
        from ctypes import wintypes

        class Credential(ctypes.Structure):
            _fields_ = [('Flags', wintypes.DWORD), ('Type', wintypes.DWORD),
                ('TargetName', wintypes.LPWSTR), ('Comment', wintypes.LPWSTR),
                ('LastWritten', wintypes.FILETIME), ('CredentialBlobSize', wintypes.DWORD),
                ('CredentialBlob', ctypes.POINTER(ctypes.c_ubyte)), ('Persist', wintypes.DWORD),
                ('AttributeCount', wintypes.DWORD), ('Attributes', ctypes.c_void_p),
                ('TargetAlias', wintypes.LPWSTR), ('UserName', wintypes.LPWSTR)]

        library = ctypes.WinDLL('Advapi32', use_last_error=True)
        pointer = ctypes.POINTER(Credential)()
        library.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                     ctypes.POINTER(ctypes.POINTER(Credential))]
        library.CredReadW.restype = wintypes.BOOL
        library.CredFree.argtypes = [ctypes.c_void_p]
        library.CredFree.restype = None
        if not library.CredReadW(locator['target'], 1, 0, ctypes.byref(pointer)):
            fail('credential_provider_denied')
        try:
            item = pointer.contents
            if not 0 < item.CredentialBlobSize <= MAX_SECRET:
                fail('credential_provider_failed')
            return Secret(ctypes.string_at(item.CredentialBlob, item.CredentialBlobSize),
                          locator.get('encoding', 'utf-16-le'))
        finally:
            if pointer:
                item = pointer.contents
                if item.CredentialBlob and 0 < item.CredentialBlobSize <= MAX_SECRET:
                    ctypes.memset(item.CredentialBlob, 0, item.CredentialBlobSize)
                library.CredFree(pointer)


class CredentialBroker:
    def __init__(self, engine):
        self.engine, self.store = engine, engine.store
        self.provider = NativeProvider()
        self.lock = threading.RLock()
        self.closed = False
        self.threads = set()
        with self.store.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS credential_requests (
                    id TEXT PRIMARY KEY, credential_id TEXT NOT NULL, label TEXT NOT NULL,
                    origin TEXT NOT NULL, device_id TEXT NOT NULL, locator_digest TEXT NOT NULL,
                    arguments TEXT NOT NULL, digest TEXT NOT NULL, client_key TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL, created_at REAL NOT NULL, expires_at REAL NOT NULL,
                    finished_at REAL, grant_id TEXT, error_code TEXT
                );
                CREATE TABLE IF NOT EXISTS credential_grants (
                    id TEXT PRIMARY KEY, credential_id TEXT NOT NULL, origin TEXT NOT NULL,
                    device_id TEXT NOT NULL, locator_digest TEXT NOT NULL,
                    created_at REAL NOT NULL, revoked_at REAL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS credential_active_grant
                ON credential_grants(credential_id, origin, device_id, locator_digest)
                WHERE revoked_at IS NULL;
            ''')
            # Browser documents are daemon-resident. Never retry an old request,
            # even if the old process died after sending input but before logging it.
            db.execute("UPDATE credential_requests SET status='interrupted', error_code='credential_interrupted', finished_at=? WHERE status IN ('pending','executing','filling')", (time.time(),))

    def _load(self):
        path = self.store.directory / 'credential-locators.json'
        try:
            fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
        except FileNotFoundError:
            return {}
        except OSError:
            fail('credential_config_invalid')
        try:
            with os.fdopen(fd, 'rb') as source:
                info = os.fstat(source.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_CONFIG:
                    fail('credential_config_invalid')
                if os.name != 'nt' and (info.st_mode & 0o077 or info.st_uid != os.geteuid()):
                    fail('credential_config_invalid')
                data = json.loads(source.read(MAX_CONFIG + 1))
            return self._validate_mapping(data)
        except (ValueError, TypeError, KeyError, AttributeError, OSError, UnicodeError, RDCError):
            fail('credential_config_invalid')

    @staticmethod
    def _validate_mapping(data):
        """One schema for existing private files and owner enrollment."""
        try:
            if not isinstance(data, dict) or set(data) != {'version', 'credentials'} or data['version'] != 1:
                raise ValueError
            rows = data['credentials']
            if not isinstance(rows, list) or len(rows) > 100:
                raise ValueError
            entries = {}
            for row in rows:
                if not isinstance(row, dict) or set(row) != {'id', 'label', 'origins', 'provider', 'locator'}:
                    raise ValueError
                identifier = str(uuid.UUID(row['id']))
                if identifier != row['id'] or identifier in entries:
                    raise ValueError
                if not isinstance(row['label'], str) or not 1 <= len(row['label']) <= 80 or any(ord(c) < 32 for c in row['label']):
                    raise ValueError
                if not isinstance(row['origins'], list) or not 1 <= len(row['origins']) <= 20:
                    raise ValueError
                allowed = []
                for value in row['origins']:
                    parsed = urlsplit(value)
                    if parsed.path not in ('', '/') or parsed.query or parsed.fragment:
                        raise ValueError
                    allowed.append(origin(value))
                locator = row['locator']
                if not isinstance(locator, dict):
                    raise ValueError
                if row['provider'] == 'macos-keychain':
                    legacy = set(locator) == {'server', 'account'}
                    if not legacy and (set(locator) != {'version', 'keychain', 'server', 'account'}
                            or type(locator['version']) is not int or locator['version'] != 2 or len(allowed) != 1):
                        raise ValueError
                    if any(urlsplit(value).hostname != locator['server'].lower().rstrip('.') for value in allowed):
                        raise ValueError
                    if not legacy:
                        from ._keychain_helper import KeychainError, validate_locator
                        try:
                            validate_locator(locator, allowed[0])
                        except KeychainError:
                            raise ValueError from None
                elif row['provider'] == 'windows-credential-manager':
                    if not {'target'} <= set(locator) <= {'target', 'encoding'} or locator.get('encoding', 'utf-16-le') not in ('utf-16-le', 'utf-8'):
                        raise ValueError
                else:
                    raise ValueError
                if any(not isinstance(v, str) or not 0 < len(v) <= (4096 if k == 'keychain' else 1024)
                       or any(ord(c) < 32 for c in v) for k, v in locator.items() if k != 'version'):
                    raise ValueError
                entry = dict(row, origins=sorted(set(allowed)))
                entry['locator_digest'] = hashlib.sha256(json.dumps(entry, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
                entries[identifier] = entry
            return entries
        except (ValueError, TypeError, KeyError, AttributeError, OSError, UnicodeError, RDCError):
            fail('credential_config_invalid')

    @staticmethod
    def _alias(entry):
        alias = {'credential_id': entry['id'], 'label': entry['label'], 'origins': entry['origins']}
        if entry['provider'] == 'macos-keychain' and entry['locator'].get('version') != 2:
            alias.update(requires_reenrollment=True, message=MESSAGES['credential_reenrollment_required'])
        return alias

    def _write_mapping(self, entries):
        value = {'version': 1, 'credentials': [
            {key: item[key] for key in ('id', 'label', 'origins', 'provider', 'locator')}
            for item in entries.values()]}
        self._validate_mapping(value)
        payload = (json.dumps(value, ensure_ascii=True, indent=2) + '\n').encode('utf-8')
        if len(payload) > MAX_CONFIG:
            fail('credential_mapping_invalid')
        temporary = None
        try:
            fd, temporary = tempfile.mkstemp(prefix='.credential-locators-', suffix='.json', dir=self.store.directory)
            with os.fdopen(fd, 'wb') as output:
                if os.name != 'nt': os.fchmod(output.fileno(), 0o600)
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.store.directory / 'credential-locators.json')
            temporary = None
        except OSError:
            fail('credential_write_failed')
        finally:
            if temporary is not None:
                try: os.unlink(temporary)
                except FileNotFoundError: pass

    def enroll(self, *, label, origin, provider, locator):
        """Owner-only mapping enrollment. Never reads or verifies a vault item."""
        with self.lock:
            if self.closed: fail('credential_interrupted')
            entries = self._load()  # Do not overwrite a malformed existing file.
            if provider == 'macos-keychain' and isinstance(locator, dict):
                if set(locator) == {'server', 'account'}:
                    fail('credential_reenrollment_required')
                keychain = locator.get('keychain')
                if isinstance(keychain, str) and keychain.startswith('~/'):
                    locator = dict(locator, keychain=str(Path.home() / keychain[2:].lstrip('/')))
            identifier = str(uuid.uuid4())
            candidate = {'id': identifier, 'label': label, 'origins': [origin],
                         'provider': provider, 'locator': locator}
            try:
                entry = self._validate_mapping({'version': 1, 'credentials': [candidate]})[identifier]
                if len(entries) >= 100: fail('credential_mapping_invalid')
            except RDCError:
                fail('credential_mapping_invalid')
            entries[identifier] = entry
            self._write_mapping(entries)
            return {'ok': True, 'credential': self._alias(entry),
                    'message': 'Saved the credential location. Native lookup still requires fill consent; the saved item has not been verified.'}

    def remove(self, credential_id):
        """Remove a mapping and block grants or requests not already admitted."""
        try:
            if not isinstance(credential_id, str) or str(uuid.UUID(credential_id)) != credential_id:
                raise ValueError
        except (ValueError, AttributeError):
            raise RDCError('invalid_arguments', 'credential_id must be a canonical UUID.') from None
        with self.lock:
            if self.closed: fail('credential_interrupted')
            entries = self._load()
            already_absent = credential_id not in entries
            if not already_absent:
                del entries[credential_id]
                self._write_mapping(entries)
            try:
                with self.store.connection() as db:
                    now = time.time()
                    db.execute('UPDATE credential_grants SET revoked_at=COALESCE(revoked_at,?) WHERE credential_id=?',
                               (now, credential_id))
                    db.execute("UPDATE credential_requests SET status='failed',error_code='credential_config_changed',finished_at=? WHERE credential_id=? AND status IN ('pending','executing')",
                               (now, credential_id))
            except sqlite3.Error:
                # The alias is already absent, so fills fail closed. An explicit
                # retry can finish cleanup without restoring data or grants.
                fail('credential_removal_incomplete')
            return {'ok': True, 'credential_id': credential_id, 'removed': True, 'already_absent': already_absent,
                    'message': 'Removed the saved credential location and its grants. Already-admitted input and browser sessions may continue.'}

    def list(self):
        return {'credentials': [self._alias(e) for e in self._load().values()]}

    def _expire(self, db):
        db.execute("UPDATE credential_requests SET status='expired', error_code='credential_expired', finished_at=? WHERE status='pending' AND expires_at<?", (time.time(), time.time()))

    @staticmethod
    def _public(row):
        result = {key: row[key] for key in ('id', 'credential_id', 'label', 'origin', 'device_id',
                  'status', 'created_at', 'expires_at', 'finished_at')}
        result['session_id'] = json.loads(row['arguments'])['session_id']
        if row['error_code']:
            result['error'] = {'code': row['error_code'], 'message': MESSAGES.get(row['error_code'], MESSAGES['credential_fill_failed'])}
        return result

    def _row(self, identifier, db):
        row = db.execute('SELECT * FROM credential_requests WHERE id=?', (identifier,)).fetchone()
        if row is None:
            raise RDCError('request_not_found', 'Credential request not found.')
        return row

    def status(self, request_id):
        with self.store.connection() as db:
            self._expire(db)
            return {'request': self._public(self._row(request_id, db))}

    def owner_snapshot(self):
        try:
            aliases = self.list()['credentials']
            configuration = 'ready' if aliases else 'unconfigured'
        except RDCError:
            aliases, configuration = [], 'invalid'
        with self.store.connection() as db:
            self._expire(db)
            requests = [self._public(row) for row in db.execute('SELECT * FROM credential_requests ORDER BY created_at DESC LIMIT 100')]
            grants = [{key: row[key] for key in ('id', 'credential_id', 'origin', 'device_id', 'created_at')}
                      for row in db.execute('SELECT * FROM credential_grants WHERE revoked_at IS NULL ORDER BY created_at DESC')]
        return {'configuration': configuration, 'aliases': aliases, 'requests': requests, 'grants': grants}

    def _entry(self, identifier):
        entry = self._load().get(identifier)
        if entry is None:
            raise RDCError('credential_not_configured', 'The owner has not configured that credential ID.')
        if entry['provider'] == 'macos-keychain' and entry['locator'].get('version') != 2:
            fail('credential_reenrollment_required')
        return entry

    def request(self, **arguments):
        encoded = json.dumps(arguments, sort_keys=True, separators=(',', ':'))
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        with self.lock:
            with self.store.connection() as db:
                self._expire(db)
                previous = db.execute('SELECT * FROM credential_requests WHERE client_key=?', (arguments['idempotency_key'],)).fetchone()
                if previous:
                    if previous['digest'] != digest:
                        raise RDCError('idempotency_conflict', 'This credential retry key belongs to a different request.')
                    return {'request': self._public(previous)}
            if self.closed:
                fail('credential_interrupted')
            if self.store.get('paused') == 'true':
                fail('paused')
        # Never hold the broker lock while waiting for the browser owner thread:
        # a previously queued private fill may need the same lock to be admitted.
        entry = self._entry(arguments['credential_id'])
        if not self.engine.adapters:
            fail('credential_target_invalid')
        try:
            actual = origin(self.engine.adapters.credentials_validate(arguments)['origin'])
        except Exception as exc:
            code = exc.code if isinstance(exc, RDCError) and exc.code in MESSAGES else 'credential_validation_failed'
            raise RDCError(code, MESSAGES[code]) from None
        if actual not in entry['origins']:
            fail('credential_origin_mismatch')
        with self.lock:
            if self.closed:
                fail('credential_interrupted')
            if self.store.get('paused') == 'true':
                fail('paused')
            if self._entry(entry['id'])['locator_digest'] != entry['locator_digest']:
                fail('credential_config_changed')
            now, identifier, device = time.time(), str(uuid.uuid4()), self.store.device_id
            with self.store.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                previous = db.execute('SELECT * FROM credential_requests WHERE client_key=?', (arguments['idempotency_key'],)).fetchone()
                if previous:
                    if previous['digest'] != digest:
                        raise RDCError('idempotency_conflict', 'This credential retry key belongs to a different request.')
                    return {'request': self._public(previous)}
                if db.execute("SELECT COUNT(*) FROM credential_requests WHERE status IN ('pending','executing','filling')").fetchone()[0] >= 32:
                    raise RDCError('credential_request_limit', 'At most 32 credential requests may be active.')
                grant = db.execute('SELECT id FROM credential_grants WHERE credential_id=? AND origin=? AND device_id=? AND locator_digest=? AND revoked_at IS NULL',
                    (entry['id'], actual, device, entry['locator_digest'])).fetchone()
                db.execute('INSERT INTO credential_requests(id,credential_id,label,origin,device_id,locator_digest,arguments,digest,client_key,status,created_at,expires_at,grant_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (identifier, entry['id'], entry['label'], actual, device, entry['locator_digest'], encoded, digest,
                     arguments['idempotency_key'], 'executing' if grant else 'pending', now, now + REQUEST_TTL, grant['id'] if grant else None))
            if grant:
                self._spawn(identifier)
            return self.status(identifier)

    def decide(self, request_id, decision):
        if decision not in ('once', 'always', 'deny'):
            raise RDCError('invalid_arguments', 'Decision must be once, always, or deny.')
        with self.lock:
            with self.store.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                self._expire(db)
                row = self._row(request_id, db)
                if row['status'] != 'pending':
                    raise RDCError('already_decided', 'This credential request is already decided, expired or executing.')
                if decision == 'deny':
                    db.execute("UPDATE credential_requests SET status='denied',finished_at=? WHERE id=?", (time.time(), request_id))
                else:
                    if self.closed:
                        fail('credential_interrupted')
                    if self.store.get('paused') == 'true':
                        fail('paused')
                    entry = self._entry(row['credential_id'])
                    if entry['locator_digest'] != row['locator_digest']:
                        fail('credential_config_changed')
                    grant_id = None
                    if decision == 'always':
                        existing = db.execute('SELECT id FROM credential_grants WHERE credential_id=? AND origin=? AND device_id=? AND locator_digest=? AND revoked_at IS NULL',
                            (row['credential_id'], row['origin'], row['device_id'], row['locator_digest'])).fetchone()
                        grant_id = existing['id'] if existing else str(uuid.uuid4())
                        if not existing:
                            db.execute('INSERT INTO credential_grants VALUES (?,?,?,?,?,?,NULL)',
                                (grant_id, row['credential_id'], row['origin'], row['device_id'], row['locator_digest'], time.time()))
                    # This transition consumes Allow Once before any provider read.
                    db.execute("UPDATE credential_requests SET status='executing',grant_id=? WHERE id=?", (grant_id, request_id))
            if decision != 'deny':
                self._spawn(request_id)
            return {'ok': True, **self.status(request_id)}

    def revoke(self, grant_id):
        with self.lock, self.store.connection() as db:
            if db.execute('SELECT id FROM credential_grants WHERE id=?', (grant_id,)).fetchone() is None:
                raise RDCError('grant_not_found', 'Credential grant not found.')
            db.execute('UPDATE credential_grants SET revoked_at=COALESCE(revoked_at,?) WHERE id=?', (time.time(), grant_id))
        return {'ok': True, 'grant_id': grant_id, 'revoked': True,
                'message': 'Inputs that have not been admitted are blocked. An already-admitted input may finish.'}

    def _check(self, identifier, *, admit=False):
        if self.closed:
            fail('credential_interrupted')
        if self.store.get('paused') == 'true':
            fail('paused')
        with self.store.connection() as db:
            row = self._row(identifier, db)
            if row['status'] != 'executing':
                fail('credential_revoked')
            if row['expires_at'] < time.time():
                fail('credential_expired')
            if row['device_id'] != self.store.device_id:
                fail('credential_revoked')
            entry = self._entry(row['credential_id'])
            if row['locator_digest'] != entry['locator_digest']:
                fail('credential_config_changed')
            if row['grant_id']:
                grant = db.execute('SELECT revoked_at FROM credential_grants WHERE id=?', (row['grant_id'],)).fetchone()
                if not grant or grant['revoked_at'] is not None:
                    fail('credential_revoked')
            if admit:
                db.execute("UPDATE credential_requests SET status='filling' WHERE id=?", (identifier,))
        return row, entry

    def _spawn(self, identifier):
        thread = threading.Thread(target=self._perform, args=(identifier,), name='rdc-credential-request', daemon=True)
        self.threads.add(thread)
        thread.start()

    def _perform(self, identifier):
        secret = None
        error = None
        stage = 'provider'
        try:
            with self.lock:
                row, entry = self._check(identifier)
            target = json.loads(row['arguments'])
            actual = origin(self.engine.adapters.credentials_validate(target)['origin'])
            if actual != row['origin']:
                fail('credential_origin_mismatch')
            with self.lock, self.engine._input_lock:
                # Validation may wait behind a browser action. Recheck owner
                # consent immediately before admitting a native provider read.
                row, entry = self._check(identifier)
            # Native authentication may wait; it must not hold the browser's
            # owning thread or block ordinary preview/status polling.
            secret = self.provider.read(entry)
            if not isinstance(secret, Secret):
                fail('credential_provider_failed')
            stage = 'fill'
            def deliver(fill):
                # Callback executes on the browser owner thread. Secret bytes
                # never enter Engine.call(), generic tool arguments or SQLite.
                with self.lock, self.engine._input_lock:
                    self._check(identifier, admit=True)
                fill(secret.text())
            self.engine.adapters.credentials_fill(target, row['origin'], deliver)
        except Exception as exc:
            error = exc.code if isinstance(exc, RDCError) and exc.code in MESSAGES else ('credential_provider_failed' if stage == 'provider' else 'credential_fill_failed')
        finally:
            if isinstance(secret, Secret):
                secret.clear()
            with self.lock:
                with self.store.connection() as db:
                    db.execute("UPDATE credential_requests SET status=?,error_code=?,finished_at=? WHERE id=? AND status IN ('executing','filling')",
                               ('failed' if error else 'filled', error, time.time(), identifier))
                self.threads.discard(threading.current_thread())

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            with self.store.connection() as db:
                db.execute("UPDATE credential_requests SET status='interrupted',error_code='credential_interrupted',finished_at=? WHERE status IN ('pending','executing','filling')", (time.time(),))
