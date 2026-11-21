"""Outbound, credential-separated bridge from a private RDC worker to a gateway.

The gateway assigns an immutable operation ID and exact request digest. This
pump journals that identity before dispatch and journals the result before
upload. An interrupted dispatch is never automatically replayed. Gateway result
uploads are idempotent; an upload retry cannot invoke the local tool again.

Only the local agent MCP credential is read. The pump never owns or closes the
worker, reads an owner token, changes grants, or exposes an inbound device port.
"""
from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field, replace
import hashlib
import hmac
import ipaddress
import json
import logging
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import time
from urllib.parse import unquote, urlsplit

import anyio
import httpx2
import jsonschema
from mcp import ClientSession, types
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError

from .diagnostics import Diagnostics, safe_record

MAX_WIRE_BYTES = 16 * 1024 * 1024
MAX_RESULT_BYTES = 12 * 1024 * 1024
MAX_REQUEST_BYTES = 12 * 1024 * 1024
RETAINED_RESULT_BYTES = 64 * 1024 * 1024
IDENTIFIER = re.compile(r'^[A-Za-z0-9_.-]{1,128}$')
TOOL_NAME = re.compile(r'^rdc_[A-Za-z0-9_]{1,100}$')
OBSERVATION_TOOL = 'rdc_preview_activity'
OBSERVER_POLL_SECONDS = 1.0
OBSERVER_TIMEOUT_SECONDS = 5.0
LOGGER = logging.getLogger(__name__)


class RelayError(RuntimeError):
    """A deliberately credential-free public diagnostic."""


class RelayPermanentError(RelayError):
    """Requires an owner configuration or protocol correction."""


class RelayTransientError(RelayError):
    """May retry transport, but never replay an uncertain device operation."""


class RelayMissingOperation(RelayPermanentError):
    """The authenticated gateway has retired this exact operation identity."""


def _json(text):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def constant(value):
        raise ValueError('nonfinite JSON number')
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def _encoded(value, limit=MAX_WIRE_BYTES):
    try:
        result = json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        if len(result.encode('utf-8')) > limit:
            raise ValueError
        return result
    except (ValueError, TypeError, RecursionError, UnicodeError):
        raise RelayPermanentError('Relay payload is invalid or exceeds the configured byte limit.') from None


def _url_parts(url):
    try:
        if not isinstance(url, str) or len(url) > 2048 or any(ord(c) <= 32 or ord(c) == 127 for c in url):
            raise ValueError
        parts = urlsplit(url)
        if (not parts.hostname or parts.username is not None or parts.password is not None or
                parts.query or parts.fragment or '\\' in url or '%' in parts.netloc or
                (parts.port is not None and not 1 <= parts.port <= 65535)):
            raise ValueError
        path = unquote(parts.path)
        if path != parts.path or any(piece in ('.', '..') for piece in path.split('/')) or '//' in path:
            raise ValueError
        return parts
    except (ValueError, TypeError):
        raise RelayPermanentError('Relay endpoint URL is invalid; credentials, queries, fragments, and ambiguous paths are forbidden.') from None


def validate_gateway_url(url):
    parts = _url_parts(url)
    if parts.scheme != 'https':
        raise RelayPermanentError('The relay gateway requires an HTTPS URL with certificate verification.')
    return url.rstrip('/')


def validate_worker_url(url):
    parts = _url_parts(url)
    try:
        local = ipaddress.ip_address(parts.hostname).is_loopback
    except ValueError:
        local = parts.hostname == 'localhost'
    if parts.scheme not in ('http', 'https') or not local or not parts.path:
        raise RelayPermanentError('The relay worker must be an explicit loopback HTTP or HTTPS MCP endpoint.')
    return url


