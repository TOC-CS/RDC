"""Optional real Atlas Bus v1 sandbox compatibility. Never enroll live sessions."""
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest

from rdc.chat_interconnect import ChatClient, ChatError


ATLAS = Path(os.environ.get("RDC_ATLAS_BUS_TEST_ROOT", "/nonexistent/atlas-bus"))
ENABLED = (ATLAS / "atlasbus" / "store.py").is_file()


@unittest.skipUnless(ENABLED, "Separate Atlas Bus source not attached; synthetic integration skipped")
class ActualAtlasBusSandboxTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(ATLAS))
        from atlasbus.store import BusStore
        self.BusStore = BusStore
        self.temp = tempfile.TemporaryDirectory(prefix="rdc-ai-chat-atlas-")
        self.db = Path(self.temp.name) / "sandbox.sqlite3"
        self.now = 1794900000000
        self.bus = BusStore(self.db, clock_ms=lambda: self.now, synthetic_mode=True)
        for session in ("chatgpt-fixture", "claude-fixture", "grok-fixture"):
            self.bus.register_synthetic_session("rdc", session)
        self.a = ChatClient(self.bus, "chatgpt-fixture", clock_ms=lambda: self.now)
        self.b = ChatClient(self.bus, "claude-fixture", clock_ms=lambda: self.now)
        self.c = ChatClient(self.bus, "grok-fixture", clock_ms=lambda: self.now)

    def tearDown(self):
        self.bus.close()
        self.temp.cleanup()
        if str(ATLAS) in sys.path:
            sys.path.remove(str(ATLAS))

    def test_exact_atlas_bus_roundtrip_reply_identity_delivery_and_dedup_after_reopen(self):
        receipt = self.a.send("claude-fixture", "Can you review the source?", key="cross1")
        self.assertEqual(receipt["receipt"]["state"], "QUEUED")
        claim = self.b.claim(holder="atlas-chat-bridge-fixture")
        self.assertEqual(claim["envelope"]["payload"]["text"], "Can you review the source?")
        self.assertEqual(claim["destination_session_id"], "claude-fixture")
        self.b.mark_fetched(claim, holder="atlas-chat-bridge-fixture")
        acknowledged = self.b.ack(claim["message_id"])
        self.assertEqual(acknowledged["state"], "SESSION_ACKNOWLEDGED")
        reply = self.b.send(
            "chatgpt-fixture", "Reviewed: no failing tests.",
            key="cross1-reply", reply_to=claim["message_id"],
        )
        incoming = self.a.claim(holder="chatgpt-read-fixture")
        self.assertEqual(incoming["envelope"]["causation_id"], claim["message_id"])
        self.assertEqual(incoming["envelope"]["correlation_id"], claim["envelope"]["correlation_id"])
        self.a.mark_fetched(incoming, holder="chatgpt-read-fixture")
        self.a.ack(incoming["message_id"])
        evidence = hashlib.sha256(b"synthetic-delivery-observed").hexdigest()
        self.assertEqual(self.a.confirm(incoming["message_id"], evidence_digest=evidence)["state"], "ACTION_CONFIRMED")
        self.now += 300001
        self.bus.close()
        self.bus = self.BusStore(self.db, clock_ms=lambda: self.now, synthetic_mode=True)
        self.a = ChatClient(self.bus, "chatgpt-fixture", clock_ms=lambda: self.now)
        replay = self.a.send("claude-fixture", "Can you review the source?", key="cross1")
        self.assertEqual(replay["receipt"], receipt["receipt"])
        self.assertTrue(replay["duplicate"])
        self.assertEqual([event["to_state"] for event in self.bus.events(claim["message_id"])], ["QUEUED", "CLAIMED", "ADAPTER_FETCHED", "SESSION_ACKNOWLEDGED"])
        self.assertEqual(reply["receipt"]["message_id"], incoming["message_id"])

    def test_wrong_owner_and_changed_content_are_rejected_by_atlas_core(self):
        first = self.a.send("grok-fixture", "Review this", key="secure1")
        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_CONFLICT"):
            self.a.send("grok-fixture", "Review altered", key="secure1")
        with self.assertRaises(ChatError):
            self.b.status(first["receipt"]["message_id"])
        with self.assertRaisesRegex(ValueError, "WRONG_DESTINATION"):
            self.a.send("fake-target", "no target", key="invalid1")
        self.assertEqual(self.bus.get_message(first["receipt"]["message_id"])["state"], "QUEUED")


if __name__ == "__main__":
    unittest.main()
