"""Two- and three-participant ChatGPT chat room fanout on an injected Atlas Bus.

This is an isolated synthetic transport adapter, not consumer ChatGPT session
enrollment. Each participant is a separately bound, trusted-in-host principal
in production; terminal fixture labels alone never authenticate a real model.
"""
from __future__ import annotations

import hashlib
import json
import time

from .chat_interconnect import (
    ChatError, _id, _KEY_RE, _SESSION_RE, _valid_text,
)


class ChatRoomError(ChatError):
    """A room membership, causation or request validation refusal."""


class ChatRoom:
    """One participant's bounded room, with individual immutable deliveries."""

    def __init__(self, bus, principal_session: str, members,
                 *, room_key: str, clock_ms=None):
        if not isinstance(principal_session, str) or not _SESSION_RE.fullmatch(principal_session):
            raise ChatRoomError("Invalid local session identity.")
        if not isinstance(room_key, str) or not _KEY_RE.fullmatch(room_key):
            raise ChatRoomError("An owner-selected stable room key is required.")
        if not isinstance(members, (list, tuple, set, frozenset)):
            raise ChatRoomError("Provide two or three exact room participants.")
        original = list(members)
        if (not 2 <= len(original) <= 3
                or any(not isinstance(item, str) or not _SESSION_RE.fullmatch(item)
                       for item in original)
                or len(set(original)) != len(original)
                or principal_session not in original):
            raise ChatRoomError("A room requires two or three distinct permitted participants.")
        self.bus = bus
        self.principal_session = principal_session
        self.members = tuple(sorted(original))
        self.room_key = room_key
        self.room_id = _id("|".join(self.members), room_key,
                           purpose="rdc-chat-room-v1")
        self._clock = clock_ms or (lambda: int(time.time() * 1000))

    def broadcast(self, text: str, *, key: str, parent_id: str | None = None) -> dict:
        """Deliver one envelope per other member and preserve retry receipts.

        Each recipient is independently queued. A partially accepted fanout
        can be retried using the exact original key/content; the bus returns
        immutable receipts for already accepted recipients. There is no
        atomic multi-recipient transaction or automatic cross-chat wake-up.
        """
        try:
            text = _valid_text(text)
        except ChatError as exc:
            raise ChatRoomError(str(exc)) from exc
        if not isinstance(key, str) or not _KEY_RE.fullmatch(key):
            raise ChatRoomError("A stable bounded broadcast request key is required.")
        parent_id = parent_id if parent_id is None else str(parent_id)
        hop = 0
        kind = "question"
        if parent_id is not None:
            parent = self.bus.get_message(parent_id)
            if (parent["destination_session_id"] != self.principal_session
                    or parent["source_session_id"] not in self.members):
                raise ChatRoomError("Reply parent belongs to a different recipient or room participant.")
            envelope = json.loads(parent["content_json"])
            if envelope["correlation_id"] != self.room_id:
                raise ChatRoomError("Reply parent belongs to another chat room.")
            hop = envelope["hop_count"] + 1
            if hop > 3:
                raise ChatRoomError("Chat room has reached its bounded reply hop limit.")
            kind = "progress"

        receipts = {}
        duplicates = {}
        for recipient in self.members:
            if recipient == self.principal_session:
                continue
            # This key must NOT include members/room ID. Reusing the same
            # sender+key to reach a previously contacted destination but with
            # altered participants must fail the bus's original-content gate.
            stable = "room-" + hashlib.sha256(
                (key + "\0" + recipient).encode("utf-8")
            ).hexdigest()
            envelope = {
                "schema_version": "atlas.bus.message.v1",
                "message_id": _id(self.principal_session, stable,
                                  purpose="rdc-chat-message-v1"),
                "correlation_id": self.room_id,
                "causation_id": parent_id,
                "source_project": "rdc",
                "source_session_id": self.principal_session,
                "destination_project": "rdc",
                "destination_session_id": recipient,
                "message_type": kind,
                "priority": "normal",
                "hop_count": hop,
                "idempotency_key": stable,
                "payload": {
                    "text": text,
                    "channel": "chat-room",
                    "room_id": self.room_id,
                    "participants": list(self.members),
                },
            }
            outcome = self.bus.enqueue(self.principal_session, envelope)
            receipts[recipient] = outcome["receipt"]
            duplicates[recipient] = outcome["duplicate"]
        return {
            "room_id": self.room_id,
            "room_size": len(self.members),
            "source_session_id": self.principal_session,
            "receipts": receipts,
            "duplicates": duplicates,
            "scope": "synthetic_fixture_only",
        }
