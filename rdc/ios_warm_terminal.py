"""Private qualification adapter for an authenticated, already provisioned USB session.

No worker catalog entry or app launch is added here. The owner explicitly provisions
the separate development companion and supplies its fixed USB transport. Both warm
and cold commands share DirectTerminal's durable per-device unknown-outcome fence.
"""
from __future__ import annotations
import asyncio
import hashlib
import inspect
import json
import os
from pathlib import Path
import stat
import threading
import time

from .ios_direct_terminal import DirectTerminal, _error, valid_id
from .ios_warm_terminal_codec import (
    BUNDLE_ID, RequestIdentity, canonical_json, legacy_receipt, make_request,
    validate_identity,
)

WARM_COMPANION = BUNDLE_ID
MAX_SESSION_REQUESTS = 64
_MAPPING_FIELDS = {'schema','device','session_id','request_id','sequence',
                   'command_sha256','request_sha256'}

class WarmDirectTerminal(DirectTerminal):
    companion = WARM_COMPANION

    def __init__(self, settings, profiles, transport):
        if transport is None:
            _error('direct_terminal_unavailable')
        super().__init__(settings, profiles, transport)
        self.enabled = self.enabled and getattr(settings, 'ios_warm_terminal_enabled', False) is True

    @staticmethod
    def _base(record):
        return DirectTerminal._base(record) | {'command_route': 'mobile_sandbox_warm_usb'}


