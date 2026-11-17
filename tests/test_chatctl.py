"""RDC synthetic terminal chat messages through the actual Atlas Bus core."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ATLAS = Path(os.environ.get("RDC_ATLAS_BUS_TEST_ROOT", "/nonexistent/atlas-bus"))
HAS_ATLAS = (ATLAS / "atlasbus" / "store.py").is_file()
REPO = Path(__file__).resolve().parents[1]


def command(db, *args, synthetic=True):
    argv = [sys.executable, "-m", "rdc.chatctl"]
    if synthetic:
        argv += ["--synthetic-only", "--atlas-source", str(ATLAS), "--db", str(db)]
    argv += list(args)
    result = subprocess.run(
        argv, text=True, capture_output=True, timeout=15, cwd=REPO,
        env={**os.environ, "PYTHONPATH": str(REPO)},
    )
    try:
        data = json.loads(result.stdout) if result.stdout.strip() else {}
    except ValueError as exc:
        raise AssertionError("CLI failed to return JSON data") from exc
    return result.returncode, data, result.stderr


class CLIRefusalTests(unittest.TestCase):
    def test_requires_explicit_sandbox_and_does_not_auto_enroll(self):
        with tempfile.TemporaryDirectory() as work:
            code, data, error = command(Path(work) / "messages.sqlite3", "sessions", synthetic=False)
            self.assertNotEqual(code, 0)
            self.assertFalse(data.get("ok", False))
            self.assertNotIn("registered", str(data).lower())

    def test_help_advertises_synthetic_only_and_authorized_sources(self):
        help_text = subprocess.run(
            [sys.executable, "-m", "rdc.chatctl", "--help"],
            text=True, capture_output=True, cwd=REPO, timeout=10,
            env={**os.environ, "PYTHONPATH": str(REPO)},
        )
        self.assertEqual(help_text.returncode, 0)
        self.assertIn("--synthetic-only", help_text.stdout)
        self.assertIn("synthetic", help_text.stdout.lower())


@unittest.skipUnless(HAS_ATLAS, "Optional Atlas Bus source is not available in this test environment")
class CLIAtlasBusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rdc-chat-cli-")
        self.db = Path(self.temp.name) / "messages.sqlite3"
        code, data, error = command(
            self.db, "init", "--session", "chatgpt-fixture", "--session", "claude-fixture",
            "--session", "grok-fixture", "--session", "bandmates-fixture",
        )
        self.assertEqual(code, 0, (data, error))

    def tearDown(self):
        self.temp.cleanup()

    def ok(self, *args):
        code, data, error = command(self.db, *args)
        self.assertEqual(code, 0, (args, data, error))
        self.assertTrue(data["ok"], (args, data, error))
        return data

    def test_bidirectional_terminal_messages_across_processes_with_receipts(self):
        listing = self.ok("sessions")
        self.assertEqual(set(listing["sessions"]), {
            "chatgpt-fixture", "claude-fixture", "grok-fixture", "bandmates-fixture",
        })
        sent = self.ok("send", "--from", "chatgpt-fixture", "--to", "claude-fixture",
                       "--key", "cli-review-1", "--text", "Review this source")
        root = sent["receipt"]["message_id"]
        claimed = self.ok("claim", "--as", "claude-fixture", "--holder", "claude-reader-1")
        self.assertEqual(claimed["claim"]["message_id"], root)
        self.assertEqual(claimed["claim"]["envelope"]["payload"]["text"], "Review this source")
        fetched = self.ok("fetch", "--as", "claude-fixture", "--message-id", root,
                          "--holder", "claude-reader-1", "--revision",
                          str(claimed["claim"]["revision"]))
        self.assertEqual(fetched["receipt"]["state"], "ADAPTER_FETCHED")
        self.assertEqual(self.ok("ack", "--as", "claude-fixture",
                                 "--message-id", root)["receipt"]["state"], "SESSION_ACKNOWLEDGED")
        reply = self.ok("reply", "--as", "claude-fixture", "--to", "chatgpt-fixture",
                        "--key", "cli-reply-1", "--parent-id", root,
                        "--text", "Reviewed and verified.")
        incoming = self.ok("claim", "--as", "chatgpt-fixture", "--holder", "chatgpt-reader-1")["claim"]
        self.assertEqual(incoming["message_id"], reply["receipt"]["message_id"])
        self.assertEqual(incoming["envelope"]["causation_id"], root)
        self.assertEqual(incoming["envelope"]["payload"]["text"], "Reviewed and verified.")
        self.assertEqual(self.ok("status", "--as", "chatgpt-fixture",
                                 "--message-id", root)["message"]["state"], "SESSION_ACKNOWLEDGED")

    def test_duplicate_key_reuses_original_id_and_changed_content_fails(self):
        first = self.ok("send", "--from", "chatgpt-fixture", "--to", "grok-fixture",
                        "--key", "cli-same-key", "--text", "First request")
        second = self.ok("send", "--from", "chatgpt-fixture", "--to", "grok-fixture",
                         "--key", "cli-same-key", "--text", "First request")
        self.assertTrue(second["duplicate"])
        self.assertEqual(second["receipt"], first["receipt"])
        code, data, error = command(
            self.db, "send", "--from", "chatgpt-fixture", "--to", "grok-fixture",
            "--key", "cli-same-key", "--text", "Malicious changed request"
        )
        self.assertNotEqual(code, 0)
        self.assertEqual(data.get("error"), "IDEMPOTENCY_CONFLICT")
        code, data, error = command(
            self.db, "status", "--as", "claude-fixture",
            "--message-id", first["receipt"]["message_id"])
        self.assertNotEqual(code, 0)
        self.assertEqual(data.get("error"), "ACCESS_DENIED")

    def test_two_and_three_way_chatgpt_rooms_across_independent_cli_processes(self):
        members = "chatgpt-fixture,claude-fixture,grok-fixture"
        room = self.ok("room-id", "--as", "chatgpt-fixture", "--members", members,
                       "--room-key", "operator-room-1")
        self.assertEqual(room["room_size"], 3)
        broadcast = self.ok("room-send", "--from", "chatgpt-fixture", "--members", members,
                            "--room-key", "operator-room-1", "--key", "invite-1",
                            "--text", "Review our shared task")
        self.assertEqual(set(broadcast["receipts"]), {"claude-fixture", "grok-fixture"})
        self.assertEqual(broadcast["room_id"], room["room_id"])
        claimed_claude = self.ok("claim", "--as", "claude-fixture", "--holder", "claude-room-reader")["claim"]
        claimed_grok = self.ok("claim", "--as", "grok-fixture", "--holder", "grok-room-reader")["claim"]
        self.assertEqual(claimed_claude["envelope"]["correlation_id"], room["room_id"])
        self.assertEqual(claimed_grok["envelope"]["correlation_id"], room["room_id"])
        replied = self.ok("room-send", "--from", "claude-fixture", "--members", members,
                          "--room-key", "operator-room-1", "--key", "reply-1",
                          "--parent-id", claimed_claude["message_id"],
                          "--text", "Reviewed: ready for the next step")
        self.assertEqual(set(replied["receipts"]), {"chatgpt-fixture", "grok-fixture"})
        claim_back = self.ok("claim", "--as", "chatgpt-fixture", "--holder", "chatgpt-room-reader")["claim"]
        self.assertEqual(claim_back["envelope"]["causation_id"], claimed_claude["message_id"])
        self.assertEqual(claim_back["envelope"]["correlation_id"], room["room_id"])
        repeated = self.ok("room-send", "--from", "chatgpt-fixture", "--members", members,
                           "--room-key", "operator-room-1", "--key", "invite-1",
                           "--text", "Review our shared task")
        self.assertEqual(broadcast["receipts"], repeated["receipts"])
        self.assertTrue(all(repeated["duplicates"].values()))

    def test_room_membership_and_mutated_request_are_denied(self):
        members = "chatgpt-fixture,claude-fixture,grok-fixture"
        self.ok("room-send", "--from", "chatgpt-fixture", "--members", members,
                "--room-key", "operator-room-1", "--key", "stable-1", "--text", "A task")
        code, result, _ = command(self.db, "room-send", "--from", "chatgpt-fixture",
                                  "--members", "chatgpt-fixture,claude-fixture",
                                  "--room-key", "operator-room-1", "--key", "stable-1",
                                  "--text", "A task")
        self.assertNotEqual(code, 0)
        self.assertEqual(result["error"], "IDEMPOTENCY_CONFLICT")
        code, result, _ = command(self.db, "room-send", "--from", "chatgpt-fixture",
                                  "--members", "claude-fixture,grok-fixture",
                                  "--room-key", "operator-room-1", "--key", "invalid-member",
                                  "--text", "A task")
        self.assertNotEqual(code, 0)
        self.assertFalse(result["ok"])

    def test_symlinked_database_argument_refuses_unsafe_redirect(self):
        target = Path(self.temp.name) / "not-created.sqlite3"
        link = Path(self.temp.name) / "alias.sqlite3"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("Creating file symlinks requires platform permission")
        code, data, error = command(link, "init", "--session", "other-fixture")
        self.assertNotEqual(code, 0)
        self.assertFalse(data.get("ok", False))
        self.assertFalse(target.exists(), "An aliased input must not create a redirected database")

    def test_bandmates_is_a_synthetic_endpoint_not_live_app(self):
        sent = self.ok("send", "--from", "chatgpt-fixture", "--to", "bandmates-fixture",
                       "--key", "mix-cue-1", "--text", "Request status of mixer")
        received = self.ok("claim", "--as", "bandmates-fixture", "--holder", "studio-fixture")
        self.assertEqual(received["claim"]["message_id"], sent["receipt"]["message_id"])
        self.assertEqual(received["claim"]["envelope"]["payload"]["text"], "Request status of mixer")
        self.assertEqual(received["scope"], "synthetic_fixture_only")


if __name__ == "__main__":
    unittest.main()
