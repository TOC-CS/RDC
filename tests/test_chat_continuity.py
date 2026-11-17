"""Cross-chat interruption prevention and explicit recovery tests.

Synthetic client identities. No real ChatGPT conversation is interrupted,
woken, stopped, restored, or opened by these tests.
"""
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from rdc.chat_continuity import ContinuityGate, ContinuityDenied


class ContinuityGateTests(unittest.TestCase):
    def setUp(self):
        self.now = 1794906000000
        self.gate = ContinuityGate(clock_ms=lambda: self.now)

    def test_undiscovered_or_busy_session_may_queue_but_never_receive_direct_push(self):
        self.assertEqual(self.gate.direct_status("chat-B")["reason"], "UNVERIFIED_SESSION")
        self.gate.heartbeat("chat-B", actor="chat-B", epoch=1, busy=True, direct_opt_in=True)
        observed = self.gate.direct_status("chat-B")
        self.assertFalse(observed["allowed"])
        self.assertEqual(observed["reason"], "SESSION_BUSY")
        self.gate.heartbeat("chat-B", actor="chat-B", epoch=1, busy=False, direct_opt_in=False)
        self.assertEqual(self.gate.direct_status("chat-B")["reason"], "DIRECT_NOT_OPTED_IN")
        self.gate.heartbeat("chat-B", actor="chat-B", epoch=1, busy=False, direct_opt_in=True)
        self.assertTrue(self.gate.direct_status("chat-B")["allowed"])

    def test_interrupted_connection_requires_explicit_verified_recovery_new_epoch(self):
        self.gate.heartbeat("chat-B", actor="chat-B", epoch=3, busy=False, direct_opt_in=True)
        self.assertTrue(self.gate.direct_status("chat-B")["allowed"])
        self.gate.interrupted("chat-B", actor="chat-B")
        self.assertEqual(self.gate.direct_status("chat-B")["reason"], "SESSION_INTERRUPTED")
        with self.assertRaises(ContinuityDenied):
            self.gate.heartbeat("chat-B", actor="chat-B", epoch=3, busy=False, direct_opt_in=True)
        with self.assertRaises(ContinuityDenied):
            self.gate.resume("chat-B", actor="chat-B", epoch=3, verified=True)
        with self.assertRaises(ContinuityDenied):
            self.gate.resume("chat-B", actor="chat-B", epoch=4, verified=False)
        self.assertEqual(self.gate.direct_status("chat-B")["reason"], "SESSION_INTERRUPTED")
        self.gate.resume("chat-B", actor="chat-B", epoch=4, verified=True)
        self.assertEqual(self.gate.direct_status("chat-B")["reason"], "DIRECT_NOT_OPTED_IN")
        self.gate.heartbeat("chat-B", actor="chat-B", epoch=4, busy=False, direct_opt_in=True)
        self.assertTrue(self.gate.direct_status("chat-B")["allowed"])

    def test_concurrent_peer_delivery_attempts_admit_only_one_direct_message(self):
        self.gate.heartbeat("chat-B", actor="chat-B", epoch=1,
                            busy=False, direct_opt_in=True)
        with ThreadPoolExecutor(max_workers=12) as pool:
            states = list(pool.map(
                lambda _: self.gate.reserve_direct("chat-B", actor="chat-B"), range(40)))
        self.assertEqual(sum(bool(item["allowed"]) for item in states), 1)
        self.assertEqual(self.gate.direct_status("chat-B")["reason"], "SESSION_BUSY")
        self.gate.heartbeat("chat-B", actor="chat-B", epoch=1,
                            busy=False, direct_opt_in=True)
        self.assertTrue(self.gate.reserve_direct("chat-B", actor="chat-B")["allowed"])

    def test_unknown_delivery_does_not_claim_the_chat_stopped_or_auto_resume(self):
        self.gate.heartbeat("chat-B", actor="chat-B", epoch=8, busy=False, direct_opt_in=True)
        result = self.gate.unconfirmed("chat-B", actor="chat-B")
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "DELIVERY_UNCONFIRMED")
        with self.assertRaises(ContinuityDenied):
            self.gate.heartbeat("chat-B", actor="chat-B", epoch=8, busy=False, direct_opt_in=True)
        self.gate.resume("chat-B", actor="chat-B", epoch=9, verified=True)
        self.assertEqual(self.gate.direct_status("chat-B")["reason"], "DIRECT_NOT_OPTED_IN")

    def test_other_chat_cannot_mark_session_ready_busy_interrupted_or_resumed(self):
        for action, kwargs in (
            ("heartbeat", dict(epoch=1, busy=False, direct_opt_in=True)),
            ("interrupted", dict()),
            ("resume", dict(epoch=2, verified=True)),
        ):
            with self.subTest(action=action):
                with self.assertRaises(ContinuityDenied):
                    getattr(self.gate, action)("chat-B", actor="chat-A", **kwargs)
        self.assertEqual(self.gate.direct_status("chat-B")["reason"], "UNVERIFIED_SESSION")

    def test_stale_heartbeat_is_not_assumed_idle_or_resumed(self):
        self.gate.heartbeat("chat-B", actor="chat-B", epoch=1, busy=False, direct_opt_in=True)
        self.now += 90_001
        self.assertEqual(self.gate.direct_status("chat-B")["reason"], "SESSION_STALE")
        self.gate.heartbeat("chat-B", actor="chat-B", epoch=1, busy=False, direct_opt_in=True)
        self.assertTrue(self.gate.direct_status("chat-B")["allowed"])

    def test_new_registry_fails_closed_after_restart_until_real_peer_reenrollment(self):
        self.gate.heartbeat("chat-B", actor="chat-B", epoch=1, busy=False, direct_opt_in=True)
        fresh = ContinuityGate(clock_ms=lambda: self.now)
        self.assertEqual(fresh.direct_status("chat-B")["reason"], "UNVERIFIED_SESSION")

    def test_disconnected_peer_does_not_alter_sender_state(self):
        self.gate.heartbeat("chat-A", actor="chat-A", epoch=1, busy=False, direct_opt_in=True)
        self.gate.heartbeat("chat-B", actor="chat-B", epoch=1, busy=True, direct_opt_in=False)
        self.gate.interrupted("chat-B", actor="chat-B")
        self.assertTrue(self.gate.direct_status("chat-A")["allowed"])
        self.assertEqual(self.gate.direct_status("chat-B")["reason"], "SESSION_INTERRUPTED")


if __name__ == "__main__":
    unittest.main()