def _private_bytes(path, limit):
    try:
        fd = os.open(Path(path).expanduser(), os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or (os.name != 'nt' and (info.st_uid != os.getuid() or info.st_mode & 0o077)):
                raise ValueError
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError
        return data
    except (OSError, ValueError):
        raise RelayPermanentError('Relay configuration and token files must be regular private files owned by this account (mode 600 on Unix).') from None


def _secret(value, minimum=32, maximum=4096):
    return (isinstance(value, str) and minimum <= len(value) <= maximum and
            all(32 < ord(character) < 127 for character in value))


@dataclass(frozen=True)
class RelayConfig:
    gateway_url: str
    device_id: str
    device_key: str = field(repr=False)
    sites_service_token: str = field(default='', repr=False)
    worker_url: str = 'http://127.0.0.1:8765/mcp'
    allowed_tools: tuple[str, ...] | None = None
    tool_timeout: float = 60
    transport: str = 'sites'  # opt-in standalone without ChatGPT Sites

    def __post_init__(self):
        object.__setattr__(self, 'gateway_url', validate_gateway_url(self.gateway_url))
        object.__setattr__(self, 'worker_url', validate_worker_url(self.worker_url))
        if not isinstance(self.device_id, str) or not IDENTIFIER.fullmatch(self.device_id):
            raise RelayPermanentError('Relay device identity is invalid.')
        if not _secret(self.device_key, maximum=1024):
            raise RelayPermanentError('Relay device credential must be a valid private value.')
        if self.transport == 'sites':
            if not _secret(self.sites_service_token):
                raise RelayPermanentError('A private Sites transport requires its separate service credential.')
            if hmac.compare_digest(self.device_key, self.sites_service_token):
                raise RelayPermanentError('Relay device and Sites service credentials must be distinct.')
        elif self.transport == 'standalone':
            if self.sites_service_token != '':
                raise RelayPermanentError('Independent standalone transport must not use a ChatGPT Sites token.')
        else:
            raise RelayPermanentError('Unknown relay gateway transport mode.')
        if isinstance(self.tool_timeout, bool) or not isinstance(self.tool_timeout, (int, float)) or not math.isfinite(self.tool_timeout) or not .1 <= self.tool_timeout <= 120:
            raise RelayPermanentError('Relay tool timeout must be between 0.1 and 120 seconds.')
        if self.allowed_tools is not None:
            if (not isinstance(self.allowed_tools, (tuple, list)) or len(self.allowed_tools) > 256 or
                    any(not isinstance(name, str) or not TOOL_NAME.fullmatch(name) for name in self.allowed_tools)):
                raise RelayPermanentError('Relay allowed_tools must be a bounded list of RDC tool names.')
            object.__setattr__(self, 'allowed_tools', tuple(dict.fromkeys(self.allowed_tools)))

    @classmethod
    def load(cls, path):
        try:
            data = _json(_private_bytes(path, 32768).decode('utf-8'))
            if not isinstance(data, dict):
                raise ValueError
            return cls(**data)
        except RelayError:
            raise
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise RelayPermanentError('Relay configuration must be valid JSON with the documented configuration fields.') from None

    @property
    def binding(self):
        return hashlib.sha256(_encoded({'gateway': self.gateway_url, 'device': self.device_id}).encode()).hexdigest()


@dataclass(frozen=True)
class Operation:
    operation_id: str
    claim_id: str
    request_json: str = field(repr=False)
    request_sha256: str
    expires_at_ms: int
    deadline: float

    @classmethod
    def from_wire(cls, data, server_time_ms):
        try:
            if not isinstance(data, dict) or set(data) != {'operation_id', 'claim_id', 'request_json', 'request_sha256', 'expires_at_ms'}:
                raise ValueError
            if any(not isinstance(data[key], str) or not IDENTIFIER.fullmatch(data[key]) for key in ('operation_id', 'claim_id')):
                raise ValueError
            raw, digest = data['request_json'], data['request_sha256']
            if not isinstance(raw, str) or len(raw.encode('utf-8')) > MAX_REQUEST_BYTES or not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
                raise ValueError
            if not hmac.compare_digest(hashlib.sha256(raw.encode('utf-8')).hexdigest(), digest):
                raise ValueError
            request = _json(raw)
            if (not isinstance(request, dict) or set(request) != {'name', 'arguments'} or
                    not isinstance(request['name'], str) or len(request['name']) > 128 or not isinstance(request['arguments'], dict)):
                raise ValueError
            expires = data['expires_at_ms']
            if type(expires) is not int or type(server_time_ms) is not int or not 0 <= expires < 2**53 or not 0 <= server_time_ms < 2**53:
                raise ValueError
            remaining = (expires - server_time_ms) / 1000
            if remaining > 300:
                raise ValueError
            return cls(data['operation_id'], data['claim_id'], raw, digest, expires, time.monotonic() + remaining)
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise RelayPermanentError('Gateway operation is malformed, has an invalid digest, or exceeds its byte/time limit.') from None

    @property
    def request(self):
        return _json(self.request_json)


def error_result(code, message, operation_id=None):
    error = {'code': code, 'message': message}
    if operation_id is not None:
        error['operation_id'] = operation_id
    data = {'ok': False, 'error': error}
    return {'content': [{'type': 'text', 'text': _encoded(data)}], 'structuredContent': data, 'isError': True}


def _result_payload(device_id, operation, result_json):
    return {'device_id': device_id, 'operation_id': operation.operation_id,
            'claim_id': operation.claim_id, 'request_sha256': operation.request_sha256,
            'result_json': result_json}


def _deliverable_result(device_id, operation, result_json):
    """Keep the durable outbox sendable, including JSON-in-JSON escaping."""
    try:
        if len(result_json.encode('utf-8')) > MAX_RESULT_BYTES:
            raise RelayPermanentError('Result exceeds its byte limit.')
        _encoded(_result_payload(device_id, operation, result_json))
        return result_json
    except (RelayPermanentError, UnicodeError):
        return _encoded(error_result('result_too_large',
            'The action returned a result exceeding the relay result or upload limit. It was not repeated; inspect the worker for its outcome.',
            operation.operation_id), MAX_RESULT_BYTES)


class Journal:
    """Durable inbox/outbox; retained identity tombstones prevent old replays."""
    def __init__(self, path, binding):
        self.db = None
        try:
            path = Path(path)
            if path.is_symlink():
                raise ValueError
            try:
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
                os.close(fd)
            except FileExistsError:
                info = path.stat()
                if not stat.S_ISREG(info.st_mode) or (os.name != 'nt' and (info.st_uid != os.getuid() or info.st_mode & 0o077)):
                    raise ValueError
            self.db = sqlite3.connect(path, timeout=5)
            self.db.row_factory = sqlite3.Row
            self.db.execute('PRAGMA journal_mode=WAL')
            self.db.execute('PRAGMA synchronous=FULL')
            self.db.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            self.db.execute('CREATE TABLE IF NOT EXISTS operations (operation_id TEXT PRIMARY KEY, claim_id TEXT NOT NULL, request_sha256 TEXT NOT NULL, request_json TEXT, expires_at_ms INTEGER NOT NULL, state TEXT NOT NULL, result_json TEXT, created REAL NOT NULL, updated REAL NOT NULL)')
            with self.db:
                previous = self.db.execute("SELECT value FROM metadata WHERE key='binding'").fetchone()
                if previous and not hmac.compare_digest(previous['value'], binding):
                    raise ValueError
                self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('binding',?)", (binding,))
        except (sqlite3.Error, OSError, ValueError):
            self.close()
            raise RelayPermanentError('Relay journal is unavailable, is not private, or belongs to another gateway/device pairing.') from None

    def close(self):
        if self.db is not None:
            self.db.close(); self.db = None

    def get(self, operation_id):
        row = self.db.execute('SELECT * FROM operations WHERE operation_id=?', (operation_id,)).fetchone()
        return dict(row) if row else None

    def remember(self, operation):
        try:
            with self.db:
                self.db.execute('BEGIN IMMEDIATE')
                existing = self.get(operation.operation_id)
                if existing:
                    if not hmac.compare_digest(existing['request_sha256'], operation.request_sha256) or not hmac.compare_digest(existing['claim_id'], operation.claim_id):
                        raise RelayPermanentError('An existing relay operation ID was reused with a different request or claim. Nothing was executed.')
                    return existing
                now = time.time()
                self.db.execute('INSERT INTO operations VALUES (?,?,?,?,?,?,?,?,?)',
                    (operation.operation_id, operation.claim_id, operation.request_sha256, operation.request_json,
                     operation.expires_at_ms, 'received', None, now, now))
            return self.get(operation.operation_id)
        except sqlite3.Error:
            raise RelayPermanentError('Relay journal could not record the inbox. Nothing was dispatched.') from None

    def mark_executing(self, operation_id):
        try:
            with self.db:
                result = self.db.execute("UPDATE operations SET state='executing',updated=? WHERE operation_id=? AND state='received'", (time.time(), operation_id))
                if result.rowcount != 1:
                    raise RelayPermanentError('Relay operation is already dispatched; automatic replay is forbidden.')
        except sqlite3.Error:
            raise RelayPermanentError('Relay journal could not record dispatch. Nothing was dispatched.') from None

    def complete(self, operation_id, result_json):
        if len(result_json.encode('utf-8')) > MAX_RESULT_BYTES:
            raise RelayPermanentError('Relay result exceeds its storage byte limit.')
        try:
            with self.db:
                changed = self.db.execute("UPDATE operations SET state='ready',result_json=?,updated=? WHERE operation_id=?", (result_json, time.time(), operation_id))
                if changed.rowcount != 1:
                    raise RelayPermanentError('Relay result has no durable operation identity.')
        except sqlite3.Error:
            raise RelayPermanentError('Relay could not persist a tool result. Its outcome must be inspected before any retry.') from None

    def recover(self, diagnostics=None):
        # Even 'received' work is not resumed automatically. The gateway does
        # not redeliver claims, and an old operation may no longer be intended.
        rows = self.db.execute("SELECT operation_id,state FROM operations WHERE state IN ('received','executing')").fetchall()
        for row in rows:
            executing = row['state'] == 'executing'
            safe_record(diagnostics, 'relay', 'outcome_unknown' if executing else 'interrupted_before_dispatch')
            result = error_result('outcome_unknown' if executing else 'interrupted_before_dispatch',
                'Relay stopped during dispatch. The action may have completed. Inspect the worker before any new attempt.' if executing else
                'Relay stopped before dispatch. This operation was not automatically executed on restart.', row['operation_id'])
            self.complete(row['operation_id'], _encoded(result, MAX_RESULT_BYTES))

    def pending(self, operation_id=None):
        if operation_id is None:
            rows = self.db.execute("SELECT * FROM operations WHERE state='ready' ORDER BY created LIMIT 32").fetchall()
        else:
            rows = self.db.execute("SELECT * FROM operations WHERE state='ready' AND operation_id=?", (operation_id,)).fetchall()
        for row in rows:
            yield Operation(row['operation_id'], row['claim_id'], row['request_json'] or '', row['request_sha256'], row['expires_at_ms'], 0), row['result_json']

    def delivered(self, operation_id):
        try:
            with self.db:
                self.db.execute("UPDATE operations SET state='delivered',request_json=NULL,updated=? WHERE operation_id=? AND state='ready'", (time.time(), operation_id))
        except sqlite3.Error:
            raise RelayPermanentError('Relay could not record the gateway acknowledgement. The same result may be uploaded again safely.') from None

    def undeliverable(self, operation_id):
        """Retain a retired cloud outcome without claiming its upload succeeded."""
        try:
            with self.db:
                changed = self.db.execute("UPDATE operations SET state='undeliverable',updated=? WHERE operation_id=? AND state='ready'", (time.time(), operation_id))
                if changed.rowcount != 1:
                    raise RelayPermanentError('The retired relay result has no ready durable operation. Nothing will be repeated.')
        except sqlite3.Error:
            raise RelayPermanentError('Relay could not retain an undeliverable outcome. No new work will be dispatched.') from None

    def prune_results(self, max_bytes=RETAINED_RESULT_BYTES):
        # Large screenshot results do not accumulate without bound. Small
        # identity/digest tombstones and undeliverable state remain indefinitely.
        # Retired, unacknowledged outcomes keep their original request/result
        # together until this same terminal-payload retention bound is reached.
        try:
            with self.db:
                payload_bytes = 'COALESCE(LENGTH(CAST(result_json AS BLOB)),0)+COALESCE(LENGTH(CAST(request_json AS BLOB)),0)'
                size = self.db.execute(f"SELECT COALESCE(SUM({payload_bytes}),0) FROM operations WHERE state IN ('delivered','undeliverable')").fetchone()[0]
                if size <= max_bytes:
                    return
                rows = self.db.execute(f"SELECT operation_id,{payload_bytes} AS size FROM operations WHERE state IN ('delivered','undeliverable') AND (result_json IS NOT NULL OR request_json IS NOT NULL) ORDER BY updated").fetchall()
                for row in rows:
                    self.db.execute('UPDATE operations SET result_json=NULL,request_json=NULL WHERE operation_id=?', (row['operation_id'],))
                    size -= row['size']
                    if size <= max_bytes:
                        break
        except sqlite3.Error:
            raise RelayPermanentError('Relay result retention could not be maintained; no new work will be dispatched.') from None


class Gateway:
    def __init__(self, config, client):
        self.config = config; self.client = client
        self.supports_activity_observer = False

    async def _post(self, path, value):
        payload = _encoded(value).encode('utf-8')
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json',
                   'OAI-Sites-Authorization': 'Bearer ' + self.config.sites_service_token,
                   'X-RDC-Device-Key': self.config.device_key}
        try:
            with anyio.fail_after(20):
                async with self.client.stream('POST', self.config.gateway_url + path, content=payload,
                                              headers=headers, follow_redirects=False) as response:
                    if response.status_code in (401, 403):
                        raise RelayPermanentError('Relay gateway authentication was rejected. Check the private device and Sites credentials.')
                    if 300 <= response.status_code < 400:
                        raise RelayPermanentError('Relay gateway redirects are forbidden. Configure its final HTTPS endpoint.')
                    if response.status_code == 409:
                        raise RelayPermanentError('Relay gateway rejected an operation or result identity conflict. The local action will not be repeated.')
                    if response.status_code == 429 or response.status_code >= 500:
                        raise RelayTransientError('Relay gateway is temporarily unavailable.')
                    missing_operation = response.status_code == 404 and path == '/device/result'
                    if response.status_code != 200 and not missing_operation:
                        raise RelayPermanentError('Relay gateway rejected the protocol request.')
                    declared = response.headers.get('content-length')
                    if declared is not None:
                        try:
                            if not 0 <= int(declared) <= MAX_WIRE_BYTES:
                                raise ValueError
                        except ValueError:
                            raise RelayPermanentError('Relay gateway response exceeds its byte limit or has invalid framing.') from None
                    chunks = []; total = 0
                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        total += len(chunk)
                        if total > MAX_WIRE_BYTES:
                            raise RelayPermanentError('Relay gateway response exceeds its byte limit.')
                        chunks.append(chunk)
                    try:
                        data = _json(b''.join(chunks).decode('utf-8'))
                        if not isinstance(data, dict):
                            raise ValueError
                        if missing_operation:
                            error = data.get('error')
                            if data.get('ok') is False and isinstance(error, dict) and error.get('code') == 'operation_not_found':
                                raise RelayMissingOperation('The gateway no longer retains this operation identity. The device action will not be repeated.')
                            raise RelayPermanentError('Relay gateway rejected the protocol request.')
                        return data
                    except (ValueError, TypeError, UnicodeError, RecursionError):
                        raise RelayPermanentError('Relay gateway returned an invalid JSON response.') from None
        except RelayError:
            raise
        except (httpx2.HTTPError, TimeoutError, ConnectionError, OSError):
            raise RelayTransientError('Relay gateway connection was interrupted; only queued result uploads may be retried.') from None

    async def poll(self, claim=True, observation_only=False):
        if type(observation_only) is not bool or observation_only and not claim:
            raise RelayPermanentError('An observer poll must explicitly claim only activity observations.')
        if observation_only and not self.supports_activity_observer:
            raise RelayPermanentError('The gateway has not advertised the activity observer lane.')
        poll_started = time.monotonic()
        payload = {'device_id': self.config.device_id, 'claim': bool(claim)}
        if observation_only:
            payload['observation_only'] = True
        data = await self._post('/device/poll', payload)
        if data.get('ok') is not True or data.get('device_id') != self.config.device_id or type(data.get('server_time_ms')) is not int:
            raise RelayPermanentError('Relay gateway poll did not confirm the paired device identity.')
        supported = data.get('observation_tools') == [OBSERVATION_TOOL]
        if observation_only and (not supported or data.get('observation_only') is not True):
            raise RelayPermanentError('The gateway did not confirm the activity-only observation claim.')
        self.supports_activity_observer = supported
        operation = data.get('operation')
        if not claim and operation is not None:
            raise RelayPermanentError('Relay gateway returned work to a heartbeat-only request.')
        delay = data.get('poll_after_ms', 250)
        if isinstance(delay, bool) or not isinstance(delay, (int, float)) or not math.isfinite(delay):
            raise RelayPermanentError('Relay gateway returned an invalid poll interval.')
        operation = Operation.from_wire(operation, data['server_time_ms']) if operation is not None else None
        if operation is not None:
            # A delayed response must not grant extra execution time. Using
            # the poll start conservatively includes server wait plus transit;
            # this can expire work early, but cannot extend the server deadline.
            operation = replace(operation, deadline=poll_started +
                                (operation.expires_at_ms - data['server_time_ms']) / 1000)
        return operation, max(.25, min(5, delay / 1000))

    async def submit(self, operation, result_json):
        if len(result_json.encode('utf-8')) > MAX_RESULT_BYTES:
            raise RelayPermanentError('Relay result exceeds the gateway byte limit.')
        data = await self._post('/device/result', _result_payload(self.config.device_id, operation, result_json))
        if data.get('ok') is not True or data.get('operation_id') != operation.operation_id or data.get('status') != 'completed':
            raise RelayPermanentError('Relay gateway did not acknowledge the exact uploaded operation result.')


