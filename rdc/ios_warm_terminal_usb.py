"""Private bounded USB mailbox transport.

Importing this module performs no device access and imports no pymobiledevice3
module. The real connection factory is invoked only by explicit open().
The root adapter owns its existing durable journal and per-device unknown fence.
There is no public execute route, network listener, reconnect loop or replay loop.
"""
from __future__ import annotations

import asyncio
import hashlib
import importlib.metadata
import re
import struct
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from .ios_warm_terminal_codec import (
    BUNDLE_ID, MAX_ENVELOPE_BYTES, MAX_SAFE_INTEGER, MAX_SESSION_REQUESTS,
    RequestIdentity, SignedRequest, WireError, canonical_uuid, mailbox_leaf,
    open_ready, open_receipt, open_request, validate_identity,
)

PINNED_PMD3_VERSION = "11.63.1"
PINNED_SOURCE_SHA256 = {
    "services/afc.py": "dba7dfed8461a0c408fe6e0b5de02206f22aeb465d677b419ce76a5147103350",
    "services/house_arrest.py": "d74657411a33360bb3096f979fff3e1261a87b27a46f08a0d38ee796bca8990b",
    "services/lockdown_service.py": "3fe1e4720c6348a6abc524286afe229c3a1515f31707e6e654d9e2b179977e3b",
    "service_connection.py": "acbf8e6e70ebff16a061838340aa7f045a190df784c328490907fa19964e6f89",
    "lockdown.py": "b6bd674eb73d2b2698270f801a685a574c6f399464c8c9ba629ac9af0ccf72a4",
}
MAX_AFC_BODY_BYTES = 32 * 1024
MAX_AFC_PACKET_BYTES = MAX_AFC_BODY_BYTES + 40
MAX_IPC_FRAME_BYTES = 32 * 1024
IO_CHUNK_BYTES = 16 * 1024
OPEN_TIMEOUT_SECONDS = 15.0
IO_TIMEOUT_SECONDS = 5.0
CLOSE_TIMEOUT_SECONDS = 1.5
_UDID = re.compile(r"[A-Fa-f0-9-]{16,64}\Z")


class TransportError(RuntimeError):
    """Stable public code; raw device exceptions and payloads stay private."""

    def __init__(self, code: str, *, mutation_attempted: bool = False):
        super().__init__(code)
        self.code = code
        self.mutation_attempted = mutation_attempted


@dataclass(frozen=True, repr=False)
class FixedTarget:
    udid: str
    session_id: str

    def __post_init__(self) -> None:
        if type(self.udid) is not str or _UDID.fullmatch(self.udid) is None:
            raise TransportError("target_invalid")
        canonical_uuid(self.session_id)


@dataclass(repr=False)
class ConnectionBundle:
    afc: Any
    lockdown: Any
    missing_errors: tuple[type[Exception], ...] = (FileNotFoundError,)


ConnectionFactory = Callable[[FixedTarget], Awaitable[ConnectionBundle]]
BeforeMutation = Callable[[RequestIdentity], Awaitable[None]]


class CappedAFCConnection:
    """Guard raw AFC body allocation before the pinned reader calls recvall.

    ServiceConnection.max_frame_size bounds plist frames, not raw AFC packets.
    This proxy is installed only on the already-vended, pinned House Arrest
    instance. It deliberately exposes only the methods that AFC requires.
    """

    def __init__(self, connection: Any):
        self._connection = connection

    async def recvall(self, size: int) -> bytes:
        if type(size) is not int or not 0 <= size <= MAX_AFC_BODY_BYTES:
            raise TransportError("afc_frame_size_invalid")
        data = await self._connection.recvall(size)
        if type(data) is not bytes or len(data) != size:
            raise TransportError("afc_frame_length_invalid")
        return data

    async def sendall(self, data: bytes) -> None:
        if type(data) is not bytes or not 0 < len(data) <= MAX_AFC_PACKET_BYTES:
            raise TransportError("afc_outbound_size_invalid")
        await self._connection.sendall(data)

    async def close(self) -> None:
        await self._connection.close()


def _verify_installed_source() -> None:
    """Read-only guard, evaluated only when real USB open is explicitly called."""
    if sys.implementation.name != "cpython" or sys.version_info[:2] != (3, 13):
        raise TransportError("pmd3_runtime_pin_mismatch")
    try:
        distribution = importlib.metadata.distribution("pymobiledevice3")
        if distribution.version != PINNED_PMD3_VERSION:
            raise TransportError("pmd3_version_pin_mismatch")
        for relative, expected in PINNED_SOURCE_SHA256.items():
            path = distribution.locate_file("pymobiledevice3/" + relative)
            with path.open("rb") as source:
                raw = source.read(262_145)
            if len(raw) > 262_144 or hashlib.sha256(raw).hexdigest() != expected:
                raise TransportError("pmd3_source_pin_mismatch")
    except TransportError:
        raise
    except Exception:
        raise TransportError("pmd3_source_pin_unavailable") from None


