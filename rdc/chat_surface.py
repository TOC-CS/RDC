"""Capability-gated direct-chat adapter contract for RDC.

A provider adapter may control an explicitly authorized browser/app conversation
or a separately authorized API conversation. This module has no provider
credentials or DOM selectors and never performs network/browser actions itself.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
import re

from .chat_interconnect import ChatError, _valid_text


class ChatSurfaceUnavailable(RuntimeError):
    """The actual host, permission or session binding is unavailable."""


class ChatSurfaceError(ValueError):
    """Input, identity or immutable request integrity problem."""


@runtime_checkable
class ChatSurface(Protocol):
    capabilities: set[str]

    def open_new(self, provider: str) -> dict: ...
    def attach_existing(self, provider: str, reference: str) -> dict: ...
    def submit_once(self, handle: dict, text: str, request_id: str) -> dict: ...
    def observe(self, handle: dict, after: str | None) -> dict: ...
    def reconcile(self, handle: dict, request_id: str) -> dict | None: ...


class ChatSurfaceGateway:
    """One authorized operator's bound chat sessions and no-replay send receipts."""

    MODES = frozenset({"browser", "api", "desktop", "studio"})
    REQ = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")

    def __init__(self, adapter: ChatSurface, *, authorized_providers: set[str],
                 operator_authorized: bool):
        self.adapter = adapter
        self.allowed = set(authorized_providers)
        self.authorized = operator_authorized is True
        self._sessions: dict[str, dict] = {}
        self._requests: dict[str, dict] = {}
        self._opens: dict[str, dict] = {}

    def _permit(self, provider: str, capability: str):
        if not self.authorized or provider not in self.allowed:
            raise ChatSurfaceUnavailable("Provider or operator has no authorized chat access.")
        if capability not in getattr(self.adapter, "capabilities", frozenset()):
            raise ChatSurfaceUnavailable(f"Host does not expose authorized {capability} capability.")

    def _bind(self, provider: str, handle: dict) -> dict:
        if (not isinstance(handle, dict) or handle.get("provider") != provider
                or handle.get("mode") not in self.MODES
                or handle.get("observed") is not True):
            raise ChatSurfaceUnavailable("Host did not verify this exact chat session.")
        opaque = handle.get("opaque_id")
        if not isinstance(opaque, str) or not self.REQ.fullmatch(opaque):
            raise ChatSurfaceUnavailable("Host did not return a usable opaque chat identity.")
        if opaque in self._sessions:
            raise ChatSurfaceUnavailable("Chat handle is already bound; refusing ambiguous reuse.")
        # Retain a copy of the exact verified handle; no global active tab fallback.
        bound = {k: handle[k] for k in ("provider", "opaque_id", "mode", "observed")}
        self._sessions[opaque] = bound
        return bound.copy()

    def _bound(self, handle: dict) -> dict:
        if not isinstance(handle, dict):
            raise ChatSurfaceUnavailable("Verified chat handle required.")
        opaque = handle.get("opaque_id")
        value = self._sessions.get(opaque) if isinstance(opaque, str) else None
        if value is None or value != handle:
            raise ChatSurfaceUnavailable("Chat handle is not bound to this operator/session.")
        self._permit(value["provider"], "observe")
        return value

    def open_new(self, provider: str, *, request_id: str) -> dict:
        """Open a new chat once per stable request, never duplicate an uncertain create."""
        self._permit(provider, "open_new")
        # A newly created chat must actually support both directions.
        self._permit(provider, "submit_once")
        self._permit(provider, "observe")
        if not isinstance(request_id, str) or not self.REQ.fullmatch(request_id):
            raise ChatSurfaceError("A stable new-chat request ID is required.")
        prior = self._opens.get(request_id)
        if prior is not None:
            if prior["provider"] != provider:
                raise ChatSurfaceError("New-chat request ID belongs to another provider.")
            return prior.copy()
        pending = {"provider": provider, "request_id": request_id, "state": "OUTCOME_UNKNOWN"}
        self._opens[request_id] = pending
        try:
            observed = self.adapter.open_new(provider)
            verified = self._bind(provider, observed)
        except Exception:
            # A timeout might occur AFTER a new consumer chat was opened.
            # Returning UNKNOWN stops accidental second-chat creation.
            return pending.copy()
        self._opens[request_id] = verified.copy()
        return verified.copy()

    def attach_existing(self, provider: str, reference: str) -> dict:
        """Attach a user-approved existing conversation; never discover hidden tabs."""
        self._permit(provider, "attach_existing")
        self._permit(provider, "submit_once")
        self._permit(provider, "observe")
        if not isinstance(reference, str) or not self.REQ.fullmatch(reference):
            raise ChatSurfaceError("Exact owner-approved chat reference required.")
        try:
            observed = self.adapter.attach_existing(provider, reference)
        except (PermissionError, NotImplementedError) as exc:
            raise ChatSurfaceUnavailable("Host did not authorize this existing chat.") from exc
        return self._bind(provider, observed)

    def submit(self, handle: dict, text: str, *, request_id: str) -> dict:
        verified = self._bound(handle)
        self._permit(verified["provider"], "submit_once")
        if not isinstance(request_id, str) or not self.REQ.fullmatch(request_id):
            raise ChatSurfaceError("A stable request ID is required.")
        try:
            payload = _valid_text(text)
        except ChatError as exc:
            raise ChatSurfaceError(str(exc)) from exc
        prior = self._requests.get(request_id)
        if prior is not None:
            if prior["handle_id"] != verified["opaque_id"] or prior["text"] != payload:
                raise ChatSurfaceError("A reused chat request ID has changed its recipient or content.")
            return prior["receipt"].copy()

        receipt = {"request_id": request_id, "state": "OUTCOME_UNKNOWN",
                   "session_id": verified["opaque_id"]}
        # Save unknown BEFORE calling the potentially mutating host. No retries
        # after timeouts, UI denial or tool-side delivery uncertainty.
        record = {"handle_id": verified["opaque_id"], "text": payload, "receipt": receipt}
        self._requests[request_id] = record
        try:
            result = self.adapter.submit_once(verified.copy(), payload, request_id)
            if (isinstance(result, dict) and result.get("submitted") is True
                    and result.get("observed") is True
                    and isinstance(result.get("host_message_id"), str)
                    and result["host_message_id"]):
                receipt["state"] = "SUBMITTED_OBSERVED"
                receipt["host_message_id"] = result["host_message_id"][:200]
        except (Exception,):
            # A failure may happen AFTER the host submitted a message. Retain
            # unknown state and require readback, never blindly send again.
            pass
        return receipt.copy()

    def observe(self, handle: dict, *, after: str | None = None) -> dict:
        verified = self._bound(handle)
        if after is not None and (not isinstance(after, str) or len(after) > 200):
            raise ChatSurfaceError("A bounded observation cursor is required.")
        output = self.adapter.observe(verified.copy(), after)
        if not isinstance(output, dict) or not isinstance(output.get("messages"), list):
            raise ChatSurfaceUnavailable("Host did not return an observed chat transcript slice.")
        messages = output["messages"]
        if len(messages) > 10:
            raise ChatSurfaceUnavailable("Observed chat result is unbounded; narrow the cursor.")
        filtered = []
        for item in messages:
            if not isinstance(item, dict):
                raise ChatSurfaceUnavailable("Host returned invalid message evidence.")
            if item.get("role") not in ("assistant", "user") or not isinstance(item.get("message_id"), str):
                raise ChatSurfaceUnavailable("Host returned invalid chat source identity.")
            text = item.get("text")
            if not isinstance(text, str) or len(text) > 3000:
                raise ChatSurfaceUnavailable("Observed chat message is larger than the allowed slice.")
            filtered.append({"role": item["role"], "message_id": item["message_id"], "text": text})
        cursor = output.get("cursor")
        if cursor is not None and (not isinstance(cursor, str) or len(cursor) > 200):
            raise ChatSurfaceUnavailable("Invalid host observation cursor.")
        return {"session_id": verified["opaque_id"], "messages": filtered,
                "cursor": cursor, "observed": True}

    def reconcile(self, handle: dict, *, request_id: str) -> dict:
        verified = self._bound(handle)
        existing = self._requests.get(request_id)
        if existing is None or existing["handle_id"] != verified["opaque_id"]:
            raise ChatSurfaceError("Unknown or foreign request ID.")
        current = existing["receipt"]
        if current["state"] != "OUTCOME_UNKNOWN":
            return current.copy()
        if "reconcile" not in getattr(self.adapter, "capabilities", frozenset()):
            return current.copy()
        try:
            result = self.adapter.reconcile(verified.copy(), request_id)
        except Exception:
            return current.copy()
        if (isinstance(result, dict) and result.get("request_id") == request_id
                and result.get("observed") is True and result.get("submitted") is True
                and isinstance(result.get("host_message_id"), str)
                and result["host_message_id"]):
            current["state"] = "SUBMITTED_OBSERVED"
            current["host_message_id"] = result["host_message_id"][:200]
        return current.copy()