class RelayPump:
    def __init__(self, config, journal, gateway, session, catalog, diagnostics=None):
        self.config = config; self.journal = journal; self.gateway = gateway
        self.session = session; self.catalog = catalog
        self.diagnostics = diagnostics
        self.worker_lost = False; self.gateway_error = None
        self._observer_active = False
        self._pending_observation_id = None

    async def _heartbeat(self):
        observe = getattr(self.gateway, 'supports_activity_observer', False) and OBSERVATION_TOOL in self.catalog and (
            self.config.allowed_tools is None or OBSERVATION_TOOL in self.config.allowed_tools)
        send_hint = getattr(self.gateway, 'heartbeat_hint', None)
        # The V2 transport can send a heartbeat without consuming a WebSocket
        # frame meant for the foreground completion. Keep v1 polling unchanged.
        hint_interval = getattr(self.gateway, 'heartbeat_interval', 5) if callable(send_hint) else 5
        if (not isinstance(hint_interval,(int,float)) or isinstance(hint_interval,bool)
                or not math.isfinite(hint_interval) or not .01 <= hint_interval <= 30):
            hint_interval = 5
        while True:
            await anyio.sleep(OBSERVER_POLL_SECONDS if observe else hint_interval)
            try:
                if observe:
                    if self._pending_observation_id:
                        await self.flush(operation_id=self._pending_observation_id)
                        self._pending_observation_id = None
                    operation, _ = await self.gateway.poll(observation_only=True)
                    if operation is not None:
                        # One bounded observer runs without another heartbeat.
                        await self.observe(operation)
                else:
                    if callable(send_hint):
                        await send_hint()
                    else:
                        await self.gateway.poll(claim=False)
            except RelayPermanentError as exc:
                safe_record(self.diagnostics, 'relay', 'permanent_failure')
                self.gateway_error = exc
                return
            except RelayTransientError:
                # Retain the original result; uploads never replay worker work.
                safe_record(self.diagnostics, 'relay', 'connection_interrupted')

    def _prepare(self, operation):
        row = self.journal.remember(operation)
        if row['state'] == 'undeliverable':
            # A retired cloud ID remains a local execution tombstone even if it
            # reappears after restart or after its original payload was pruned.
            return False
        if row['state'] in ('ready', 'delivered'):
            if row['result_json'] is None:
                self.journal.complete(operation.operation_id, _encoded(error_result('result_expired',
                    'This operation was already completed and its full result was retired. It will not be executed again.', operation.operation_id), MAX_RESULT_BYTES))
            elif row['state'] == 'delivered':
                self.journal.complete(operation.operation_id, row['result_json'])
            return False
        if row['state'] == 'executing':
            safe_record(self.diagnostics, 'relay', 'outcome_unknown')
            self.journal.complete(operation.operation_id, _encoded(error_result('outcome_unknown',
                'This operation was already dispatched. Inspect the worker before any new attempt.', operation.operation_id), MAX_RESULT_BYTES))
            return False
        request = operation.request
        name, arguments = request['name'], request['arguments']
        reason = None
        if time.monotonic() >= operation.deadline:
            reason = ('operation_expired', 'The gateway operation expired before local dispatch. Nothing was executed.')
        elif name not in self.catalog or (self.config.allowed_tools is not None and name not in self.config.allowed_tools):
            reason = ('tool_forbidden', 'The requested tool is outside the paired worker catalog or local relay allowlist.')
        else:
            try:
                jsonschema.Draft202012Validator(self.catalog[name]).validate(arguments)
            except (jsonschema.ValidationError, jsonschema.SchemaError, ValueError, TypeError, RecursionError):
                reason = ('invalid_arguments', 'The requested tool arguments do not match the paired worker schema.')
        if reason:
            safe_record(self.diagnostics, 'relay', 'worker_rejected', name)
            self.journal.complete(operation.operation_id, _encoded(error_result(*reason, operation.operation_id), MAX_RESULT_BYTES))
            return False
        self.journal.mark_executing(operation.operation_id)
        return True

    async def _execute_once(self, operation, observation_only=False):
        name, arguments = operation.request['name'], operation.request['arguments']
        timeout = min(self.config.tool_timeout, OBSERVER_TIMEOUT_SECONDS) if observation_only else self.config.tool_timeout
        try:
            with anyio.fail_after(timeout):
                result = await self.session.call_tool(name, arguments, read_timeout_seconds=timeout)
            result = result.model_dump(by_alias=True, exclude_none=True) if hasattr(result, 'model_dump') else result
            if isinstance(result, dict) and result.get('isError') is True:
                safe_record(self.diagnostics, 'relay', 'worker_rejected', name)
            try:
                encoded = _encoded(result, MAX_RESULT_BYTES)
            except RelayPermanentError:
                encoded = _encoded(error_result('result_too_large',
                    'The action returned a result exceeding the relay byte limit. It was not repeated; inspect the worker for its outcome.', operation.operation_id), MAX_RESULT_BYTES)
        except anyio.get_cancelled_exc_class():
            if observation_only:
                # Primary completion cancels its heartbeat. Retain a terminal
                # read outcome so the main flush can deliver it without replay.
                encoded = _encoded(error_result('observation_interrupted',
                    'The activity observation was interrupted. Its original operation was not repeated. Request a fresh observation explicitly if needed.', operation.operation_id), MAX_RESULT_BYTES)
                self.journal.complete(operation.operation_id,
                                      _deliverable_result(self.config.device_id, operation, encoded))
            raise
        except MCPError as exc:
            unknown = exc.code in (types.REQUEST_TIMEOUT, types.CONNECTION_CLOSED)
            if not observation_only:
                self.worker_lost = unknown
            safe_record(self.diagnostics, 'relay', 'outcome_unknown' if unknown else 'worker_rejected', name)
            encoded = _encoded(error_result('outcome_unknown' if unknown else 'worker_rejected',
                'Worker response was lost. The action may have completed; inspect the worker before any new attempt.' if unknown else
                'The local MCP worker rejected this request. The relay will not repeat it.', operation.operation_id), MAX_RESULT_BYTES)
        except Exception:
            if not observation_only:
                self.worker_lost = True
            safe_record(self.diagnostics, 'relay', 'outcome_unknown', name)
            encoded = _encoded(error_result('outcome_unknown',
                'Worker connection failed or timed out during dispatch. The action may have completed. Inspect the worker before any new attempt.', operation.operation_id), MAX_RESULT_BYTES)
        # Primary cancellation keeps its existing unknown-outcome semantics.
        self.journal.complete(operation.operation_id,
                              _deliverable_result(self.config.device_id, operation, encoded))

    async def observe(self, operation):
        # Reject a different tool before touching any existing journal identity.
        if operation.request['name'] != OBSERVATION_TOOL:
            raise RelayPermanentError('The observer lane returned a non-activity operation. Nothing was dispatched.')
        if self._observer_active:
            raise RelayPermanentError('An activity observation is already in flight.')
        self._observer_active = True
        try:
            self._pending_observation_id = operation.operation_id
            if self._prepare(operation):
                await self._execute_once(operation, observation_only=True)
            await self.flush(operation_id=operation.operation_id)
            self._pending_observation_id = None
        finally:
            self._observer_active = False

    async def handle(self, operation):
        if not self._prepare(operation):
            return
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(self._heartbeat)
            await self._execute_once(operation)
            tasks.cancel_scope.cancel()
        if self.gateway_error:
            raise self.gateway_error

    async def flush(self, operation_id=None):
        for operation, result_json in self.journal.pending(operation_id):
            # Older versions could persist a valid result whose escaped upload
            # envelope exceeded the wire limit. Retire that unsendable response
            # durably before retrying transport, without repeating device work.
            deliverable = _deliverable_result(self.config.device_id, operation, result_json)
            if deliverable != result_json:
                self.journal.complete(operation.operation_id, deliverable)
                result_json = deliverable
            try:
                await self.gateway.submit(operation, result_json)
            except RelayMissingOperation:
                # Only an authenticated, exact operation_not_found response
                # permits local retirement. Other protocol failures still stop
                # the pump. Retirement never acknowledges or repeats an action.
                self.journal.undeliverable(operation.operation_id)
                safe_record(self.diagnostics, 'relay', 'result_undeliverable')
                LOGGER.warning('RDC relay operation %s is undeliverable: the gateway no longer retains its identity. '
                               'Its original outcome remains local within the retention bound; inspect the worker '
                               'before another attempt. The action was not repeated.', operation.operation_id)
                continue
            except RelayTransientError:
                safe_record(self.diagnostics, 'relay', 'result_upload_retry')
                raise
            self.journal.delivered(operation.operation_id)
            safe_record(self.diagnostics, 'relay', 'result_uploaded')
        self.journal.prune_results()