def _validate_usb_identity(lockdown: Any, target: FixedTarget) -> None:
    mux = getattr(getattr(lockdown, "service", None), "mux_device", None)
    if (
        getattr(lockdown, "paired", None) is not True
        or getattr(lockdown, "udid", None) != target.udid
        or mux is None
        or getattr(mux, "connection_type", None) != "USB"
        or getattr(mux, "serial", None) != target.udid
    ):
        raise TransportError("usb_identity_mismatch")


async def _dispose_bundle(bundle: ConnectionBundle | None) -> bool:
    """Close both owners within separate bounds; retain cleanup uncertainty."""
    if bundle is None:
        return False
    incomplete = False
    try:
        if bundle.afc is not None:
            await asyncio.wait_for(bundle.afc.aclose(), CLOSE_TIMEOUT_SECONDS)
    except BaseException:
        incomplete = True
    finally:
        try:
            if bundle.lockdown is not None:
                await asyncio.wait_for(bundle.lockdown.close(), CLOSE_TIMEOUT_SECONDS)
        except BaseException:
            incomplete = True
    return incomplete


async def pinned_usb_connection(target: FixedTarget) -> ConnectionBundle:
    """Exactly one attempt using existing pairing, exact USB, and VendDocuments."""
    _verify_installed_source()
    # These imports are intentionally deferred until the guarded explicit open.
    from pymobiledevice3.exceptions import AfcFileNotFoundError
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.house_arrest import HouseArrestService

    lockdown = None
    house = None
    try:
        lockdown = await create_using_usbmux(
            serial=target.udid, autopair=False, connection_type="USB",
        )
        _validate_usb_identity(lockdown, target)
        # The initial client setup is owned by the pinned library. Bound its
        # subsequent small control replies without a global class modification.
        lockdown.service.max_frame_size = 1024 * 1024
        house = HouseArrestService(lockdown, documents_only=True)
        await house.connect()
        if house._service is None:
            raise TransportError("house_arrest_connection_missing")
        house._service.max_frame_size = MAX_AFC_BODY_BYTES
        # Never enter AFC's async context before completing this plist exchange.
        await house.send_command(BUNDLE_ID, cmd="VendDocuments")
        house._service = CappedAFCConnection(house._service)
        return ConnectionBundle(house, lockdown, (AfcFileNotFoundError,))
    except BaseException:
        await _dispose_bundle(ConnectionBundle(house, lockdown))
        raise


def _now_milliseconds() -> int:
    return time.time_ns() // 1_000_000


