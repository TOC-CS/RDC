"""Private warm-terminal wire codec. No device access or module-level I/O.

Requests, ready messages and provisions have canonical integer-only payloads.
Receipt HMACs cover their exact raw payload bytes; receipt payloads are parsed
strictly without a float-sensitive canonical reserialization requirement.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import math
import re
import uuid
from dataclasses import dataclass
from typing import Any

SCHEMA = 1
BUNDLE_ID = "org.tocministries.rdc.warmterminal"
MAX_SAFE_INTEGER = (1 << 53) - 1
MAX_SESSION_REQUESTS = 64
MAX_COMMAND_BYTES = 4000
MAX_OUTPUT_BYTES = 4096
MAX_PAYLOAD_BYTES = 9000
MAX_ENVELOPE_BYTES = 12 * 1024
MAX_PROVISION_BYTES = 2048
MAX_SESSION_TTL_MS = 600_000
DOMAINS = {
    "request": b"RDC-WARM-REQUEST-v1\0",
    "receipt": b"RDC-WARM-RECEIPT-v1\0",
    "ready": b"RDC-WARM-READY-v1\0",
}
LEGACY_RECEIPT_FIELDS = frozenset({
    "schema", "request_id", "run_id", "command_sha256", "exit_code",
    "device_elapsed_ms", "output", "execution_location",
})
REQUEST_FIELDS = frozenset({
    "schema", "session_id", "request_id", "sequence", "expires_at_ms",
    "command", "command_sha256",
})
RECEIPT_FIELDS = LEGACY_RECEIPT_FIELDS | {
    "session_id", "sequence", "request_sha256",
}
READY_FIELDS = frozenset({
    "schema", "session_id", "expires_at_ms", "next_sequence",
    "status", "bundle_id",
})
PROVISION_FIELDS = frozenset({
    "schema", "session_id", "secret_b64", "expires_at_ms",
})
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class WireError(ValueError):
    """A stable error code with no untrusted payload or secret in its message."""


@dataclass(frozen=True, repr=False)
class RequestIdentity:
    session_id: str
    request_id: str
    sequence: int
    command_sha256: str
    request_sha256: str


@dataclass(frozen=True, repr=False)
class SignedRequest:
    identity: RequestIdentity
    expires_at_ms: int
    command: str
    payload_bytes: bytes
    envelope_bytes: bytes


def canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), sort_keys=True,
            allow_nan=False,
        ).encode("utf-8", "strict")
    except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError):
        raise WireError("json_encoding_invalid") from None


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise WireError("json_duplicate_key")
        result[key] = value
    return result


def _constant_rejected(_: str) -> None:
    raise WireError("json_nonfinite_number")


def _parse(raw: bytes, maximum: int, *, canonical: bool) -> dict[str, Any]:
    if type(raw) is not bytes or not 0 < len(raw) <= maximum:
        raise WireError("json_size_invalid")
    try:
        value = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=_unique_object,
            parse_constant=_constant_rejected,
        )
    except WireError:
        raise
    except (UnicodeError, ValueError, TypeError, RecursionError, OverflowError):
        raise WireError("json_invalid") from None
    if type(value) is not dict:
        raise WireError("json_object_required")
    if canonical and canonical_json(value) != raw:
        raise WireError("json_noncanonical")
    return value


def _keys(value: dict[str, Any], expected: frozenset[str]) -> None:
    if set(value) != expected:
        raise WireError("fields_invalid")


def _integer(value: Any, minimum: int = 0) -> int:
    if type(value) is not int or not minimum <= value <= MAX_SAFE_INTEGER:
        raise WireError("integer_invalid")
    return value


def _sequence(value: Any) -> int:
    number = _integer(value, 1)
    if number > MAX_SESSION_REQUESTS:
        raise WireError("sequence_invalid")
    return number


def canonical_uuid(value: Any) -> str:
    if type(value) is not str:
        raise WireError("uuid_invalid")
    try:
        canonical = str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise WireError("uuid_invalid") from None
    if value != canonical:
        raise WireError("uuid_noncanonical")
    return value


def _digest(value: Any) -> str:
    if type(value) is not str or _HEX64.fullmatch(value) is None:
        raise WireError("digest_invalid")
    return value


def _secret(secret: bytes) -> bytes:
    if type(secret) is not bytes or len(secret) != 32:
        raise WireError("secret_invalid")
    return secret


def _text_bytes(value: Any, maximum: int, *, command: bool) -> bytes:
    if type(value) is not str:
        raise WireError("text_invalid")
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeError:
        raise WireError("text_invalid") from None
    if len(encoded) > maximum or (command and not value.strip()):
        raise WireError("text_size_invalid")
    for character in value:
        point = ord(character)
        if (point < 0x20 or 0x7F <= point <= 0x9F):
            if command or point not in (9, 10):
                raise WireError("text_control_forbidden")
    return encoded


def _schema(value: Any) -> None:
    if type(value) is not int or value != SCHEMA:
        raise WireError("schema_invalid")


def _session(value: Any, expected: str) -> None:
    if canonical_uuid(value) != canonical_uuid(expected):
        raise WireError("session_mismatch")


def _decode_base64(value: Any, maximum: int) -> bytes:
    if type(value) is not str or len(value) > 4 * ((maximum + 2) // 3):
        raise WireError("base64_size_invalid")
    try:
        decoded = base64.b64decode(value.encode("ascii"), validate=True)
    except (ValueError, UnicodeError, binascii.Error):
        raise WireError("base64_invalid") from None
    if len(decoded) > maximum or base64.b64encode(decoded).decode("ascii") != value:
        raise WireError("base64_noncanonical")
    return decoded


def _seal(payload: dict[str, Any], secret: bytes, kind: str) -> bytes:
    raw = canonical_json(payload)
    if not 0 < len(raw) <= MAX_PAYLOAD_BYTES:
        raise WireError("payload_size_invalid")
    envelope = canonical_json({
        "schema": SCHEMA,
        "payload_b64": base64.b64encode(raw).decode("ascii"),
        "mac": hmac.new(_secret(secret), DOMAINS[kind] + raw, hashlib.sha256).hexdigest(),
    })
    if len(envelope) > MAX_ENVELOPE_BYTES:
        raise WireError("envelope_size_invalid")
    return envelope


def _open(envelope: bytes, secret: bytes, kind: str) -> tuple[dict[str, Any], bytes]:
    outer = _parse(envelope, MAX_ENVELOPE_BYTES, canonical=True)
    _keys(outer, frozenset({"schema", "payload_b64", "mac"}))
    _schema(outer["schema"])
    supplied = _digest(outer["mac"])
    raw = _decode_base64(outer["payload_b64"], MAX_PAYLOAD_BYTES)
    calculated = hmac.new(
        _secret(secret), DOMAINS[kind] + raw, hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(supplied, calculated):
        raise WireError("authentication_failed")
    return _parse(raw, MAX_PAYLOAD_BYTES, canonical=(kind != "receipt")), raw


def validate_identity(identity: RequestIdentity) -> None:
    if type(identity) is not RequestIdentity:
        raise WireError("identity_invalid")
    canonical_uuid(identity.session_id)
    canonical_uuid(identity.request_id)
    _sequence(identity.sequence)
    _digest(identity.command_sha256)
    _digest(identity.request_sha256)


def _validate_request(
    payload: dict[str, Any], *, expected_session_id: str, now_ms: int,
    session_expires_at_ms: int,
) -> None:
    _keys(payload, REQUEST_FIELDS)
    _schema(payload["schema"])
    _session(payload["session_id"], expected_session_id)
    canonical_uuid(payload["request_id"])
    _sequence(payload["sequence"])
    expiry = _integer(payload["expires_at_ms"], 1)
    _integer(now_ms)
    session_expiry = _integer(session_expires_at_ms, 1)
    if not now_ms < expiry <= session_expiry:
        raise WireError("request_expired_or_outside_session")
    command = _text_bytes(payload["command"], MAX_COMMAND_BYTES, command=True)
    supplied = _digest(payload["command_sha256"])
    if not hmac.compare_digest(supplied, hashlib.sha256(command).hexdigest()):
        raise WireError("command_digest_mismatch")


def make_request(
    secret: bytes, *, session_id: str, request_id: str, sequence: int,
    expires_at_ms: int, command: str, now_ms: int, session_expires_at_ms: int,
) -> SignedRequest:
    command_bytes = _text_bytes(command, MAX_COMMAND_BYTES, command=True)
    payload = {
        "schema": SCHEMA, "session_id": session_id, "request_id": request_id,
        "sequence": sequence, "expires_at_ms": expires_at_ms, "command": command,
        "command_sha256": hashlib.sha256(command_bytes).hexdigest(),
    }
    _validate_request(
        payload, expected_session_id=session_id, now_ms=now_ms,
        session_expires_at_ms=session_expires_at_ms,
    )
    return open_request(
        _seal(payload, secret, "request"), secret,
        expected_session_id=session_id, now_ms=now_ms,
        session_expires_at_ms=session_expires_at_ms,
    )


def open_request(
    envelope_bytes: bytes, secret: bytes, *, expected_session_id: str,
    now_ms: int, session_expires_at_ms: int,
) -> SignedRequest:
    payload, raw = _open(envelope_bytes, secret, "request")
    _validate_request(
        payload, expected_session_id=expected_session_id, now_ms=now_ms,
        session_expires_at_ms=session_expires_at_ms,
    )
    identity = RequestIdentity(
        session_id=payload["session_id"], request_id=payload["request_id"],
        sequence=payload["sequence"], command_sha256=payload["command_sha256"],
        request_sha256=hashlib.sha256(raw).hexdigest(),
    )
    return SignedRequest(
        identity=identity, expires_at_ms=payload["expires_at_ms"],
        command=payload["command"], payload_bytes=raw, envelope_bytes=envelope_bytes,
    )


def _validate_receipt(payload: dict[str, Any]) -> None:
    _keys(payload, RECEIPT_FIELDS)
    _schema(payload["schema"])
    canonical_uuid(payload["session_id"])
    canonical_uuid(payload["request_id"])
    canonical_uuid(payload["run_id"])
    _sequence(payload["sequence"])
    _digest(payload["command_sha256"])
    _digest(payload["request_sha256"])
    if type(payload["exit_code"]) is not int or payload["exit_code"] not in (0, 1):
        raise WireError("receipt_exit_code_invalid")
    elapsed = payload["device_elapsed_ms"]
    if type(elapsed) not in (int, float) or not 0 <= elapsed < 30_000:
        raise WireError("receipt_elapsed_invalid")
    if not math.isfinite(elapsed):
        raise WireError("receipt_elapsed_invalid")
    _text_bytes(payload["output"], MAX_OUTPUT_BYTES, command=False)
    if payload["execution_location"] != "mobile_device":
        raise WireError("receipt_location_invalid")


def make_receipt(payload: dict[str, Any], secret: bytes) -> bytes:
    """Useful for companion fixtures; the host never invents a device receipt."""
    _validate_receipt(payload)
    return _seal(payload, secret, "receipt")


def open_receipt(
    envelope_bytes: bytes, secret: bytes, *, expected: RequestIdentity,
) -> dict[str, Any]:
    validate_identity(expected)
    payload, _ = _open(envelope_bytes, secret, "receipt")
    _validate_receipt(payload)
    for field in (
        "session_id", "request_id", "sequence", "command_sha256", "request_sha256",
    ):
        if payload[field] != getattr(expected, field):
            raise WireError("receipt_request_mismatch")
    return payload


def legacy_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    """Call only on an authenticated open_receipt result before parent validation."""
    _validate_receipt(payload)
    return {field: payload[field] for field in LEGACY_RECEIPT_FIELDS}


def _validate_ready(
    payload: dict[str, Any], *, expected_session_id: str, now_ms: int,
    allow_expired: bool,
) -> None:
    _keys(payload, READY_FIELDS)
    _schema(payload["schema"])
    _session(payload["session_id"], expected_session_id)
    expiry = _integer(payload["expires_at_ms"], 1)
    _integer(now_ms)
    _sequence(payload["next_sequence"])
    if payload["next_sequence"] != 1:
        raise WireError("ready_sequence_invalid")
    if expiry > now_ms + MAX_SESSION_TTL_MS or (not allow_expired and expiry <= now_ms):
        raise WireError("session_expiry_invalid")
    if payload["status"] != "ready" or payload["bundle_id"] != BUNDLE_ID:
        raise WireError("ready_invalid")


def make_ready(payload: dict[str, Any], secret: bytes, *, now_ms: int) -> bytes:
    _validate_ready(
        payload, expected_session_id=payload.get("session_id"),
        now_ms=now_ms, allow_expired=False,
    )
    return _seal(payload, secret, "ready")


def open_ready(
    envelope_bytes: bytes, secret: bytes, *, expected_session_id: str,
    now_ms: int, allow_expired: bool = False,
) -> dict[str, Any]:
    payload, _ = _open(envelope_bytes, secret, "ready")
    _validate_ready(
        payload, expected_session_id=expected_session_id, now_ms=now_ms,
        allow_expired=allow_expired,
    )
    return payload


def make_provision(
    secret: bytes, *, session_id: str, expires_at_ms: int, now_ms: int,
) -> bytes:
    payload = {
        "schema": SCHEMA, "session_id": canonical_uuid(session_id),
        "secret_b64": base64.b64encode(_secret(secret)).decode("ascii"),
        "expires_at_ms": _integer(expires_at_ms, 1),
    }
    _integer(now_ms)
    if not now_ms < expires_at_ms <= now_ms + MAX_SESSION_TTL_MS:
        raise WireError("session_expiry_invalid")
    raw = canonical_json(payload)
    if len(raw) > MAX_PROVISION_BYTES:
        raise WireError("provision_size_invalid")
    return raw


def open_provision(
    raw: bytes, *, expected_session_id: str, now_ms: int,
) -> dict[str, Any]:
    payload = _parse(raw, MAX_PROVISION_BYTES, canonical=True)
    _keys(payload, PROVISION_FIELDS)
    _schema(payload["schema"])
    _session(payload["session_id"], expected_session_id)
    _secret(_decode_base64(payload["secret_b64"], 32))
    expiry = _integer(payload["expires_at_ms"], 1)
    _integer(now_ms)
    if not now_ms < expiry <= now_ms + MAX_SESSION_TTL_MS:
        raise WireError("session_expiry_invalid")
    return payload


def mailbox_leaf(session_id: str, kind: str, sequence: int | None = None) -> str:
    """Only three fixed filename templates. No caller-provided path component."""
    session = canonical_uuid(session_id)
    if kind == "ready" and sequence is None:
        return f"rdc-warm-{session}-ready.json"
    if kind in ("in", "out") and sequence is not None:
        number = _sequence(sequence)
        return f"rdc-warm-{session}-{kind}-{number}.json"
    raise WireError("mailbox_name_invalid")
