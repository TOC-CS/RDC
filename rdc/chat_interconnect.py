"""Provider-neutral RDC chat envelope adapter for Atlas Bus v1.

This module has no browser, model, account, token or transport side effects.
The BusStore and trusted session principal are injected by an authorized caller.
Production enrollment is intentionally NOT implemented here.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid

from .errors import RDCError


_SESSION_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_KEY_RE = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")
_SECRET_RE = re.compile(r"(?i)\b(?:password|secret|api[-_ ]?key|bearer|access[-_ ]?token|private[-_ ]?key)\s*[:=]\s*\S+")
_EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")


class ChatError(ValueError):
    """An application-level denial before queuing or touching an external chat."""


def _id(source: str, key: str, *, purpose: str) -> str:
    """Stable unique ID for an idempotency key, with a standards-valid UUIDv4 variant."""
    raw = hashlib.sha256((purpose + "\0" + source + "\0" + key).encode("utf-8")).digest()
    return str(uuid.UUID(bytes=raw[:16], version=4))


def _valid_text(text: object) -> str:
    if not isinstance(text, str) or not text.strip() or len(text) > 3000:
        raise ChatError("Chat text must contain 1 to 3000 characters.")
    if _SECRET_RE.search(text) or _EMAIL_RE.search(text):
        raise ChatError("Potential credential or personal contact content requires a separate approved transfer.")
    if "\0" in text:
        raise ChatError("NUL cannot appear in chat messages.")
    return text


class ChatClient:
    """One bound session's bus adapter. A trusted host must construct it.

    In tests the identity is a synthetic fixture. Do not let a model set the
    principal from untrusted chat text; real identity comes from enrollment.
    """

    def __init__(self, bus, principal_session: str, *, project: str = "rdc", clock_ms=None):
        if not isinstance(principal_session, str) or not _SESSION_RE.fullmatch(principal_session):
            raise ChatError("Invalid bound session identity.")
        if project != "rdc":
            raise ChatError("Only RDC-owned same-project messages are supported by this adapter.")
        self.bus = bus
        self.principal_session = principal_session
        self.project = project
        self._clock = clock_ms if clock_ms is not None else lambda: int(time.time() * 1000)

    def send(self, destination_session: str, text: str, *, key: str, reply_to: str | None = None) -> dict:
        if not isinstance(destination_session, str) or not _SESSION_RE.fullmatch(destination_session):
            raise ChatError("Invalid recipient session.")
        if destination_session == self.principal_session:
            raise ChatError("A chat session cannot send messages to itself.")
        if not isinstance(key, str) or not _KEY_RE.fullmatch(key):
            raise ChatError("An explicit stable idempotency key is required.")
        text = _valid_text(text)
        identifier = _id(self.principal_session, key, purpose="rdc-chat-message-v1")
        correlation = identifier
        cause = None
        hop = 0
        kind = "question"

        if reply_to is not None:
            if not isinstance(reply_to, str):
                raise ChatError("Reply parent must be an existing message ID.")
            parent = self.bus.get_message(reply_to)
            if (parent["destination_session_id"] != self.principal_session
                    or parent["source_session_id"] != destination_session):
                raise ChatError("Reply target does not match the original conversation.")
            source = json.loads(parent["content_json"])
            correlation = source["correlation_id"]
            cause = source["message_id"]
            hop = source["hop_count"] + 1
            if hop > 3:
                raise ChatError("Conversation hop limit reached.")
            kind = "progress"

        envelope = {
            "schema_version": "atlas.bus.message.v1",
            "message_id": identifier,
            "correlation_id": correlation,
            "causation_id": cause,
            "source_project": self.project,
            "source_session_id": self.principal_session,
            "destination_project": self.project,
            "destination_session_id": destination_session,
            "message_type": kind,
            "priority": "normal",
            "hop_count": hop,
            "idempotency_key": key,
            "payload": {"text": text, "channel": "chat"},
        }
        # Same exact envelope on every retry; source/recipient/key changes
        # reach the BusStore's immutable content/idempotency conflict gate.
        return self.bus.enqueue(self.principal_session, envelope)

    def claim(self, *, holder: str) -> dict | None:
        if not isinstance(holder, str) or not _SESSION_RE.fullmatch(holder):
            raise ChatError("A bounded adapter holder is required for claiming.")
        return self.bus.claim_next(self.principal_session, holder, int(self._clock()))

    def mark_fetched(self, claim: dict, *, holder: str) -> dict:
        if not isinstance(claim, dict) or claim.get("envelope", {}).get("destination_session_id") != self.principal_session:
            raise ChatError("Claim belongs to a different recipient session.")
        return self.bus.mark_fetched(
            claim["message_id"], holder, claim["revision"], int(self._clock())
        )

    def ack(self, message_id: str) -> dict:
        return self.bus.ack_session(message_id, self.principal_session, int(self._clock()))

    def confirm(self, message_id: str, *, evidence_digest: str) -> dict:
        if not isinstance(evidence_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", evidence_digest):
            raise ChatError("Actual delivery/action evidence requires a SHA-256 digest.")
        return self.bus.record_action(
            message_id, self.principal_session, evidence_digest, int(self._clock())
        )

    def status(self, message_id: str) -> dict:
        row = self.bus.get_message(message_id)
        if self.principal_session not in (row["source_session_id"], row["destination_session_id"]):
            raise ChatError("Session has no access to this message.")
        return {key: row[key] for key in (
            "source_session_id", "destination_session_id", "state"
        )} | {"message_id": message_id}
