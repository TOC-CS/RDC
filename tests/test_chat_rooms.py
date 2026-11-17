"""Two- and three-way ChatGPT fixture rooms over the existing Atlas Bus.
Every recipient gets a separate durable envelope with one shared correlation ID.
No real ChatGPT tab or model is contacted by these tests.
"""
import os
from pathlib import Path
import tempfile
import unittest

from rdc.chat_rooms import ChatRoom, ChatRoomError
from rdc.chat_interconnect import ChatClient

ATLAS = Path(os.environ.get("RDC_ATLAS_BUS_TEST_ROOT", "/nonexistent/atlas-bus"))
READY = (ATLAS / "atlasbus" / "store.py").is_file()


@unittest.skipUnless(READY, "Atlas Bus source unavailable")
class ThreeWayRoomTests(unittest.TestCase):
    def setUp(self):
        import sys
        sys.path.insert(0, str(ATLAS))
        from atlasbus.store import BusStore
        self.temp = tempfile.TemporaryDirectory(prefix="rdc-3way-test-")
        self.now = 1794900000000
        self.bus = BusStore(Path(self.temp.name) / "room.sqlite3",
                            clock_ms=lambda: self.now, synthetic_mode=True)
        self.members = ("chatgpt-alpha", "chatgpt-beta", "chatgpt-gamma")
        for member in self.members:
            self.bus.register_synthetic_session("rdc", member)

    def tearDown(self):
        import sys
        self.bus.close()
        self.temp.cleanup()
        if str(ATLAS) in sys.path:
            sys.path.remove(str(ATLAS))

    def room(self, sender, members=None, key="owner-room-20261117"):
        return ChatRoom(self.bus, sender, members or self.members, room_key=key,
                        clock_ms=lambda: self.now)

    def test_three_way_room_fanout_and_reply_to_both_peers_share_correlation(self):
        a = self.room("chatgpt-alpha")
        b = self.room("chatgpt-beta")
        c = self.room("chatgpt-gamma")
        announcement = a.broadcast("Please review the plan", key="task-1")
        self.assertEqual(set(announcement["receipts"]), {"chatgpt-beta", "chatgpt-gamma"})
        self.assertEqual(len({x["message_id"] for x in announcement["receipts"].values()}), 2)
        claim_b = ChatClient(self.bus, "chatgpt-beta", clock_ms=lambda: self.now).claim(holder="beta-lease")
        claim_c = ChatClient(self.bus, "chatgpt-gamma", clock_ms=lambda: self.now).claim(holder="gamma-lease")
        self.assertEqual(claim_b["envelope"]["correlation_id"], a.room_id)
        self.assertEqual(claim_c["envelope"]["correlation_id"], a.room_id)
        self.assertEqual(claim_b["envelope"]["payload"]["text"], "Please review the plan")
        self.assertEqual(claim_c["envelope"]["payload"]["text"], "Please review the plan")
        reply = b.broadcast("I completed my review", key="task-2",
                            parent_id=claim_b["message_id"])
        self.assertEqual(set(reply["receipts"]), {"chatgpt-alpha", "chatgpt-gamma"})
        self.assertEqual(reply["room_id"], announcement["room_id"])
        for receipt in reply["receipts"].values():
            envelope = self.bus.get_message(receipt["message_id"])
            import json
            payload = json.loads(envelope["content_json"])
            self.assertEqual(payload["correlation_id"], a.room_id)
            self.assertEqual(payload["causation_id"], claim_b["message_id"])
            self.assertEqual(payload["hop_count"], 1)
        received_a = ChatClient(self.bus, "chatgpt-alpha",
                                clock_ms=lambda: self.now).claim(holder="alpha-lease")
        self.assertEqual(received_a["envelope"]["source_session_id"], "chatgpt-beta")

    def test_same_room_and_key_retries_original_receipts_and_changed_text_conflicts(self):
        room = self.room("chatgpt-alpha")
        first = room.broadcast("Same task", key="stable-123")
        second = room.broadcast("Same task", key="stable-123")
        self.assertEqual(first["receipts"], second["receipts"])
        self.assertTrue(all(second["duplicates"].values()))
        self.assertEqual(len(self.bus.connection.execute("SELECT 1 FROM messages").fetchall()), 2)
        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_CONFLICT"):
            room.broadcast("Changed instruction", key="stable-123")
        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_CONFLICT"):
            self.room("chatgpt-alpha", members=("chatgpt-alpha", "chatgpt-beta")).broadcast(
                "Same task", key="stable-123")

    def test_invalid_room_or_foreign_sender_or_wrong_parent_is_denied(self):
        with self.assertRaises(ChatRoomError):
            self.room("unknown-chat")
        with self.assertRaises(ChatRoomError):
            self.room("chatgpt-alpha", members=("chatgpt-alpha",))
        with self.assertRaises(ChatRoomError):
            self.room("chatgpt-alpha", members=self.members + ("fourth",))
        a = self.room("chatgpt-alpha")
        b = self.room("chatgpt-beta")
        sent = a.broadcast("Question", key="source-1")
        recipient_for_c = sent["receipts"]["chatgpt-gamma"]["message_id"]
        with self.assertRaises(ChatRoomError):
            b.broadcast("Spoofed parent", key="spoof-1", parent_id=recipient_for_c)
        self.assertEqual(len(self.bus.connection.execute("SELECT 1 FROM messages").fetchall()), 2)

    def test_two_member_room_routes_one_message_and_is_idempotent(self):
        room = self.room("chatgpt-alpha", members=("chatgpt-beta", "chatgpt-alpha"),
                         key="paired-session")
        sent = room.broadcast("Hello other ChatGPT chat", key="one")
        self.assertEqual(set(sent["receipts"]), {"chatgpt-beta"})
        self.assertEqual(sent["room_size"], 2)
        self.assertTrue(room.broadcast("Hello other ChatGPT chat", key="one")["duplicates"]["chatgpt-beta"])

    def test_third_party_cannot_read_other_rooms_by_guessing_correlation(self):
        a = self.room("chatgpt-alpha")
        b = self.room("chatgpt-beta")
        sent = a.broadcast("One room", key="first")
        self.assertEqual(b.room_id, a.room_id)
        with self.assertRaises(ChatRoomError):
            other = self.room("chatgpt-gamma", members=("chatgpt-gamma", "chatgpt-beta"), key="other-room")
            other.broadcast("Mismatched room", key="first", parent_id=sent["receipts"]["chatgpt-beta"]["message_id"])


if __name__ == "__main__":
    unittest.main()
