"""Real detached-worker acceptance for the bounded RDC terminal fast path."""
from pathlib import Path
import os
import subprocess
from unittest.mock import patch
import sys
import tempfile
import time
import unittest

from rdc.config import Settings
from rdc.engine import Engine


class TerminalFastPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="rdc-terminal-fastpath-")
        self.root = Path(self.tmp.name)
        self.engine = Engine(Settings(
            state_dir=self.root / "state", roots=[self.root],
            browser_backend="disabled", approval_mode="trusted", allow_exec=True,
        ))
        # Retain actual child handles: a terminal DB row precedes interpreter exit.
        # The inherited worker log remains locked on Windows until that exit.
        self.workers = []
        real_popen = subprocess.Popen

        def launch(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            self.workers.append(process)
            return process

        launcher = patch("rdc.jobs.subprocess.Popen", side_effect=launch)
        launcher.start()
        self.addCleanup(launcher.stop)

    def tearDown(self):
        deadline = time.monotonic() + 12
        try:
            for process in self.workers:
                process.wait(timeout=max(.01, deadline - time.monotonic()))
        finally:
            self.engine.close()
            self.tmp.cleanup()

    def run_command(self, script, **kwargs):
        return self.engine.call("rdc_job_run", {
            "argv": [sys.executable, "-c", script],
            "cwd": str(self.root),
            **kwargs,
        })

    def test_short_command_returns_output_and_exit_in_one_call(self):
        result = self.run_command("print('ONE-CALL-READY')", wait_ms=3000)
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["complete"], result)
        self.assertEqual(result["job"]["status"], "completed")
        self.assertEqual(result["job"]["exit_code"], 0)
        self.assertEqual(result["output"]["text"], "ONE-CALL-READY" + os.linesep)
        self.assertTrue(result["output"]["complete"])
        self.assertEqual(result["output"]["job_id"], result["job"]["id"])

    def test_zero_wait_returns_durable_job_that_later_completes(self):
        result = self.run_command("import time; time.sleep(.5); print('LATE-READY')", wait_ms=0)
        self.assertTrue(result["ok"], result)
        self.assertFalse(result["complete"], result)
        identifier = result["job"]["id"]
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            state = self.engine.call("rdc_job_status", {"job_id": identifier})
            if state["job"]["status"] not in ("queued", "running", "cancelling"):
                break
            time.sleep(.05)
        else:
            self.fail("Durable job did not settle after bounded wait")
        self.assertEqual(state["job"]["status"], "completed")
        output = self.engine.call("rdc_job_output", {"job_id": identifier})
        self.assertTrue(output["ok"], output)
        self.assertEqual(output["text"], "LATE-READY" + os.linesep)

    def test_same_key_reuses_job_and_different_spec_conflicts(self):
        script = "print('DEDUP-READY')"
        initial = self.run_command(script, wait_ms=3000, idempotency_key="fastpath-dedup")
        self.assertTrue(initial["ok"], initial)
        repeated = self.run_command(script, wait_ms=0, idempotency_key="fastpath-dedup")
        self.assertTrue(repeated["ok"], repeated)
        self.assertTrue(repeated["reused"], repeated)
        self.assertEqual(initial["job"]["id"], repeated["job"]["id"])
        conflict = self.run_command("print('DIFFERENT')", wait_ms=0, idempotency_key="fastpath-dedup")
        self.assertFalse(conflict["ok"], conflict)
        self.assertEqual(conflict["error"]["code"], "idempotency_conflict")

    def test_nonzero_exit_and_bounded_output_are_truthful(self):
        failed = self.run_command("import sys; print('ERR-7',file=sys.stderr); sys.exit(7)", wait_ms=3000)
        self.assertTrue(failed["ok"], failed)
        self.assertTrue(failed["complete"], failed)
        self.assertEqual(failed["job"]["status"], "failed")
        self.assertEqual(failed["job"]["exit_code"], 7)
        self.assertIn("ERR-7", failed["output"]["text"])
        bounded = self.run_command("print('ABCDEFGHIJKL')", wait_ms=3000, output_limit=4)
        self.assertTrue(bounded["ok"], bounded)
        self.assertTrue(bounded["complete"], bounded)
        self.assertEqual(bounded["output"]["text"], "ABCD")
        self.assertEqual(bounded["output"]["next_offset"], 4)
        self.assertGreater(bounded["output"]["bytes_available"], 4)

    def test_post_launch_output_error_preserves_durable_id_without_leaking_cause(self):
        script = "print('RECOVERABLE-ONE')"
        with patch.object(self.engine.jobs, "output", side_effect=OSError("PRIVATE-IO-DETAILS")):
            failed = self.run_command(script, wait_ms=3000, idempotency_key="recoverable-one")
        self.assertFalse(failed["ok"], failed)
        self.assertEqual(failed["error"]["code"], "result_unavailable")
        identity = failed["error"]["details"]["job_id"]
        self.assertNotIn("PRIVATE-IO-DETAILS", str(failed))
        retry = self.run_command(script, wait_ms=3000, idempotency_key="recoverable-one")
        self.assertTrue(retry["ok"], retry)
        self.assertTrue(retry["reused"])
        self.assertEqual(retry["job"]["id"], identity)
        self.assertEqual(retry["output"]["text"], "RECOVERABLE-ONE" + os.linesep)

    def test_zero_wait_does_not_read_output_or_touch_unneeded_log(self):
        with patch.object(self.engine.jobs, "output", side_effect=OSError("unexpected immediate I/O")):
            pending = self.run_command("import time;time.sleep(.35)", wait_ms=0)
        self.assertTrue(pending["ok"], pending)
        self.assertFalse(pending["complete"])
        self.assertIsNone(pending["output"])
        self.assertTrue(pending["job"]["id"])

    def test_regular_output_reader_refuses_symlink_to_external_file(self):
        if os.name == "nt":
            self.skipTest("Windows symlink creation may require special privileges")
        result = self.run_command("print('PUBLIC-OUTPUT')", wait_ms=3000)
        self.assertTrue(result["ok"], result)
        identifier = result["job"]["id"]
        secret = self.root / "PRIVATE-NOT-AN-OUTPUT"
        secret.write_text("PRIVATE-MARKER-MUST-NOT-LEAK")
        log = self.engine.jobs.directory / (identifier + ".output")
        log.unlink()
        log.symlink_to(secret)
        response = self.engine.call("rdc_job_output", {"job_id": identifier})
        self.assertFalse(response["ok"], response)
        self.assertEqual(response["error"]["code"], "output_unavailable")
        self.assertNotIn("PRIVATE-MARKER-MUST-NOT-LEAK", str(response))

    def test_fastpath_is_visible_in_activity_feed(self):
        result = self.run_command("print('OBSERVED-ONE')", wait_ms=3000)
        self.assertTrue(result["ok"], result)
        report = self.engine.call("rdc_preview_activity", {})
        self.assertTrue(report["ok"], report)
        tools = [row["tool"] for row in report["recent_operations"]]
        self.assertIn("rdc_job_run", tools)

    def test_authorization_and_schema_constraints_prevent_dispatch(self):
        expected_before = len(self.engine.call("rdc_job_list", {})["jobs"])
        invalid = self.run_command("print(1)", wait_ms=3001)
        self.assertFalse(invalid["ok"], invalid)
        self.assertEqual(invalid["error"]["code"], "invalid_arguments")
        self.assertEqual(len(self.engine.call("rdc_job_list", {})["jobs"]), expected_before)
        self.engine.store.set("paused", "true")
        paused = self.run_command("print(1)")
        self.assertFalse(paused["ok"], paused)
        self.assertEqual(paused["error"]["code"], "paused")
        self.engine.store.set("paused", "false")
        unauthorized = self.engine.call("rdc_job_run", {
            "argv": [sys.executable, "-c", "print(1)"],
            "cwd": str(self.root / "outside-not-created"),
        })
        self.assertFalse(unauthorized["ok"], unauthorized)

        locked = Engine(Settings(
            state_dir=self.root / "locked", roots=[self.root],
            browser_backend="disabled", allow_exec=False,
        ))
        try:
            result = locked.call("rdc_job_run", {"argv": [sys.executable], "cwd": str(self.root)})
            self.assertFalse(result["ok"], result)
            self.assertEqual(result["error"]["code"], "capability_disabled")
        finally:
            locked.close()

        reviewing = Engine(Settings(
            state_dir=self.root / "review", roots=[self.root],
            browser_backend="disabled", approval_mode="review", allow_exec=True,
        ))
        try:
            queued = reviewing.call("rdc_job_run", {
                "argv": [sys.executable, "-c", "print(1)"], "cwd": str(self.root),
            })
            self.assertEqual(queued["status"], "pending_approval")
            self.assertEqual(reviewing.call("rdc_job_list", {})["jobs"], [])
        finally:
            reviewing.close()


if __name__ == "__main__":
    unittest.main()