class WarmUSBTransport:
    """One persistent connection with fixed targets and serialized operations.

    allow_submit defaults false. A recovery instance only reads receipts.
    Root may enable submission for its explicitly activated fresh host session.
    Ready metadata never authorizes resuming submissions after process restart.

    before_mutation must durably store request_id -> session_id, sequence,
    command_sha256, request_sha256 in the existing host journal. If it raises,
    no AFC mutation is attempted. Root retains the per-device unknown fence.
    """

    def __init__(
        self, target: FixedTarget, secret: bytes, session_expires_at_ms: int, *,
        connection_factory: ConnectionFactory | None = None,
        allow_submit: bool = False,
        now_ms: Callable[[], int] = _now_milliseconds,
    ):
        if type(target) is not FixedTarget:
            raise TransportError("target_invalid")
        if type(secret) is not bytes or len(secret) != 32:
            raise TransportError("secret_invalid")
        if (
            type(session_expires_at_ms) is not int
            or not 0 < session_expires_at_ms <= MAX_SAFE_INTEGER
            or type(allow_submit) is not bool
        ):
            raise TransportError("session_configuration_invalid")
        self._target = target
        self._secret = secret
        self._session_expiry = session_expires_at_ms
        self._factory = connection_factory or pinned_usb_connection
        self._allow_submit = allow_submit
        self._now_ms = now_ms
        self._state = "new"
        self._connection: ConnectionBundle | None = None
        self._lock = asyncio.Lock()
        self._pending: RequestIdentity | None = None
        self._used_ids: set[str] = set()
        self._used_sequences: set[int] = set()
        self._monotonic_expiry = 0.0
        self.cleanup_incomplete = False

    @property
    def binding(self) -> tuple[str, str, int]:
        """Immutable configured device/session/expiry identity for the journal bridge."""
        return (self._target.udid, self._target.session_id, self._session_expiry)

    def _path(self, kind: str, sequence: int | None = None) -> str:
        return "/Documents/" + mailbox_leaf(self._target.session_id, kind, sequence)

    def _require_open(self) -> ConnectionBundle:
        if self._state != "open" or self._connection is None:
            raise TransportError("transport_unavailable")
        return self._connection

    def _require_active_submission(self) -> None:
        self._require_open()
        if not self._allow_submit:
            raise TransportError("recovery_only")
        if (
            self._now_ms() >= self._session_expiry
            or asyncio.get_running_loop().time() >= self._monotonic_expiry
        ):
            raise TransportError("session_expired")

    async def _poison(self) -> None:
        self._state = "poisoned"
        connection, self._connection = self._connection, None
        self.cleanup_incomplete |= await _dispose_bundle(connection)

    async def open(self) -> dict[str, Any]:
        """One connection attempt and one ready read. No launch, polling or retry."""
        async with self._lock:
            if self._state != "new":
                raise TransportError("open_already_attempted")
            self._state = "opening"
            try:
                async with asyncio.timeout(OPEN_TIMEOUT_SECONDS):
                    self._connection = await self._factory(self._target)
                    _validate_usb_identity(self._connection.lockdown, self._target)
                    directory = await self._connection.afc.stat("/Documents")
                    if directory.get("st_ifmt") != "S_IFDIR":
                        raise TransportError("documents_root_invalid")
                    raw = await self._read_regular(self._path("ready"))
                    if raw is None:
                        raise TransportError("ready_missing")
                    ready = open_ready(
                        raw, self._secret,
                        expected_session_id=self._target.session_id,
                        now_ms=self._now_ms(), allow_expired=True,
                    )
                    if ready["expires_at_ms"] != self._session_expiry:
                        raise TransportError("session_expiry_mismatch")
                    # next_sequence is a permanent initial-ready value of 1.
                    # Only root's persisted journal determines current sequence.
                    remaining = max(0, self._session_expiry - self._now_ms()) / 1000
                    self._monotonic_expiry = asyncio.get_running_loop().time() + remaining
                    self._state = "open"
                    return ready
            except BaseException as exc:
                await self._poison()
                if not isinstance(exc, Exception):
                    raise
                if isinstance(exc, (TransportError, WireError)):
                    raise
                raise TransportError("usb_open_failed") from None

    async def _stat(self, path: str) -> dict[str, Any] | None:
        assert self._connection is not None
        try:
            return await self._connection.afc.stat(path)
        except self._connection.missing_errors:
            return None

    async def _read_regular(self, path: str) -> bytes | None:
        assert self._connection is not None
        afc = self._connection.afc
        metadata = await self._stat(path)
        if metadata is None:
            return None
        size = metadata.get("st_size")
        if (
            metadata.get("st_ifmt") != "S_IFREG"
            or type(metadata.get("st_nlink")) is not int
            or metadata["st_nlink"] != 1
            or type(size) is not int
            or not 0 < size <= MAX_ENVELOPE_BYTES
        ):
            raise TransportError("mailbox_file_metadata_invalid")
        # AFC supplies no O_NOFOLLOW/fstat. This type check has a check/use race.
        # Fixed paths, bounded bytes and MAC validation remain mandatory.
        handle = await afc.fopen(path, "r")
        if type(handle) is not int or handle <= 0:
            raise TransportError("afc_handle_invalid")
        try:
            parts: list[bytes] = []
            remaining = size
            while remaining:
                wanted = min(IO_CHUNK_BYTES, remaining)
                chunk = await afc.fread(handle, wanted)
                if type(chunk) is not bytes or not 0 < len(chunk) <= wanted:
                    raise TransportError("afc_file_read_size_invalid")
                parts.append(chunk)
                remaining -= len(chunk)
            return b"".join(parts)
        finally:
            await asyncio.wait_for(afc.fclose(handle), CLOSE_TIMEOUT_SECONDS)

    async def _write_regular(self, path: str, data: bytes) -> None:
        assert self._connection is not None
        if type(data) is not bytes or not 0 < len(data) <= MAX_ENVELOPE_BYTES:
            raise TransportError("request_size_invalid")
        afc = self._connection.afc
        handle = await afc.fopen(path, "w")
        if type(handle) is not int or handle <= 0:
            raise TransportError("afc_handle_invalid", mutation_attempted=True)
        try:
            await afc.fwrite(handle, data, chunk_size=IO_CHUNK_BYTES)
        finally:
            await asyncio.wait_for(afc.fclose(handle), CLOSE_TIMEOUT_SECONDS)

    async def submit(
        self, request: SignedRequest, *, before_mutation: BeforeMutation,
    ) -> None:
        """Publish once. Successful return acknowledges transfer, not execution.

        Partial visibility is handled by the companion's strict authenticated
        envelope and private claim. No AFC rename/link exclusivity is assumed.
        """
        async with self._lock:
            self._require_active_submission()
            if type(request) is not SignedRequest or not callable(before_mutation):
                raise TransportError("submission_invalid")
            checked = open_request(
                request.envelope_bytes, self._secret,
                expected_session_id=self._target.session_id,
                now_ms=self._now_ms(), session_expires_at_ms=self._session_expiry,
            )
            if checked != request:
                raise TransportError("request_object_mismatch")
            identity = checked.identity
            if (
                self._pending is not None
                or identity.request_id in self._used_ids
                or identity.sequence in self._used_sequences
                or len(self._used_ids) >= MAX_SESSION_REQUESTS
            ):
                raise TransportError("submission_fenced")
            path = self._path("in", identity.sequence)
            # Read-only collision check. This does not claim O_EXCL semantics.
            try:
                async with asyncio.timeout(IO_TIMEOUT_SECONDS):
                    if await self._stat(path) is not None:
                        raise TransportError("mailbox_collision")
            except TransportError:
                raise
            except BaseException as exc:
                await self._poison()
                if not isinstance(exc, Exception):
                    raise
                raise TransportError("submission_preflight_failed") from None

            # Mandatory durable callback is deliberately outside the mutation
            # try block. Its failure propagates and no write has begun.
            await before_mutation(identity)
            self._require_active_submission()
            if self._now_ms() >= checked.expires_at_ms:
                raise TransportError("request_expired_before_write")
            self._pending = identity
            self._used_ids.add(identity.request_id)
            self._used_sequences.add(identity.sequence)
            try:
                async with asyncio.timeout(IO_TIMEOUT_SECONDS):
                    await self._write_regular(path, checked.envelope_bytes)
            except BaseException as exc:
                await self._poison()
                if not isinstance(exc, Exception):
                    raise
                raise TransportError("publication_unknown", mutation_attempted=True) from None

    async def read(self, identity: RequestIdentity) -> dict[str, Any] | None:
        """Read only the exact recorded sequence, including after session expiry."""
        async with self._lock:
            self._require_open()
            validate_identity(identity)
            if identity.session_id != self._target.session_id:
                raise TransportError("session_mismatch")
            if self._pending is not None and self._pending != identity:
                raise TransportError("different_request_pending")
            try:
                async with asyncio.timeout(IO_TIMEOUT_SECONDS):
                    raw = await self._read_regular(self._path("out", identity.sequence))
            except BaseException as exc:
                await self._poison()
                if not isinstance(exc, Exception):
                    raise
                raise TransportError("receipt_read_failed") from None
            if raw is None:
                return None
            # Authentication/shape failure never returns bytes or clears the
            # pending fence. A later explicitly requested read remains possible.
            receipt = open_receipt(raw, self._secret, expected=identity)
            if self._pending == identity:
                self._pending = None
            return receipt

    async def close(self) -> None:
        async with self._lock:
            if self._state == "closed" and self._connection is None:
                return
            connection, self._connection = self._connection, None
            self._state = "closed"
            self.cleanup_incomplete |= await _dispose_bundle(connection)
            if self.cleanup_incomplete:
                raise TransportError("cleanup_incomplete")


async def read_frame(reader: asyncio.StreamReader) -> bytes | None:
    """Bounded framing for already inherited private pipes; never opens a socket."""
    try:
        prefix = await reader.readexactly(4)
    except asyncio.IncompleteReadError as error:
        if not error.partial:
            return None
        raise TransportError("ipc_partial_header") from None
    size = struct.unpack("!I", prefix)[0]
    if not 0 < size <= MAX_IPC_FRAME_BYTES:
        raise TransportError("ipc_frame_size_invalid")
    try:
        return await reader.readexactly(size)
    except asyncio.IncompleteReadError:
        raise TransportError("ipc_partial_body") from None


async def write_frame(writer: asyncio.StreamWriter, payload: bytes) -> None:
    """Caller owns the private pipe and its bounded write deadline."""
    if type(payload) is not bytes or not 0 < len(payload) <= MAX_IPC_FRAME_BYTES:
        raise TransportError("ipc_frame_size_invalid")
    writer.write(struct.pack("!I", len(payload)) + payload)
    await writer.drain()
