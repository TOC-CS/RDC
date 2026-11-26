"""12 focused unittest cases for the private warm USB candidate. No real USB factory is invoked.

The root campaign owner must precharge these cases before executing them.
Fixtures use generic identifiers, a synthetic key and in-memory AFC doubles.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import unittest
from dataclasses import replace
from types import SimpleNamespace

from rdc.ios_warm_terminal_codec import (
    BUNDLE_ID, LEGACY_RECEIPT_FIELDS, MAX_ENVELOPE_BYTES, RequestIdentity,
    WireError, canonical_json, legacy_receipt, make_provision, make_ready,
    make_receipt, make_request, mailbox_leaf, open_provision, open_ready,
    open_receipt, open_request,
)
from rdc.ios_warm_terminal_usb import (
    CappedAFCConnection, ConnectionBundle, FixedTarget, MAX_AFC_BODY_BYTES,
    TransportError, WarmUSBTransport, read_frame,
)

SECRET = bytes(range(32))  # Public synthetic fixture, never a provisioned key.
SESSION = "00000000-0000-4000-8000-000000000001"
REQUEST = "00000000-0000-4000-8000-000000000002"
RUN = "00000000-0000-4000-8000-000000000003"
UDID = "00000000-0000000000000000"
NOW = 1000
EXPIRY = 100_000


def request_fixture(**overrides):
    arguments = {
        "session_id": SESSION, "request_id": REQUEST, "sequence": 1,
        "expires_at_ms": 50_000, "command": "pwd", "now_ms": NOW,
        "session_expires_at_ms": EXPIRY,
    }
    arguments.update(overrides)
    return make_request(SECRET, **arguments)


def receipt_payload(request, **overrides):
    identity = request.identity
    payload = {
        "schema": 1, "session_id": identity.session_id,
        "request_id": identity.request_id, "sequence": identity.sequence,
        "request_sha256": identity.request_sha256, "run_id": RUN,
        "command_sha256": identity.command_sha256, "exit_code": 0,
        "device_elapsed_ms": 1.5, "output": "/workspace\n",
        "execution_location": "mobile_device",
    }
    payload.update(overrides)
    return payload


def ready_payload():
    return {
        "schema": 1, "session_id": SESSION, "expires_at_ms": EXPIRY,
        "next_sequence": 1, "status": "ready", "bundle_id": BUNDLE_ID,
    }


def signed_raw(raw, domain):
    """Independent wire fixture, including legal noncanonical receipt numbers."""
    return canonical_json({
        "schema": 1, "payload_b64": base64.b64encode(raw).decode("ascii"),
        "mac": hmac.new(SECRET, domain + raw, hashlib.sha256).hexdigest(),
    })


class WarmCodecTests(unittest.TestCase):
    def test_unicode_request_and_utf8_byte_boundary(self):
        request = request_fixture(command='echo "caf\u00e9/\U0001f600"')
        opened = open_request(
            request.envelope_bytes, SECRET, expected_session_id=SESSION,
            now_ms=NOW, session_expires_at_ms=EXPIRY,
        )
        self.assertEqual(opened, request)
        self.assertIn("caf\u00e9/\U0001f600".encode("utf-8"), request.payload_bytes)
        self.assertEqual(
            request.identity.request_sha256,
            hashlib.sha256(request.payload_bytes).hexdigest(),
        )
        self.assertLessEqual(len(request_fixture(command="\u00e9" * 2000).envelope_bytes), MAX_ENVELOPE_BYTES)
        with self.assertRaises(WireError):
            request_fixture(command="\u00e9" * 2000 + "x")

    def test_tampering_and_domain_substitution_fail(self):
        request = request_fixture()
        outer = json.loads(request.envelope_bytes)
        outer["mac"] = ("0" if outer["mac"][0] != "0" else "1") + outer["mac"][1:]
        with self.assertRaisesRegex(WireError, "authentication_failed"):
            open_request(
                canonical_json(outer), SECRET, expected_session_id=SESSION,
                now_ms=NOW, session_expires_at_ms=EXPIRY,
            )
        with self.assertRaisesRegex(WireError, "authentication_failed"):
            open_ready(
                request.envelope_bytes, SECRET, expected_session_id=SESSION,
                now_ms=NOW,
            )

    def test_partial_duplicate_and_noncanonical_request_rejected(self):
        request = request_fixture()
        for raw in (
            request.envelope_bytes[:-1],
            b'{"schema":1,' + request.envelope_bytes[1:],
            signed_raw(b" " + request.payload_bytes, b"RDC-WARM-REQUEST-v1\0"),
            signed_raw(b'{"sequence":1,' + request.payload_bytes[1:], b"RDC-WARM-REQUEST-v1\0"),
        ):
            with self.assertRaises(WireError):
                open_request(
                    raw, SECRET, expected_session_id=SESSION, now_ms=NOW,
                    session_expires_at_ms=EXPIRY,
                )

    def test_sequence_deadline_controls_and_initial_ready_limits(self):
        self.assertEqual(request_fixture(sequence=64).identity.sequence, 64)
        for overrides in (
            {"sequence": 65}, {"sequence": True}, {"expires_at_ms": NOW},
            {"expires_at_ms": EXPIRY + 1}, {"command": "pwd\n"},
            {"command": "pwd\x7f"}, {"command": "pwd\x85"},
        ):
            with self.assertRaises(WireError):
                request_fixture(**overrides)
        invalid_ready = ready_payload()
        invalid_ready["next_sequence"] = 2
        with self.assertRaises(WireError):
            make_ready(invalid_ready, SECRET, now_ms=NOW)

    def test_receipt_raw_float_mac_and_full_request_binding(self):
        request = request_fixture()
        payload = receipt_payload(request)
        raw = canonical_json(payload).replace(
            b'"device_elapsed_ms":1.5', b'"device_elapsed_ms":1.5e0',
        )
        envelope = signed_raw(raw, b"RDC-WARM-RECEIPT-v1\0")
        result = open_receipt(envelope, SECRET, expected=request.identity)
        self.assertEqual(result, payload)
        self.assertEqual(set(legacy_receipt(result)), LEGACY_RECEIPT_FIELDS)
        with self.assertRaisesRegex(WireError, "receipt_request_mismatch"):
            open_receipt(
                envelope, SECRET,
                expected=replace(request.identity, request_sha256="0" * 64),
            )

    def test_receipt_output_and_scalar_limits(self):
        request = request_fixture()
        valid = make_receipt(receipt_payload(request, output="one\ttwo\n"), SECRET)
        self.assertEqual(
            open_receipt(valid, SECRET, expected=request.identity)["output"],
            "one\ttwo\n",
        )
        for overrides in (
            {"output": "x" * 4097}, {"output": "\u00e9" * 2049},
            {"output": "\x1b[0m"}, {"device_elapsed_ms": True},
            {"device_elapsed_ms": 30_000}, {"exit_code": True},
        ):
            with self.assertRaises(WireError):
                make_receipt(receipt_payload(request, **overrides), SECRET)

    def test_ready_and_private_provision_expiry_contract(self):
        ready = make_ready(ready_payload(), SECRET, now_ms=NOW)
        with self.assertRaises(WireError):
            open_ready(ready, SECRET, expected_session_id=SESSION, now_ms=EXPIRY)
        self.assertEqual(
            open_ready(
                ready, SECRET, expected_session_id=SESSION,
                now_ms=EXPIRY, allow_expired=True,
            )["next_sequence"],
            1,
        )
        provision = make_provision(
            SECRET, session_id=SESSION, expires_at_ms=EXPIRY, now_ms=NOW,
        )
        self.assertEqual(
            open_provision(
                provision, expected_session_id=SESSION, now_ms=NOW,
            )["secret_b64"],
            base64.b64encode(SECRET).decode("ascii"),
        )
        with self.assertRaises(WireError):
            open_provision(provision, expected_session_id=SESSION, now_ms=EXPIRY)


class FakeAFC:
    def __init__(self, files, events):
        self.files = dict(files)
        self.events = events
        self.handles = {}
        self.counter = 0
        self.fail_write = False
        self.oversize_path = None

    async def stat(self, path):
        self.events.append(("stat", path))
        if path == "/Documents":
            return {"st_ifmt": "S_IFDIR"}
        if path not in self.files:
            raise FileNotFoundError()
        return {"st_ifmt": "S_IFREG", "st_nlink": 1, "st_size": len(self.files[path])}

    async def fopen(self, path, mode="r"):
        self.events.append(("open", mode, path))
        if mode == "w":
            self.files[path] = b""
        elif path not in self.files:
            raise FileNotFoundError()
        self.counter += 1
        self.handles[self.counter] = [path, mode, 0]
        return self.counter

    async def fread(self, handle, wanted):
        path, mode, offset = self.handles[handle]
        if path == self.oversize_path:
            return b"x" * (wanted + 1)
        data = self.files[path][offset:offset + wanted]
        self.handles[handle][2] += len(data)
        return data

    async def fwrite(self, handle, data, chunk_size):
        self.events.append(("write",))
        if self.fail_write:
            raise OSError("synthetic write failure")
        path = self.handles[handle][0]
        self.files[path] += data

    async def fclose(self, handle):
        self.events.append(("fclose", handle))
        self.handles.pop(handle, None)

    async def aclose(self):
        self.events.append(("afc_close",))
        self.handles.clear()


class FakeLockdown:
    def __init__(self, events):
        self.events = events
        self.paired = True
        self.udid = UDID
        self.service = SimpleNamespace(
            mux_device=SimpleNamespace(connection_type="USB", serial=UDID),
        )

    async def close(self):
        self.events.append(("lockdown_close",))


def transport_fixture(*, allow_submit=True, clock_ms=NOW):
    events = []
    ready_path = "/Documents/" + mailbox_leaf(SESSION, "ready")
    afc = FakeAFC(
        {ready_path: make_ready(ready_payload(), SECRET, now_ms=NOW)}, events,
    )
    lockdown = FakeLockdown(events)
    calls = []
    clock = [clock_ms]

    async def factory(target):
        calls.append(target)
        return ConnectionBundle(afc, lockdown)

    transport = WarmUSBTransport(
        FixedTarget(UDID, SESSION), SECRET, EXPIRY,
        connection_factory=factory, allow_submit=allow_submit,
        now_ms=lambda: clock[0],
    )
    return transport, afc, lockdown, events, calls, clock


class WarmTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_exact_usb_target_failure_closes_without_retry(self):
        transport, afc, lockdown, events, calls, clock = transport_fixture()
        lockdown.service.mux_device.connection_type = "Network"
        with self.assertRaisesRegex(TransportError, "usb_identity_mismatch"):
            await transport.open()
        self.assertIn(("afc_close",), events)
        self.assertIn(("lockdown_close",), events)
        self.assertFalse(any(event[0] == "open" for event in events))
        with self.assertRaisesRegex(TransportError, "open_already_attempted"):
            await transport.open()
        self.assertEqual(len(calls), 1)

    async def test_durable_callback_precedes_write_and_failure_sends_nothing(self):
        transport, afc, lockdown, events, calls, clock = transport_fixture()
        await transport.open()
        request = request_fixture()

        async def rejected(identity):
            events.append(("journal_rejected",))
            raise RuntimeError("synthetic journal rejection")

        with self.assertRaisesRegex(RuntimeError, "synthetic journal rejection"):
            await transport.submit(request, before_mutation=rejected)
        self.assertFalse(any(event[:2] == ("open", "w") for event in events))

        async def recorded(identity):
            self.assertEqual(identity, request.identity)
            events.append(("journal_recorded",))

        await transport.submit(request, before_mutation=recorded)
        write_index = next(i for i, event in enumerate(events) if event[:2] == ("open", "w"))
        self.assertLess(events.index(("journal_recorded",)), write_index)
        self.assertEqual(len(calls), 1)
        out = "/Documents/" + mailbox_leaf(SESSION, "out", 1)
        afc.files[out] = make_receipt(receipt_payload(request), SECRET)
        self.assertEqual((await transport.read(request.identity))["request_id"], REQUEST)
        with self.assertRaisesRegex(TransportError, "submission_fenced"):
            await transport.submit(request, before_mutation=recorded)
        self.assertEqual(sum(event == ("write",) for event in events), 1)
        await transport.close()

    async def test_mutation_failure_is_unknown_and_never_reconnects(self):
        transport, afc, lockdown, events, calls, clock = transport_fixture()
        await transport.open()
        afc.fail_write = True
        request = request_fixture()

        async def recorded(identity):
            events.append(("journal_recorded",))

        with self.assertRaises(TransportError) as caught:
            await transport.submit(request, before_mutation=recorded)
        self.assertEqual(caught.exception.code, "publication_unknown")
        self.assertTrue(caught.exception.mutation_attempted)
        self.assertTrue(any(event[0] == "fclose" for event in events))
        self.assertIn(("afc_close",), events)
        self.assertIn(("lockdown_close",), events)
        with self.assertRaisesRegex(TransportError, "transport_unavailable"):
            await transport.submit(request, before_mutation=recorded)
        self.assertEqual(len(calls), 1)
        self.assertEqual(sum(event == ("write",) for event in events), 1)

    async def test_expired_read_only_instance_recovers_only_authenticated_receipt(self):
        transport, afc, lockdown, events, calls, clock = transport_fixture(
            allow_submit=False, clock_ms=EXPIRY + 1,
        )
        request = request_fixture()
        out = "/Documents/" + mailbox_leaf(SESSION, "out", 1)
        afc.files[out] = make_receipt(receipt_payload(request), SECRET)
        await transport.open()
        self.assertEqual((await transport.read(request.identity))["request_id"], REQUEST)

        async def forbidden(identity):
            self.fail("Recovery must not invoke the mutation callback")

        with self.assertRaisesRegex(TransportError, "recovery_only"):
            await transport.submit(request, before_mutation=forbidden)
        self.assertFalse(any(event[:2] == ("open", "w") for event in events))
        await transport.close()

    async def test_raw_and_file_read_bounds_and_partial_pipe_fail_closed(self):
        delegated = []

        class Raw:
            async def recvall(self, size):
                delegated.append(size)
                return b"x" * size

        capped = CappedAFCConnection(Raw())
        with self.assertRaisesRegex(TransportError, "afc_frame_size_invalid"):
            await capped.recvall(MAX_AFC_BODY_BYTES + 1)
        self.assertEqual(delegated, [])

        reader = asyncio.StreamReader()
        reader.feed_data(b"\x00\x00\x00\x04ab")
        reader.feed_eof()
        with self.assertRaisesRegex(TransportError, "ipc_partial_body"):
            await read_frame(reader)

        transport, afc, lockdown, events, calls, clock = transport_fixture()
        await transport.open()
        request = request_fixture()
        out = "/Documents/" + mailbox_leaf(SESSION, "out", 1)
        afc.files[out] = make_receipt(receipt_payload(request), SECRET)
        afc.oversize_path = out
        previous_closes = sum(event[0] == "fclose" for event in events)
        with self.assertRaisesRegex(TransportError, "receipt_read_failed"):
            await transport.read(request.identity)
        self.assertGreater(sum(event[0] == "fclose" for event in events), previous_closes)
        self.assertIn(("afc_close",), events)
        self.assertEqual(afc.handles, {})
