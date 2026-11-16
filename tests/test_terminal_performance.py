"""Completion latency and bounded work for isolated durable terminal jobs."""
from contextlib import contextmanager
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from rdc.jobs import Jobs
from rdc.store import Store
from rdc.worker import run


class InlineCompletionBudgetTests(unittest.TestCase):
    def run_at(self, complete_after, wait_ms=1500):
        clock = [0.0]
        reads = []
        outputs = []

        class StoreFixture:
            def job(self, identifier):
                reads.append(clock[0])
                return {"id": identifier, "status": "completed" if clock[0] >= complete_after else "running"}

        jobs = object.__new__(Jobs)
        jobs.store = StoreFixture()
        jobs.settings = type("Settings", (), {"max_read_bytes": 65536})()
        jobs.start = lambda *args, **kwargs: {"job": {"id": "retained-job", "status": "queued"}, "reused": False}

        def output(identifier, **kwargs):
            outputs.append((identifier, kwargs["job_snapshot"]["status"]))
            return {"text": "complete-output"}

        jobs.output = output
        with patch("rdc.jobs.time.monotonic", side_effect=lambda: clock[0]), \
             patch("rdc.jobs.time.sleep", side_effect=lambda duration: clock.__setitem__(0, clock[0] + duration)):
            result = jobs.run(["command"], "/isolated", wait_ms=wait_ms)
        return result, clock[0], reads, outputs

    def test_early_completion_is_collected_without_a_full_control_poll_delay(self):
        result, elapsed, reads, outputs = self.run_at(.005)
        self.assertTrue(result["complete"])
        self.assertEqual(result["output"]["text"], "complete-output")
        self.assertEqual(outputs, [("retained-job", "completed")])
        self.assertLessEqual(elapsed, .020)

    def test_long_wait_does_not_keep_the_high_frequency_initial_polling(self):
        result, elapsed, reads, outputs = self.run_at(1.0)
        self.assertTrue(result["complete"])
        self.assertLessEqual(elapsed, 1.0400001)
        self.assertLessEqual(len(reads), 50, "One second must not cause 100+ SQLite status snapshots")
        self.assertEqual(len(outputs), 1)

    def test_bounded_wait_returns_original_identity_without_partial_output_read(self):
        result, elapsed, reads, outputs = self.run_at(5.0, wait_ms=17)
        self.assertFalse(result["complete"])
        self.assertEqual(result["job"]["id"], "retained-job")
        self.assertIsNone(result["output"])
        self.assertEqual(outputs, [])
        self.assertLessEqual(elapsed, .0170001)


class SupervisorCompletionTests(unittest.TestCase):
    def test_output_eof_before_exit_preserves_child_and_does_not_spin(self):
        with tempfile.TemporaryDirectory(prefix="rdc-eof-budget-") as temp:
            root = Path(temp)
            store = Store(root / "state")
            (store.directory / "jobs").mkdir()
            spec = {"argv": [sys.executable, "-c",
                "import os,time; os.close(1); os.close(2); time.sleep(.30); "
                "open('after-eof', 'w').write('finished')"],
                "cwd": str(root), "timeout": 2, "max_output_bytes": 1024}
            with store.connection() as db:
                db.execute("INSERT INTO jobs(id,fingerprint,spec,status,created_at) VALUES(?,?,?,?,?)",
                           ("eof-budget", "test", json.dumps(spec), "queued", time.time()))
            heartbeat_updates = []
            original_connection = Store.connection

            @contextmanager
            def counted_connection(instance):
                with original_connection(instance) as db:
                    db.set_trace_callback(lambda sql: heartbeat_updates.append(sql)
                        if sql.startswith("UPDATE jobs SET heartbeat=") else None)
                    yield db

            with patch.object(Store, "connection", counted_connection):
                run(store.directory, "eof-budget")
            job = store.job("eof-budget")
            self.assertEqual(job["status"], "completed", job)
            self.assertEqual(job["exit_code"], 0)
            self.assertEqual((root / "after-eof").read_text(), "finished")
            self.assertEqual((store.directory / "jobs/eof-budget.output").read_bytes(), b"")
            self.assertLessEqual(len(heartbeat_updates), 25,
                "A closed output pipe must not spin while the owned process is still running")


if __name__ == "__main__":
    unittest.main()
