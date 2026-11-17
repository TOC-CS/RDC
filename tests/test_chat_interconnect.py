"""Cross-chat bridge tests. Synthetic messaging only, no provider login or hidden chat automation."""
import hashlib
import json
import unittest

from rdc.chat_interconnect import ChatClient, ChatError


class FakeBusPort:
    """A deterministic stub for the bridge, not a replacement for the Atlas Bus."""
    def __init__(self):
        self.messages = {}
        self.keys = {}
        self.sessions = {"chatgpt-alpha", "claude-beta", "grok-gamma"}
        self.now_ms = 1794900000000
        self.claims = {}

    def enqueue(self, principal_session, envelope):
        if principal_session != envelope["source_session_id"]:
            raise ValueError("SOURCE_IDENTITY_REJECTED")
        if envelope["destination_session_id"] not in self.sessions:
            raise ValueError("WRONG_DESTINATION")
        if principal_session == envelope["destination_session_id"]:
            raise ValueError("SELF_ECHO")
        key = (principal_session, envelope["idempotency_key"])
        content = json.dumps(envelope, sort_keys=True)
        if key in self.keys:
            old_id = self.keys[key]
            if json.dumps(self.messages[old_id]["envelope"], sort_keys=True) != content:
                raise ValueError("IDEMPOTENCY_CONFLICT")
            return {"receipt": self.messages[old_id]["receipt"], "duplicate": True}
        identifier = envelope["message_id"]
        receipt = {"message_id": identifier, "state": "QUEUED", "content_hash": hashlib.sha256(content.encode()).hexdigest()}
        self.messages[identifier] = {
            "envelope": envelope, "receipt": receipt, "state": "QUEUED",
            "source_session_id": principal_session,
            "destination_session_id": envelope["destination_session_id"],
            "content_json": content,
        }
        self.keys[key] = identifier
        return {"receipt": receipt, "duplicate": False}

    def get_message(self, message_id):
        return self.messages[message_id]

    def claim_next(self, recipient_session, holder, now_ms):
        for identifier, row in self.messages.items():
            if row["destination_session_id"] == recipient_session and row["state"] == "QUEUED":
                row["state"] = "CLAIMED"
                self.claims[identifier] = (holder, 1)
                return {"message_id": identifier, "revision": 1, "envelope": row["envelope"], "state": "CLAIMED"}
        return None

    def mark_fetched(self, message_id, holder, claim_revision, now_ms):
        if self.claims.get(message_id) != (holder, claim_revision):
            raise ValueError("STALE_CLAIM")
        self.messages[message_id]["state"] = "ADAPTER_FETCHED"
        return {"message_id": message_id, "state": "ADAPTER_FETCHED"}

    def ack_session(self, message_id, recipient, now_ms):
        row = self.messages[message_id]
        if row["destination_session_id"] != recipient or row["state"] != "ADAPTER_FETCHED":
            raise ValueError("INVALID_ACK")
        row["state"] = "SESSION_ACKNOWLEDGED"
        return {"message_id": message_id, "state": "SESSION_ACKNOWLEDGED"}

    def record_action(self, message_id, recipient, evidence_digest, now_ms):
        row = self.messages[message_id]
        if row["destination_session_id"] != recipient or row["state"] != "SESSION_ACKNOWLEDGED":
            raise ValueError("ACTION_NOT_RECEIVED")
        row["state"] = "ACTION_CONFIRMED"
        return {"message_id": message_id, "state": "ACTION_CONFIRMED"}