@contextmanager
def _relay_lock(directory):
    try:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = directory.stat()
        if directory.is_symlink() or not stat.S_ISDIR(info.st_mode) or (os.name != 'nt' and (info.st_uid != os.getuid() or info.st_mode & 0o077)):
            raise ValueError
        fd = os.open(directory / 'relay.lock', os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0), 0o600)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            os.close(fd); raise ValueError
        if os.name == 'nt':
            import msvcrt
            if info.st_size == 0:
                os.write(fd, b'0'); os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, ValueError):
        if 'fd' in locals():
            try: os.close(fd)
            except OSError: pass
        raise RelayPermanentError('Relay state must be private, and only one relay pump may use it at a time.') from None
    try:
        yield
    finally:
        if os.name == 'nt':
            import msvcrt
            os.lseek(fd, 0, os.SEEK_SET); msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


@asynccontextmanager
async def _worker_session(config, token):
    # Allow the complete tool deadline while also bounding SDK session DELETE
    # during shutdown/reconnect. Legacy idle GET streams may reconnect safely;
    # no tool invocation is retried by this socket deadline.
    async with httpx2.AsyncClient(headers={'Authorization': 'Bearer ' + token}, trust_env=False,
        follow_redirects=False, timeout=httpx2.Timeout(15, read=config.tool_timeout + 1), verify=True) as client:
        async with streamable_http_client(config.worker_url, http_client=client, max_sse_event_size=MAX_WIRE_BYTES) as streams:
            async with ClientSession(*streams, read_timeout_seconds=config.tool_timeout) as session:
                with anyio.fail_after(15):
                    try:
                        await session.discover()
                    except MCPError as exc:
                        if exc.code not in (types.METHOD_NOT_FOUND, types.UNSUPPORTED_PROTOCOL_VERSION):
                            raise
                        await session.initialize()
                    catalog = {}; cursor = None
                    for _ in range(8):
                        page = await session.list_tools(params=types.PaginatedRequestParams(cursor=cursor) if cursor else None)
                        for tool in page.tools:
                            if not TOOL_NAME.fullmatch(tool.name) or tool.name in catalog:
                                raise RelayPermanentError('The local worker returned an invalid or repeated RDC tool name.')
                            catalog[tool.name] = tool.input_schema
                        if len(catalog) > 256:
                            raise RelayPermanentError('The local worker catalog exceeds the relay limit.')
                        cursor = page.next_cursor
                        if not cursor:
                            break
                    if cursor or 'rdc_system_status' not in catalog:
                        raise RelayPermanentError('The worker is not a compatible bounded RDC MCP server.')
                    _encoded(catalog, 1024 * 1024)
                    identity = await session.call_tool('rdc_system_status', {})
                    data = identity.structured_content
                    if not isinstance(data, dict) or data.get('ok') is False or data.get('device_id') != config.device_id:
                        raise RelayPermanentError('The local worker identity differs from the configured paired device.')
                yield session, catalog


