"""Opt-in RDC 2.0 event-driven device relay.

This module is independent from the installed polling relay. It reuses the
existing worker permissions and durable local execution journal, while using
one private authenticated WebSocket for claims, heartbeats and exact result
acknowledgments. No operation is retried after an uncertain outcome.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from pathlib import Path
import time
from urllib.parse import urlsplit, urlunsplit

from .relay import (
    Journal, Operation, RelayConfig, RelayError, RelayPermanentError,
    RelayTransientError, RelayPump, _encoded, _json, _private_bytes, _secret,
    _relay_lock, _worker_session, error_result, validate_gateway_url,
)

LOGGER = logging.getLogger(__name__)
MAX_V2_FRAME_BYTES = 1_572_864
MAX_V2_RESULT_BYTES = 262_144
MAX_V2_IDLE_WAIT_SECONDS = 15.0


def v2_socket_url(gateway_url: str) -> str:
    """Use the exact previously validated HTTPS owner Site, never a redirect."""
    parts = urlsplit(validate_gateway_url(gateway_url))
    return urlunsplit(('wss', parts.netloc, '/v2/device/socket', '', ''))


class V2SocketGateway:
    """A single original-work WebSocket with bounded event-driven reads."""

    supports_activity_observer = False

    def __init__(self, socket, *, wait_timeout: float = MAX_V2_IDLE_WAIT_SECONDS):
        if not 0 < wait_timeout <= MAX_V2_IDLE_WAIT_SECONDS:
            raise ValueError('V2 idle wait must be between zero and fifteen seconds.')
        self.socket = socket
        self.wait_timeout = wait_timeout

    async def _send(self, data: dict):
        try:
            frame = _encoded({'version': 2, **data}, MAX_V2_FRAME_BYTES)
            await self.socket.send(frame)
        except RelayError:
            raise
        except Exception:
            raise RelayTransientError('RDC 2.0 socket send was interrupted; no worker action will be replayed.') from None

    async def _receive(self):
        try:
            data = await asyncio.wait_for(self.socket.recv(), self.wait_timeout)
        except TimeoutError:
            return None
        except asyncio.CancelledError:
            raise
        except Exception:
            raise RelayTransientError('RDC 2.0 socket disconnected; original operation status must be recovered.') from None
        if not isinstance(data, str) or len(data.encode('utf-8')) > MAX_V2_FRAME_BYTES:
            raise RelayPermanentError('RDC 2.0 received an invalid or oversized gateway frame.')
        try:
            frame = _json(data)
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise RelayPermanentError('RDC 2.0 gateway frame is malformed.') from None
        if not isinstance(frame, dict) or frame.get('version') != 2 or not isinstance(frame.get('type'), str):
            raise RelayPermanentError('RDC 2.0 gateway frame has an invalid protocol version.')
        if frame['type'] in ('operation_error', 'protocol_error'):
            raise RelayPermanentError('RDC 2.0 gateway rejected an original operation; no automatic replay.')
        if frame['type'] not in ('claimed', 'work_available', 'result_ack',
                                 'result_available', 'heartbeat_ack'):
            raise RelayPermanentError('RDC 2.0 gateway sent an unknown frame.')
        return frame

    @staticmethod
    def _claimed(frame):
        data = frame.get('operation')
        if data is None:
            return None
        if not isinstance(data, dict):
            raise RelayPermanentError('RDC 2.0 claimed operation shape is invalid.')
        try:
            wire = {
                'operation_id': data['id'], 'claim_id': data['claimId'],
                'request_json': data['requestJson'],
                'request_sha256': data['requestDigest'],
                'expires_at_ms': data['expiresAtMs'],
            }
            server_time_ms = data['serverTimeMs']
            return Operation.from_wire(wire, server_time_ms)
        except (KeyError, TypeError, ValueError, RecursionError):
            raise RelayPermanentError('RDC 2.0 returned a malformed claimed operation.') from None

    async def poll(self, claim=True, observation_only=False):
        if observation_only:
            raise RelayPermanentError('RDC 2.0 has no unverified activity-observer lane.')
        if not claim:
            await self._send({'type': 'heartbeat'})
            while True:
                frame = await self._receive()
                if frame is None:
                    raise RelayTransientError('RDC 2.0 device heartbeat acknowledgment timed out.')
                if frame['type'] == 'heartbeat_ack':
                    return None, 0
                # Unsolicited work or result hints never authorize a claim
                # from the heartbeat-only lane.
        await self._send({'type': 'claim'})
        awaiting_claim = True
        noticed_while_claiming = False
        while True:
            frame = await self._receive()
            if frame is None:
                # This is an application heartbeat. The primary operation
                # claim remains event-driven, without a periodic DB query.
                await self._send({'type': 'heartbeat'})
                continue
            kind = frame['type']
            if kind == 'heartbeat_ack' or kind == 'result_available':
                continue
            if kind == 'work_available':
                if awaiting_claim:
                    noticed_while_claiming = True
                else:
                    await self._send({'type': 'claim'})
                    awaiting_claim = True
                continue
            if kind == 'claimed':
                operation = self._claimed(frame)
                if operation is not None:
                    return operation, 0
                awaiting_claim = False
                if noticed_while_claiming:
                    noticed_while_claiming = False
                    await self._send({'type': 'claim'})
                    awaiting_claim = True
                continue
            raise RelayPermanentError('RDC 2.0 received an unexpected claim response.')

    async def submit(self, operation: Operation, result_json: str):
        if not isinstance(result_json, str):
            raise RelayPermanentError('RDC 2.0 result must have a valid JSON body.')
        if len(result_json.encode('utf-8')) > MAX_V2_RESULT_BYTES:
            # Bound cloud payload size while retaining the original local
            # outcome in its durable outbox for owner recovery.
            result_json = _encoded(error_result(
                'result_too_large',
                'RDC 2.0 result exceeds the private transport size limit. Inspect the local original output.',
                operation.operation_id), MAX_V2_RESULT_BYTES)
        await self._send({
            'type': 'complete', 'id': operation.operation_id,
            'claimId': operation.claim_id,
            'requestDigest': operation.request_sha256,
            'resultJson': result_json,
            'resultDigest': hashlib.sha256(result_json.encode('utf-8')).hexdigest(),
        })
        while True:
            frame = await self._receive()
            if frame is None:
                raise RelayTransientError('RDC 2.0 result acknowledgment was lost; only original upload may retry.')
            if frame['type'] in ('result_available', 'heartbeat_ack', 'work_available'):
                continue
            if frame['type'] == 'result_ack':
                if frame.get('id') != operation.operation_id or type(frame.get('duplicate')) is not bool:
                    raise RelayPermanentError('RDC 2.0 result acknowledgment identity differs from original.')
                return
            raise RelayPermanentError('RDC 2.0 received an invalid completion acknowledgment.')


async def run_relay_v2(config_path, state_dir, *, stop_event=None):
    """Run the explicit V2 relay only; never start/stop an installed v1 relay.

    Acquires the exact same exclusive relay lock as v1, which prevents both
    transports from consuming the device concurrently. V2 uses a separate
    durable inbox/outbox database and a separate cloud operation identity.
    """
    config = RelayConfig.load(config_path)
    try:
        token = _private_bytes(Path(state_dir).expanduser() / 'agent-token', 1024).decode('ascii').strip()
    except (UnicodeError, ValueError):
        raise RelayPermanentError('Local RDC agent credential is invalid.') from None
    if not _secret(token, minimum=40, maximum=1024):
        raise RelayPermanentError('Local RDC agent credential is invalid.')

    try:
        from websockets.asyncio.client import connect
    except ImportError:
        raise RelayPermanentError('RDC 2.0 requires the separately installed optional websockets dependency.') from None

    state_dir = Path(state_dir).expanduser().absolute()
    directory = state_dir / 'relay'
    with _relay_lock(directory):
        binding = hashlib.sha256(('rdc2:' + config.binding).encode()).hexdigest()
        journal = Journal(directory / 'relay-v2.sqlite3', binding)
        try:
            journal.recover()
            delay = .5
            while stop_event is None or not stop_event.is_set():
                try:
                    headers = {
                        'OAI-Sites-Authorization': 'Bearer ' + config.sites_service_token,
                        'X-RDC-Device-Key': config.device_key,
                    }
                    async with connect(v2_socket_url(config.gateway_url),
                        additional_headers=headers, proxy=None, compression=None,
                        open_timeout=10, ping_interval=20, ping_timeout=20,
                        max_size=MAX_V2_FRAME_BYTES, max_queue=16,
                        close_timeout=5) as socket:
                        gateway = V2SocketGateway(socket)
                        # Explicit liveness before owner cloud admission.
                        await gateway.poll(claim=False)
                        # Preserve original stored result across any reconnect.
                        await RelayPump(config,journal,gateway,None,{}).flush()
                        async with _worker_session(config,token) as (session,catalog):
                            pump=RelayPump(config,journal,gateway,session,catalog)
                            delay=.5
                            while stop_event is None or not stop_event.is_set():
                                await pump.flush()
                                operation,_ = await gateway.poll()
                                if operation is None:
                                    continue
                                await pump.handle(operation)
                                if pump.worker_lost:
                                    raise RelayTransientError('Local worker connection was lost; no action replay.')
                                await pump.flush()
                except asyncio.CancelledError:
                    raise
                except RelayPermanentError:
                    raise
                except Exception:
                    LOGGER.warning('RDC 2.0 socket interrupted; recovering original durable results without replay.')
                    await asyncio.sleep(delay)
                    delay=min(15,delay*2)
        finally:
            journal.close()