class ChatInterconnectTests(unittest.TestCase):
    def setUp(self):
        self.bus = FakeBusPort()
        self.a = ChatClient(self.bus, "chatgpt-alpha", clock_ms=lambda: self.bus.now_ms)
        self.b = ChatClient(self.bus, "claude-beta", clock_ms=lambda: self.bus.now_ms)
        self.c = ChatClient(self.bus, "grok-gamma", clock_ms=lambda: self.bus.now_ms)

    def test_two_way_chat_and_reply_keep_correlation_and_no_automatic_action(self):
        sent = self.a.send("claude-beta", "Can you review this?", key="review-1")
        claim = self.b.claim(holder="claude-agent")
        self.assertEqual(claim["envelope"]["payload"]["text"], "Can you review this?")
        self.assertEqual(claim["envelope"]["source_session_id"], "chatgpt-alpha")
        self.assertEqual(self.bus.get_message(sent["receipt"]["message_id"])["state"], "CLAIMED")
        self.b.mark_fetched(claim, holder="claude-agent")
        self.b.ack(sent["receipt"]["message_id"])
        self.assertEqual(self.bus.get_message(sent["receipt"]["message_id"])["state"], "SESSION_ACKNOWLEDGED")
        reply = self.b.send("chatgpt-alpha", "Reviewed: looks good.", key="reply-1", reply_to=sent["receipt"]["message_id"])
        got = self.a.claim(holder="chatgpt-agent")
        self.assertEqual(got["envelope"]["payload"]["text"], "Reviewed: looks good.")
        self.assertEqual(got["envelope"]["causation_id"], sent["receipt"]["message_id"])
        self.assertEqual(got["envelope"]["correlation_id"], claim["envelope"]["correlation_id"])
        self.assertEqual(reply["receipt"]["state"], "QUEUED")

    def test_identical_retry_is_deduplicated_and_changed_key_content_conflicts(self):
        first = self.a.send("grok-gamma", "Compare these two reports", key="comp-1")
        self.assertFalse(first["duplicate"])
        second = self.a.send("grok-gamma", "Compare these two reports", key="comp-1")
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["receipt"], second["receipt"])
        self.assertEqual(len(self.bus.messages), 1)
        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_CONFLICT"):
            self.a.send("grok-gamma", "Mutated instructions", key="comp-1")
        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_CONFLICT"):
            self.a.send("claude-beta", "Compare these two reports", key="comp-1")

    def test_self_send_unknown_target_oversized_or_secret_like_message_fail_closed(self):
        with self.assertRaises(ChatError):
            self.a.send("chatgpt-alpha", "echo", key="x")
        with self.assertRaises(ValueError):
            self.a.send("missing-chat", "question", key="missing")
        with self.assertRaises(ChatError):
            self.a.send("claude-beta", "a" * 3001, key="oversize")
        with self.assertRaises(ChatError):
            self.a.send("claude-beta", "password: mySecret", key="sensitive")
        self.assertEqual(self.bus.messages, {})

    def test_unverified_message_does_not_implicitly_ack_or_confirm(self):
        sent = self.a.send("claude-beta", "Task?", key="task-one")
        target = sent["receipt"]["message_id"]
        with self.assertRaises(ValueError):
            self.c.ack(target)
        claim = self.b.claim(holder="worker-1")
        with self.assertRaises(ValueError):
            self.b.mark_fetched(claim, holder="worker-spoof")
        self.assertEqual(self.bus.get_message(target)["state"], "CLAIMED")
        self.b.mark_fetched(claim, holder="worker-1")
        self.b.ack(target)
        evidence = hashlib.sha256(b"verified sandbox result").hexdigest()
        confirmed = self.b.confirm(target, evidence_digest=evidence)
        self.assertEqual(confirmed["state"], "ACTION_CONFIRMED")

    def test_reply_to_other_destination_is_rejected_without_enqueuing(self):
        sent = self.a.send("claude-beta", "question", key="first")
        self.assertEqual(len(self.bus.messages), 1)
        with self.assertRaises(ChatError):
            self.c.send("chatgpt-alpha", "fabricated reply", key="fake", reply_to=sent["receipt"]["message_id"])
        self.assertEqual(len(self.bus.messages), 1)


if __name__ == "__main__":
    unittest.main()