def _idle_poll_sleep(poll_delay, idle_delay, elapsed):
    """Credit genuine gateway long-poll time against BOTH idle minimums.

    If a bounded server wait already consumed the maximum idle backoff,
    immediately issue the next authenticated claim. Immediate/short empty
    results still obey the remote minimum and local exponential backoff.
    No device operation is reissued by this scheduling decision.
    """
    return max(0.0, max(poll_delay, idle_delay) - elapsed)


def _permanent(exc):
    if isinstance(exc, RelayPermanentError):
        return exc
    for nested in getattr(exc, 'exceptions', ()):
        result = _permanent(nested)
        if result is not None:
            return result
    return None


async def _run_relay(config_path, state_dir, *, stop_event=None, diagnostics=None):
    """CLI entry: ``anyio.run(run_relay, private_config_path, worker_state_dir)``.

    No listener is opened. Transport reconnects preserve operation identities;
    result uploads retry, uncertain tool invocations never do. Ctrl+C closes only
    these client connections, leaving the worker and its workflows alive.
    """
    config = RelayConfig.load(config_path)
    try:
        token = _private_bytes(Path(state_dir).expanduser() / 'agent-token', 1024).decode('ascii').strip()
    except (UnicodeError, ValueError):
        raise RelayPermanentError('The worker agent credential is invalid.') from None
    if not _secret(token, minimum=40, maximum=1024):
        raise RelayPermanentError('The worker agent credential is invalid.')
    directory = Path(state_dir).expanduser().absolute() / 'relay'
    with _relay_lock(directory):
        journal = Journal(directory / 'relay.sqlite3', config.binding)
        try:
            journal.recover(diagnostics)
            async with httpx2.AsyncClient(trust_env=False, follow_redirects=False, verify=True,
                timeout=httpx2.Timeout(15, connect=5, pool=5)) as client:
                gateway = Gateway(config, client)
                delay = .5
                interrupted = False
                while stop_event is None or not stop_event.is_set():
                    try:
                        if interrupted:
                            safe_record(diagnostics, 'relay', 'reconnect_attempt')
                        # Deliver previously recorded outcomes even while the
                        # local MCP worker is temporarily unavailable.
                        await RelayPump(config, journal, gateway, None, {}, diagnostics).flush()
                        async with _worker_session(config, token) as (session, catalog):
                            pump = RelayPump(config, journal, gateway, session, catalog, diagnostics)
                            delay = .5
                            idle_delay = .25
                            while stop_event is None or not stop_event.is_set():
                                await pump.flush()
                                if pump.worker_lost:
                                    raise RelayTransientError('Local worker connection ended; uncertain actions will not be replayed.')
                                poll_started = time.monotonic()
                                operation, poll_delay = await gateway.poll()
                                poll_elapsed = time.monotonic() - poll_started
                                if interrupted:
                                    safe_record(diagnostics, 'relay', 'reconnected')
                                    interrupted = False
                                if operation is not None:
                                    idle_delay = .25
                                    await pump.handle(operation)
                                else:
                                    # A genuine long poll has already provided
                                    # backoff. Do not impose another 250ms gap
                                    # before the next claim. Immediate/short
                                    # empty responses retain bounded throttling.
                                    gap = _idle_poll_sleep(poll_delay, idle_delay, poll_elapsed)
                                    if gap > 0:
                                        await anyio.sleep(gap)
                                    idle_delay = min(5, idle_delay * 2)
                    except Exception as exc:
                        fatal = _permanent(exc)
                        if fatal is not None:
                            raise RelayPermanentError(str(fatal)) from None
                        # Transport exception groups can embed credentials and
                        # payloads. Neither their repr nor their text is logged.
                        interrupted = True
                        safe_record(diagnostics, 'relay', 'connection_interrupted')
                        LOGGER.warning('RDC relay connection interrupted. Retained results will retry; uncertain actions will not replay.')
                        await anyio.sleep(delay)
                        delay = min(15, delay * 2)
        finally:
            journal.close()


async def run_relay(config_path, state_dir, *, stop_event=None):
    """Run the existing relay with best-effort private diagnostics only."""
    try:
        diagnostics = Diagnostics(state_dir)
    except Exception:
        diagnostics = None
    try:
        return await _run_relay(config_path, state_dir, stop_event=stop_event, diagnostics=diagnostics)
    except Exception as exc:
        if _permanent(exc) is not None:
            safe_record(diagnostics, 'relay', 'permanent_failure')
        raise
    finally:
        try:
            if diagnostics is not None:
                diagnostics.close()
        except Exception:
            pass
