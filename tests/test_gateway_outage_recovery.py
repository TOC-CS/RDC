"""Durable standalone gateway recovery following a process/power interruption."""
import json
from pathlib import Path
import tempfile
import unittest

from rdc.gateway_standalone import (
    DeviceSocket, MAX_QUEUE, UNKNOWN_MS, StandaloneGateway, initialize, sha256,
)


class GatewayOutageRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rdc-outage-recovery-")
        self.root = Path(self.temp.name) / "gateway"
        initialize(self.root)
        self.now = 1_000_000
        self.state = StandaloneGateway(self.root, clock=lambda: self.now)
        self.online()
        self.request = json.dumps({"name": "rdc_job_run", "arguments": {
            "argv": ["/bin/echo", "fixture-only"], "cwd": "/tmp",
        }})

    def tearDown(self):
        self.state.db.close()
        self.temp.cleanup()

    def online(self):
        self.state.sockets.add(DeviceSocket(None))
        self.state.last_heartbeat = self.now

    def restart(self):
        self.state.db.close()
        self.state = StandaloneGateway(self.root, clock=lambda: self.now)
        self.online()

    def add(self, key):
        return self.state.enqueue(key, self.request, "rdc_job_run", True)

    def frame(self, op, text="original-retained-result"):
        raw = json.dumps({"content": [{"type": "text", "text": text}],
                          "structuredContent": {"ok": True, "text": text}})
        return {"id": op["id"], "claimId": op["claimId"],
                "requestDigest": op["requestDigest"], "resultJson": raw,
                "resultDigest": sha256(raw)}

    def test_expired_queue_frees_capacity_without_replay_after_clock_rollback(self):
        originals = [self.add(f"expired-{i}")[0] for i in range(MAX_QUEUE)]
        with self.assertRaisesRegex(ValueError, "queue_full"):
            self.add("over-capacity")
        previous = self.now
        self.now += 30_000
        self.restart()
        self.assertEqual(self.state.status()["pending_operations"], 0)
        self.assertEqual(self.state.recover(originals[0])["state"], "expired")
        self.assertEqual(self.add("expired-0"), (originals[0], False))
        self.now = previous
        self.online()
        self.assertEqual(self.state.recover(originals[-1])["state"], "expired")
        self.assertIsNone(self.state.claim())
        new_id, fresh = self.add("new-after-restart")
        self.assertTrue(fresh)
        self.assertEqual(self.state.claim()["id"], new_id)

    def test_unknown_claims_free_capacity_and_accept_only_original_late_result(self):
        originals = []
        for i in range(MAX_QUEUE):
            self.add(f"claimed-{i}")
            originals.append(self.state.claim())
        self.now += UNKNOWN_MS
        self.online()
        self.assertEqual(self.state.status()["pending_operations"], MAX_QUEUE)
        with self.assertRaisesRegex(ValueError, "queue_full"):
            self.add("too-soon")
        self.now += 1
        self.restart()
        self.assertEqual(self.state.status()["pending_operations"], 0)
        self.assertEqual(self.state.recover(originals[0]["id"])["state"], "unknown")
        self.assertEqual(self.add("claimed-0"), (originals[0]["id"], False))
        self.assertIsNone(self.state.claim())
        new_id, fresh = self.add("after-unknown")
        self.assertTrue(fresh)
        self.assertEqual(self.state.claim()["id"], new_id)
        exact = self.frame(originals[0])
        with self.assertRaisesRegex(ValueError, "claim_mismatch"):
            self.state.complete(dict(exact, claimId="wrong"))
        self.assertFalse(self.state.complete(exact)["duplicate"])
        self.assertTrue(self.state.complete(exact)["duplicate"])
        self.assertEqual(self.state.recover(originals[0]["id"])["resultJson"],
                         exact["resultJson"])
        self.restart()
        self.assertEqual(self.state.recover(originals[1]["id"])["state"], "unknown")
        self.assertIsNone(self.state.claim())

    def test_direct_admission_after_outage_does_not_require_status_poll(self):
        for i in range(MAX_QUEUE):
            self.add(f"queued-{i}")
        self.now += 30_001
        self.restart()
        new_id, fresh = self.add("new-without-status")
        self.assertTrue(fresh)
        self.assertEqual(self.state.claim()["id"], new_id)

    def test_inline_retained_result_integrity_failure_never_replays(self):
        original, _ = self.add("retained")
        frame = self.frame(self.state.claim())
        self.state.complete(frame)
        self.restart()
        self.assertEqual(self.state.recover(original)["resultJson"], frame["resultJson"])
        self.state.db.execute("UPDATE operations SET result_json=? WHERE id=?",
                              ('{"content":[{"type":"text","text":"corrupt"}]}', original))
        with self.assertRaisesRegex(ValueError, "result_unavailable"):
            self.state.recover(original)
        self.assertEqual(self.add("retained"), (original, False))
        self.assertIsNone(self.state.claim())

    def test_additive_upgrade_preserves_prior_claim_and_late_result(self):
        original, _ = self.add("legacy-claimed")
        claimed = self.state.claim()
        queued, _ = self.add("legacy-queued")
        # Reproduce the previous schema with its existing original records.
        self.state.db.execute("DROP INDEX operations_live_queue")
        self.state.db.execute("ALTER TABLE operations DROP COLUMN unknown_since_ms")
        self.now += UNKNOWN_MS + 1
        self.restart()
        self.assertEqual(self.state.status()["pending_operations"], 0)
        self.assertEqual(self.state.recover(queued)["state"], "expired")
        row = self.state.row("SELECT * FROM operations WHERE id=?", original)
        self.assertEqual(row["state"], "claimed")
        self.assertEqual(row["claim_id"], claimed["claimId"])
        self.assertEqual(row["request_digest"], claimed["requestDigest"])
        self.assertIsNotNone(row["unknown_since_ms"])
        self.assertEqual(self.state.recover(original)["state"], "unknown")
        self.now -= UNKNOWN_MS + 1
        self.online()
        self.assertEqual(self.state.recover(original)["state"], "unknown")
        self.assertEqual(self.add("legacy-claimed"), (original, False))
        self.assertIsNone(self.state.claim())
        exact = self.frame(claimed)
        self.assertFalse(self.state.complete(exact)["duplicate"])
        self.assertEqual(self.state.recover(original)["resultJson"], exact["resultJson"])

    def test_recovery_of_single_expired_operation_is_durable(self):
        original, _ = self.add("expires")
        previous = self.now
        self.now += 30_000
        self.assertEqual(self.state.recover(original)["state"], "expired")
        self.restart()
        self.now = previous
        self.online()
        self.assertEqual(self.state.recover(original)["state"], "expired")
        self.assertIsNone(self.state.claim())


if __name__ == "__main__":
    unittest.main()