class WarmSessionTransport:
    """Serial synchronous bridge retaining one asyncio loop and USB connection.

    A fresh attachment is consumed durably before connecting. Restarted attachments
    are explicitly read-only. Secrets remain caller-owned memory; private mappings
    contain hashes and identities, never commands, output or keys.
    """
    def __init__(self, state_dir, udid, session_id, secret, session_expires_at_ms,
                 usb, *, fresh_session=False):
        if (not valid_id(session_id) or type(secret) is not bytes or len(secret) != 32
                or type(session_expires_at_ms) is not int
                or not isinstance(udid, str) or not udid):
            raise ValueError('warm_session_configuration_invalid')
        if getattr(usb, 'binding', None) != (udid, session_id, session_expires_at_ms):
            raise ValueError('warm_usb_binding_mismatch')
        self._assert_sync_context()
        self.root = Path(state_dir) / 'warm-terminal-v1'
        self.udid = udid
        self.device = hashlib.sha256(('ios:' + udid.casefold()).encode()).hexdigest()
        self.session_id = session_id
        self._secret = secret
        self.expiry = session_expires_at_ms
        self.usb = usb
        self._fresh = fresh_session is True
        self._next = 1
        self._attempted = False
        self._usb_open_attempted = False
        self._ready = False
        self._closed = False
        self._deadline = 0.0
        self._runner = asyncio.Runner()
        self._lock = threading.RLock()

    def _directory(self):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        info = os.fstat(fd)
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077):
            os.close(fd)
            raise OSError('warm_private_directory_invalid')
        return fd

    def _write_once(self, leaf, value):
        raw = canonical_json(value)
        if len(raw) > 2048:
            raise OSError('warm_private_record_too_large')
        directory = self._directory()
        fd = None
        try:
            fd = os.open(leaf, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=directory)
            offset = 0
            for _ in range(64):
                if offset == len(raw):
                    break
                written = os.write(fd, raw[offset:])
                if written <= 0:
                    raise OSError('warm_private_write_failed')
                offset += written
            if offset != len(raw):
                raise OSError('warm_private_write_incomplete')
            os.fsync(fd)
            os.close(fd)
            fd = None
            os.fsync(directory)
        finally:
            if fd is not None:
                os.close(fd)
            os.close(directory)

    def _read_private(self, leaf):
        directory = self._directory()
        fd = None
        try:
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or info.st_nlink != 1 or info.st_mode & 0o077
                    or not 0 < info.st_size <= 2048):
                raise OSError('warm_private_record_invalid')
            raw = os.read(fd, 2049)
            if len(raw) != info.st_size:
                raise OSError('warm_private_record_incomplete')
            value = json.loads(raw)
            if canonical_json(value) != raw:
                raise OSError('warm_private_record_noncanonical')
            return value
        finally:
            if fd is not None:
                os.close(fd)
            os.close(directory)

    @staticmethod
    def _assert_sync_context():
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        raise OSError('warm_sync_worker_required')

    def _run(self, coroutine, timeout=4.0):
        try:
            self._assert_sync_context()
            if self._closed:
                raise OSError('warm_connection_closed')
        except BaseException:
            coroutine.close()
            raise
        bounded = asyncio.wait_for(coroutine, timeout)
        try:
            return self._runner.run(bounded)
        except BaseException:
            if inspect.getcoroutinestate(bounded) == inspect.CORO_CREATED:
                bounded.close()
                coroutine.close()
            raise

    def open(self):
        self._assert_sync_context()
        with self._lock:
            if self._attempted or self._closed:
                raise OSError('warm_open_already_attempted')
            self._attempted = True
            try:
                marker = {'schema':1, 'session_id':self.session_id,
                          'device':self.device, 'bundle_id':WARM_COMPANION}
                leaf = 'session-' + self.session_id + '.activation'
                if self._fresh:
                    self._write_once(leaf, marker)
                elif self._read_private(leaf) != marker:
                    raise OSError('warm_recovery_attachment_invalid')
                self._usb_open_attempted = True
                ready = self._run(self.usb.open(), timeout=17.0)
                if (ready.get('session_id') != self.session_id
                        or ready.get('expires_at_ms') != self.expiry
                        or ready.get('bundle_id') != WARM_COMPANION
                        or ready.get('next_sequence') != 1
                        or ready.get('status') != 'ready'):
                    raise OSError('warm_ready_binding_invalid')
                remaining = (self.expiry - int(time.time() * 1000)) / 1000
                if remaining > 600 or (self._fresh and remaining <= 0):
                    raise OSError('warm_session_expiry_invalid')
                self._deadline = time.monotonic() + max(0, remaining)
                self._ready = True
            except BaseException:
                try:
                    self.close()
                except Exception:
                    pass
                raise

    def preflight(self, udid):
        with self._lock:
            return (self._ready and not self._closed and self._fresh and udid == self.udid
                    and self._next <= MAX_SESSION_REQUESTS
                    and time.monotonic() < self._deadline
                    and int(time.time() * 1000) < self.expiry)

    def _publish_mapping(self, identity):
        validate_identity(identity)
        if identity.session_id != self.session_id or identity.sequence != self._next:
            raise OSError('warm_mapping_binding_invalid')
        value = {'schema':1, 'device':self.device,
                 **{key:getattr(identity, key) for key in
                    ('session_id','request_id','sequence','command_sha256','request_sha256')}}
        self._write_once('request-' + identity.request_id + '.json', value)
        self._next += 1

    def submit(self, udid, payload):
        self._assert_sync_context()
        with self._lock:
            if not self.preflight(udid):
                raise OSError('warm_submission_unavailable')
            now = int(time.time() * 1000)
            request = make_request(self._secret, session_id=self.session_id,
                request_id=payload['request_id'], sequence=self._next,
                expires_at_ms=min(now + 15_000, self.expiry), command=payload['command'],
                now_ms=now, session_expires_at_ms=self.expiry)
            if request.identity.command_sha256 != payload['command_sha256']:
                raise OSError('warm_command_digest_mismatch')
            async def before_mutation(identity):
                self._publish_mapping(identity)
            try:
                self._run(self.usb.submit(request, before_mutation=before_mutation))
            except BaseException:
                # The durable parent journal owns the unknown-outcome fence.
                self._fresh = False
                raise

    def read(self, udid, request_id):
        self._assert_sync_context()
        with self._lock:
            if not self._ready or self._closed or udid != self.udid or not valid_id(request_id):
                raise OSError('warm_recovery_unavailable')
            value = self._read_private('request-' + request_id + '.json')
            if (type(value) is not dict or set(value) != _MAPPING_FIELDS
                    or type(value['schema']) is not int or value['schema'] != 1
                    or value['device'] != self.device or value['session_id'] != self.session_id
                    or value['request_id'] != request_id):
                raise OSError('warm_mapping_invalid')
            identity = RequestIdentity(**{key:value[key] for key in
                ('session_id','request_id','sequence','command_sha256','request_sha256')})
            validate_identity(identity)
            async def receive():
                deadline = time.monotonic() + 1.0
                for _ in range(40):
                    result = await self.usb.read(identity)
                    if result is not None:
                        return legacy_receipt(result)
                    if time.monotonic() >= deadline:
                        break
                    await asyncio.sleep(.025)
                return None
            return self._run(receive(), timeout=2.0)

    def close(self):
        self._assert_sync_context()
        with self._lock:
            if self._closed:
                return
            try:
                if self._usb_open_attempted:
                    self._run(self.usb.close(), timeout=4.0)
            finally:
                self._ready = False
                self._fresh = False
                self._closed = True
                self._secret = b''
                self._runner.close()
