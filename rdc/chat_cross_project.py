"""RDC ↔ Atlas/BandMates/Presentation cross-project communication contract.

An independently owned and approved Atlas route dispatcher is required.
The current Atlas Bus v1 core intentionally returns CROSS_PROJECT_DENIED;
this contract MUST NOT bypass or mutate its owner project. Synthetic
dispatchers used in tests are not live enrollment or reviewer approval.
"""
from __future__ import annotations

import hashlib
import json

from .chat_interconnect import _id, _SESSION_RE, _KEY_RE, _valid_text, ChatError


class RouteDenied(ValueError):
    """The proposed cross-project action lacks explicit authenticated approval."""


_PROJECTS = frozenset({"atlas", "rdc", "bandmates", "presentation"})


class CrossProjectChatRouter:
    """One provider-neutral, explicitly approved inter-project routing bridge.

    Identity and grant providers MUST be injected from authenticated server
    services, never built from user model arguments. Dispatchers must
    implement transactional durable no-replay semantics before any real
    external side effect.
    """

    def __init__(self, identities, approvals, dispatcher):
        if not callable(getattr(identities, "verify_actor", None)):
            raise RouteDenied("A trusted sender identity verifier is required.")
        if not callable(getattr(identities, "verify_target", None)):
            raise RouteDenied("A trusted recipient identity verifier is required.")
        if not callable(getattr(approvals, "resolve", None)):
            raise RouteDenied("An independent approved-route service is required.")
        self.identities = identities
        self.approvals = approvals
        self.dispatcher = dispatcher

    @property
    def live_configured(self) -> bool:
        """Diagnostic only; true requires a separately certified adapter."""
        return bool(self.dispatcher is not None
                    and getattr(self.dispatcher, "live_authorized", False) is True
                    and getattr(self.approvals, "live_authorized", False) is True)

    def send(self, source_ref, target_ref, text, *, key: str, kind: str = "message") -> dict:
        if kind != "message":
            raise RouteDenied("Cross-project execution and control operations are disabled.")
        if not isinstance(key, str) or _KEY_RE.fullmatch(key) is None:
            raise RouteDenied("Bounded stable idempotency key required.")
        try:
            text = _valid_text(text)
        except ChatError as exc:
            raise RouteDenied(str(exc)) from exc
        source = self.identities.verify_actor(source_ref)
        target = self.identities.verify_target(target_ref)
        if (not isinstance(source, dict) or source.get("authenticated") is not True
                or not isinstance(target, dict) or target.get("verified") is not True):
            raise RouteDenied("Both source and target need host-verified enrollment.")
        src_project = source.get("project_id")
        dst_project = target.get("project_id")
        src_session = source.get("session_id")
        dst_session = target.get("session_id")
        if (src_project not in _PROJECTS or dst_project not in _PROJECTS
                or src_project == dst_project
                or not isinstance(src_session, str) or _SESSION_RE.fullmatch(src_session) is None
                or not isinstance(dst_session, str) or _SESSION_RE.fullmatch(dst_session) is None):
            raise RouteDenied("Only distinct authorized Atlas project routes are supported.")
        grant = self.approvals.resolve(src_project, dst_project, "message")
        if (not isinstance(grant, dict) or grant.get("approved") is not True
                or grant.get("source_project") != src_project
                or grant.get("destination_project") != dst_project
                or grant.get("operation") != "message"
                or not isinstance(grant.get("grant_id"), str)
                or not grant["grant_id"]
                or not isinstance(grant.get("authorized_by"), str)
                or not grant["authorized_by"]):
            raise RouteDenied("Independent Atlas route approval is absent or invalid.")
        if self.dispatcher is None or not callable(getattr(self.dispatcher,"send_once",None)):
            raise RouteDenied("Approved Atlas dispatch service has not been installed.")
        # One per-target idempotent envelope. No model-supplied project IDs.
        identifier = _id(src_project + ":" + src_session, key, purpose="rdc-atlas-cross-project-v1")
        envelope = {
            "schema_version": "atlas.bus.message.v1",
            "message_id": identifier,
            "correlation_id": identifier,
            "causation_id": None,
            "source_project": src_project,
            "source_session_id": src_session,
            "destination_project": dst_project,
            "destination_session_id": dst_session,
            "message_type": "question",
            "priority": "normal",
            "hop_count": 0,
            "idempotency_key": key,
            "payload": {"channel":"cross-project-chat","text":text},
        }
        # Never call the original BusStore.enqueue to get around its
        # CROSS_PROJECT_DENIED authorization gate. Only the independent
        # Atlas dispatcher may carry an approved cross-project proposal.
        return self.dispatcher.send_once(grant, envelope)
