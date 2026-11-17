"""Fail-closed per-session continuity policy for RDC/DC peer-chat delivery.

The durable bus can queue messages regardless of recipient availability.
Direct chat delivery is separately gated, preserving other active sessions.
This is local synthetic/adapter evidence, NOT a provider authentication
system, browser process controller, or ChatGPT session restarter.
"""
from __future__ import annotations

from threading import RLock
import time

from .chat_interconnect import _SESSION_RE


class ContinuityDenied(ValueError):
    """A peer identity, delivery reservation or recovery was refused."""


class ContinuityGate:
    """One adapter's per-recipient readiness, opt-in, and no-replay policy.

    A real host MUST authenticate the actor outside this class. Matching
    untrusted ID strings is only an isolated fixture contract. Gate restarts
    fail closed and never assume previously permitted browser access.
    """

    def __init__(self, *, clock_ms=None, stale_after_ms=90_000):
        if type(stale_after_ms) is not int or not 1_000 <= stale_after_ms <= 600_000:
            raise ContinuityDenied("Heartbeat stale threshold must be bounded.")
        self._clock = clock_ms or (lambda: int(time.time() * 1000))
        self._stale_after_ms = stale_after_ms
        self._sessions = {}
        self._lock = RLock()

    def _identity(self, session_id, actor):
        if (not isinstance(session_id, str)
                or not _SESSION_RE.fullmatch(session_id)
                or actor != session_id):
            raise ContinuityDenied("Only the exact trusted recipient adapter may change its presence.")

    @staticmethod
    def _epoch(epoch):
        if type(epoch) is not int or epoch < 1:
            raise ContinuityDenied("A positive integer connection epoch is required.")

    def heartbeat(self, session_id, *, actor, epoch, busy, direct_opt_in):
        self._identity(session_id, actor)
        self._epoch(epoch)
        if type(busy) is not bool or type(direct_opt_in) is not bool:
            raise ContinuityDenied("Busy and direct opt-in must be explicit booleans.")
        with self._lock:
            previous = self._sessions.get(session_id)
            if previous is not None:
                if previous["interrupted"] or previous["unconfirmed"]:
                    raise ContinuityDenied("Interrupted or unconfirmed sessions require explicit verified recovery.")
                if previous["epoch"] != epoch:
                    raise ContinuityDenied("Connection epoch changed without an explicit rebind.")
            self._sessions[session_id] = {
                "epoch": epoch,
                "busy": busy,
                "direct_opt_in": direct_opt_in,
                "last_seen_ms": int(self._clock()),
                "interrupted": False,
                "unconfirmed": False,
            }
            return self.direct_status(session_id)

    def reserve_direct(self, session_id, *, actor):
        """Atomically admit ONE direct peer submission, then mark target busy.

        The lock protects this in-process gate against multiple concurrent
        agents. An approved recipient must send a fresh idle/opt-in heartbeat
        after handling the first message before another may be injected.
        """
        self._identity(session_id, actor)
        with self._lock:
            status = self.direct_status(session_id)
            if status["allowed"] is not True:
                return status
            state = self._sessions[session_id]
            state["busy"] = True
            state["direct_opt_in"] = False
            return {**status, "reason": "DIRECT_RESERVED"}

    def unconfirmed(self, session_id, *, actor):
        """Suspend further pushes when delivery is uncertain, without asserting stop."""
        self._identity(session_id, actor)
        with self._lock:
            previous = self._sessions.get(session_id)
            if previous is None:
                raise ContinuityDenied("Unknown peer cannot report a delivery outcome.")
            previous["unconfirmed"] = True
            previous["direct_opt_in"] = False
            return self.direct_status(session_id)

    def interrupted(self, session_id, *, actor):
        self._identity(session_id, actor)
        with self._lock:
            previous = self._sessions.get(session_id)
            if previous is None:
                raise ContinuityDenied("Unknown recipient sessions cannot be marked as recovered or interrupted.")
            previous["interrupted"] = True
            previous["direct_opt_in"] = False
            return self.direct_status(session_id)

    def resume(self, session_id, *, actor, epoch, verified):
        self._identity(session_id, actor)
        self._epoch(epoch)
        with self._lock:
            previous = self._sessions.get(session_id)
            if previous is None or not (previous["interrupted"] or previous["unconfirmed"]):
                raise ContinuityDenied("No interrupted or unconfirmed session has a recovery request.")
            if verified is not True or epoch <= previous["epoch"]:
                raise ContinuityDenied("Recovery needs observed proof and a newer connection epoch.")
            # A recovered chat is never automatically opted back into direct
            # delivery. The receiving model must explicitly report READY.
            self._sessions[session_id] = {
                "epoch": epoch,
                "busy": False,
                "direct_opt_in": False,
                "last_seen_ms": int(self._clock()),
                "interrupted": False,
                "unconfirmed": False,
            }
            return self.direct_status(session_id)

    def direct_status(self, session_id):
        if not isinstance(session_id, str) or not _SESSION_RE.fullmatch(session_id):
            raise ContinuityDenied("Invalid recipient session identity.")
        with self._lock:
            previous = self._sessions.get(session_id)
            if previous is None:
                reason = "UNVERIFIED_SESSION"
            elif previous["interrupted"]:
                reason = "SESSION_INTERRUPTED"
            elif previous["unconfirmed"]:
                reason = "DELIVERY_UNCONFIRMED"
            elif int(self._clock()) - previous["last_seen_ms"] > self._stale_after_ms:
                reason = "SESSION_STALE"
            elif previous["busy"]:
                reason = "SESSION_BUSY"
            elif not previous["direct_opt_in"]:
                reason = "DIRECT_NOT_OPTED_IN"
            else:
                reason = "DIRECT_READY"
            return {
                "session_id": session_id,
                "allowed": reason == "DIRECT_READY",
                "reason": reason,
                "epoch": previous["epoch"] if previous is not None else None,
            }
