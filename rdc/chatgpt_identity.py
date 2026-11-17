"""Bind trusted ChatGPT tool-call metadata to opaque RDC/DC actor identities.

Official ChatGPT plugin tool calls may include _meta['openai/session'] and
_meta['openai/subject']. Neither field is a project ID. An independently trusted
host registry MUST resolve the exact project from those two values. This
broker cannot enroll unverified ChatGPT conversations by URL, tab, model text,
or self-reported CLI project parameters.

The caller MUST check transport/OAuth authentication *before* passing
verified_transport=True. Never expose the server HMAC key or the raw host
metadata through ordinary assistant-visible tool responses.
"""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import hmac
import secrets
from threading import RLock

from .chat_interconnect import _SESSION_RE


class ChatGPTIdentityDenied(ValueError):
    """No verified host tool-call session/project binding is available."""


def _host_token(value, *, name):
    if not isinstance(value, str) or not 1 <= len(value) <= 256:
        raise ChatGPTIdentityDenied(f"Missing or oversized host {name}.")
    if any(ord(c) < 33 or ord(c) > 126 for c in value):
        raise ChatGPTIdentityDenied(f"Invalid host {name} characters.")
    return value


class ChatGPTToolIdentityBroker:
    """Adapter-injected trusted session references for direct MCP tool calls.

    The project_registry.find_project(subject,session) method MUST use a
    trusted ChatGPT project-membership service or separately enrolled map.
    Host metadata alone DOES NOT attest project membership. This in-memory
    handle broker remains synthetic until installed in an authenticated host.
    """

    def __init__(self, project_registry, *, secret: bytes, max_handles: int = 4096):
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise ChatGPTIdentityDenied("A strong host-private HMAC key is required.")
        if not callable(getattr(project_registry, "find_project", None)):
            raise ChatGPTIdentityDenied("A trusted project membership resolver is required.")
        if type(max_handles) is not int or not 1 <= max_handles <= 16384:
            raise ChatGPTIdentityDenied("Host handle capacity must be bounded.")
        self._registry = project_registry
        self._secret = secret
        self._max_handles = max_handles
        self._handles = {}
        self._lock = RLock()

    def bind_tool_call(self, request_context: Mapping, *, verified_transport: bool):
        """Bind host-provided request metadata, never model tool arguments."""
        if verified_transport is not True:
            raise ChatGPTIdentityDenied("Unauthenticated host transport cannot enroll chats.")
        if not isinstance(request_context, Mapping):
            raise ChatGPTIdentityDenied("Missing trusted host tool-call context.")
        meta = request_context.get("_meta")
        if not isinstance(meta, Mapping):
            raise ChatGPTIdentityDenied("Missing host-provided metadata.")
        subject = _host_token(meta.get("openai/subject"), name="subject")
        session = _host_token(meta.get("openai/session"), name="session")
        project = self._registry.find_project(subject, session)
        if not isinstance(project, str) or _SESSION_RE.fullmatch(project) is None:
            raise ChatGPTIdentityDenied("Host has not verified this conversation's project.")
        # Domain-separated, project-scoped pseudonym binds the account,
        # conversation and project without raw ChatGPT identifiers.
        data = ("rdc-chatgpt-session-v1\0" + str(len(subject)) + ":" + subject +
                str(len(session)) + ":" + session + ":" + project).encode("utf-8")
        principal = "chatgpt-" + hmac.new(self._secret, data, hashlib.sha256).hexdigest()[:40]
        identity = {"project_id":project, "session_id":principal,
                    "authenticated":True,"provider":"chatgpt"}
        with self._lock:
            if len(self._handles) >= self._max_handles:
                raise ChatGPTIdentityDenied("Host tool-call handle capacity exceeded.")
            handle = secrets.token_urlsafe(24)
            self._handles[handle] = identity
        return handle

    def verify_actor(self, session_handle):
        if not isinstance(session_handle, str):
            return None
        with self._lock:
            actor = self._handles.get(session_handle)
            return dict(actor) if actor is not None else None

    def verify_target(self, session_handle):
        if not isinstance(session_handle, str):
            return None
        with self._lock:
            actor = self._handles.get(session_handle)
            if actor is None:
                return None
            return {"project_id":actor["project_id"],
                    "session_id":actor["session_id"],
                    "provider":actor["provider"],
                    "opaque_id":actor["session_id"],
                    "verified":True}
