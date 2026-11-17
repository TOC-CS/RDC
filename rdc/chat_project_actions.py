"""One-time project-scoped chat creation and wake contracts for RDC/DC.

The owner activates capabilities once for a trusted project; any subsequent
host-authenticated session in that project may use them without repeated
owner prompts. Actual project/peer authentication MUST be supplied by a
trusted ChatGPT/App/DC host adapter. This module does not access credentials,
browsers or consumer ChatGPT sessions.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from threading import RLock

from .chat_interconnect import _SESSION_RE


class ProjectActionDenied(ValueError):
    """No project grant, no verified session, invalid intent, or key conflict."""


_CAPABILITIES = frozenset({"create", "wake", "message"})
_PROVIDER_RE = re.compile(r"^[a-z][a-z0-9._-]{0,63}$")
_KEY_RE = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")


def _identity_string(value):
    return isinstance(value, str) and _SESSION_RE.fullmatch(value) is not None


class ProjectActionStore:
    """Durable project grant and original-operation journal in one private DB.

    The database is *not* a second message bus. It stores only the owner's
    activation policy and immutable operation identity/receipts; peer chat
    messages continue to use Atlas Bus v1.
    """

    def __init__(self, path: Path):
        raw = Path(path).expanduser()
        if raw.is_symlink():
            raise ProjectActionDenied("Project action database cannot be a symlink.")
        if not raw.parent.is_dir():
            raise ProjectActionDenied("Existing private state directory required.")
        self.path = raw.resolve()
        self._lock = RLock()
        self.db = sqlite3.connect(str(self.path), isolation_level=None,
                                  timeout=3, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.path.chmod(0o600)
        try:
            self.db.execute("PRAGMA busy_timeout=3000")
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.executescript(
                "CREATE TABLE IF NOT EXISTS project_activation("
                "project_id TEXT PRIMARY KEY, capabilities_json TEXT NOT NULL, "
                "active INTEGER NOT NULL, revision INTEGER NOT NULL);"
                "CREATE TABLE IF NOT EXISTS action_receipts("
                "project_id TEXT NOT NULL, actor_session TEXT NOT NULL, "
                "request_id TEXT NOT NULL, fingerprint TEXT NOT NULL, "
                "receipt_json TEXT NOT NULL, "
                "PRIMARY KEY(project_id,actor_session,request_id));"
                "CREATE TABLE IF NOT EXISTS used_owner_proofs("
                "proof_digest TEXT PRIMARY KEY,project_id TEXT NOT NULL,"
                "operation TEXT NOT NULL);"
            )
        except BaseException:
            self.db.close()
            raise

    @contextmanager
    def _write(self):
        with self._lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise

    @staticmethod
    def _validate(project_id, capabilities):
        if not _identity_string(project_id):
            raise ProjectActionDenied("Exact bounded project identity required.")
        if (not isinstance(capabilities, (set, frozenset, list, tuple))
                or not capabilities or not set(capabilities) <= _CAPABILITIES):
            raise ProjectActionDenied("Only bounded create, wake and message grants are supported.")
        return tuple(sorted(set(capabilities)))

    @staticmethod
    def _proof_digest(proof):
        if not isinstance(proof, str) or not proof or len(proof) > 512:
            raise ProjectActionDenied("Opaque owner-grant evidence is required.")
        return hashlib.sha256(("rdc-project-owner-proof-v1\\0" + proof).encode("utf-8")).hexdigest()

    def activate(self, project_id, capabilities, *, authority, proof):
        scopes = self._validate(project_id, capabilities)
        proof_digest = self._proof_digest(proof)
        # The verifier lives in an owner/host broker, never in message text.
        if not authority.verify_activation(proof, project_id, scopes, operation="activate"):
            raise ProjectActionDenied("Owner activation evidence was not verified.")
        with self._write():
            used = self.db.execute(
                "SELECT project_id,operation FROM used_owner_proofs WHERE proof_digest=?",
                (proof_digest,)).fetchone()
            prior = self.db.execute(
                "SELECT revision,active,capabilities_json FROM project_activation WHERE project_id=?",
                (project_id,)).fetchone()
            if used is not None:
                if (prior is not None and prior["active"] == 1
                        and used["project_id"] == project_id
                        and used["operation"] == "activate"
                        and tuple(json.loads(prior["capabilities_json"])) == scopes):
                    return {"project_id":project_id,"active":True,
                            "capabilities":list(scopes),"revision":int(prior["revision"])}
                raise ProjectActionDenied("One-time owner approval evidence has already been used.")
            revision = int(prior["revision"]) + 1 if prior else 1
            self.db.execute("INSERT INTO used_owner_proofs(proof_digest,project_id,operation)"
                            " VALUES(?,?,?)",(proof_digest,project_id,"activate"))
            self.db.execute(
                "INSERT INTO project_activation(project_id,capabilities_json,active,revision)"
                " VALUES(?,?,1,?) ON CONFLICT(project_id) DO UPDATE SET "
                "capabilities_json=excluded.capabilities_json,active=1,revision=excluded.revision",
                (project_id,json.dumps(scopes),revision))
        return {"project_id":project_id, "active":True,
                "capabilities":list(scopes),"revision":revision}

    def revoke(self, project_id, *, authority, proof):
        proof_digest = self._proof_digest(proof)
        if not _identity_string(project_id):
            raise ProjectActionDenied("Valid project identity required.")
        with self._lock:
            row = self.db.execute(
                "SELECT capabilities_json FROM project_activation WHERE project_id=?",
                (project_id,)).fetchone()
        if row is None:
            raise ProjectActionDenied("Project has no activation to revoke.")
        scopes = tuple(json.loads(row["capabilities_json"]))
        if not authority.verify_activation(proof, project_id, scopes, operation="revoke"):
            raise ProjectActionDenied("Owner revocation evidence was not verified.")
        with self._write():
            if self.db.execute("SELECT 1 FROM used_owner_proofs WHERE proof_digest=?",
                               (proof_digest,)).fetchone() is not None:
                raise ProjectActionDenied("One-time owner approval evidence has already been used.")
            self.db.execute("INSERT INTO used_owner_proofs(proof_digest,project_id,operation)"
                            " VALUES(?,?,?)",(proof_digest,project_id,"revoke"))
            self.db.execute(
                "UPDATE project_activation SET active=0,revision=revision+1 WHERE project_id=?",
                (project_id,))
        return {"project_id":project_id,"active":False}

    def allowed(self, project_id, capability):
        with self._lock:
            row = self.db.execute(
                "SELECT capabilities_json,active FROM project_activation WHERE project_id=?",
                (project_id,)).fetchone()
        return bool(row and row["active"] == 1
                    and capability in json.loads(row["capabilities_json"]))

    @staticmethod
    def _fingerprint(action, provider, target):
        value = json.dumps({"action":action,"provider":provider,"target":target},
                           sort_keys=True,separators=(",",":"))
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def receipt(self, project_id, actor, request_id, *, action, provider, target):
        digest = self._fingerprint(action,provider,target)
        with self._lock:
            prior = self.db.execute(
                "SELECT fingerprint,receipt_json FROM action_receipts "
                "WHERE project_id=? AND actor_session=? AND request_id=?",
                (project_id,actor,request_id)).fetchone()
        if prior is None:
            return None
        if prior["fingerprint"] != digest:
            raise ProjectActionDenied("IDEMPOTENCY_CONFLICT")
        return json.loads(prior["receipt_json"])

    def prepare(self, project_id, actor, request_id, *, action, provider, target):
        # Atomically prepare an UNKNOWN receipt before any external side effect.
        digest = self._fingerprint(action,provider,target)
        with self._write():
            prior = self.db.execute(
                "SELECT fingerprint,receipt_json FROM action_receipts "
                "WHERE project_id=? AND actor_session=? AND request_id=?",
                (project_id,actor,request_id)).fetchone()
            if prior is not None:
                if prior["fingerprint"] != digest:
                    raise ProjectActionDenied("IDEMPOTENCY_CONFLICT")
                return json.loads(prior["receipt_json"]),False
            pending = {"project_id":project_id,"actor_session":actor,
                       "request_id":request_id,"action":action,"provider":provider,
                       "state":"OUTCOME_UNKNOWN"}
            self.db.execute(
                "INSERT INTO action_receipts(project_id,actor_session,request_id,"
                "fingerprint,receipt_json) VALUES(?,?,?,?,?)",
                (project_id,actor,request_id,digest,json.dumps(pending,sort_keys=True)))
        return pending,True

    def complete(self, project_id, actor, request_id, *, action, provider, target, receipt):
        digest = self._fingerprint(action,provider,target)
        with self._write():
            prior = self.db.execute(
                "SELECT fingerprint,receipt_json FROM action_receipts "
                "WHERE project_id=? AND actor_session=? AND request_id=?",
                (project_id,actor,request_id)).fetchone()
            if prior is None or prior["fingerprint"] != digest:
                raise ProjectActionDenied("No matching pending authorized action.")
            old = json.loads(prior["receipt_json"])
            if old["state"] != "OUTCOME_UNKNOWN":
                return old
            self.db.execute(
                "UPDATE action_receipts SET receipt_json=? "
                "WHERE project_id=? AND actor_session=? AND request_id=?",
                (json.dumps(receipt,sort_keys=True),project_id,actor,request_id))
        return receipt.copy()

    def close(self):
        with self._lock:
            self.db.close()


class ProjectChatActions:
    """Reusable RDC/DC lifecycle broker with project-wide activated actions.

    A trusted host must supply the session verifier and provider adapter.
    Project strings and peer identity copied from a prompt are never proof.
    """

    def __init__(self, store: ProjectActionStore, *, session_verifier, host):
        self.store=store
        self.verifier=session_verifier
        self.host=host

    def _actor(self, session_ref, action):
        identity = self.verifier.verify_actor(session_ref)
        if (not isinstance(identity,dict)
                or identity.get("authenticated") is not True
                or not _identity_string(identity.get("project_id"))
                or not _identity_string(identity.get("session_id"))):
            raise ProjectActionDenied("A host-authenticated project session is required.")
        if not self.store.allowed(identity["project_id"],action):
            raise ProjectActionDenied("Action has no active project-wide grant.")
        return identity["project_id"],identity["session_id"]

    @staticmethod
    def _provider(provider):
        if not isinstance(provider,str) or _PROVIDER_RE.fullmatch(provider) is None:
            raise ProjectActionDenied("A bounded provider identifier is required.")
        return provider

    @staticmethod
    def _key(request_id):
        if not isinstance(request_id,str) or _KEY_RE.fullmatch(request_id) is None:
            raise ProjectActionDenied("A stable bounded action ID is required.")

    def _host_capabilities(self,*required):
        available = getattr(self.host,"capabilities",set())
        if any(cap not in available for cap in required):
            raise ProjectActionDenied("Host lacks an approved capability for this project action.")

    def create(self, actor_ref, provider, *, request_id):
        project,actor=self._actor(actor_ref,"create")
        provider=self._provider(provider)
        self._key(request_id)
        prior=self.store.receipt(project,actor,request_id,action="create",provider=provider,target=project)
        if prior is not None: return prior
        self._host_capabilities("create_in_project","inspect_chat")
        receipt,created=self.store.prepare(project,actor,request_id,action="create",
                                           provider=provider,target=project)
        if not created: return receipt
        try:
            # The provider MUST create a conversation INSIDE this exact project.
            handle=self.host.create_in_project(provider,project,request_id)
            readback=self.host.inspect_chat(handle)
            if (not isinstance(handle,dict) or not isinstance(readback,dict)
                    or handle.get("provider")!=provider or handle.get("project_id")!=project
                    or handle.get("observed") is not True
                    or not _identity_string(handle.get("opaque_id"))
                    or readback.get("provider")!=provider
                    or readback.get("project_id")!=project
                    or readback.get("opaque_id")!=handle["opaque_id"]
                    or readback.get("observed") is not True):
                return receipt
            confirmed={**receipt,"state":"CREATED_VERIFIED",
                       "session_id":handle["opaque_id"],"mode":handle.get("mode"),
                       "scope":"synthetic_host_contract_only"}
            return self.store.complete(project,actor,request_id,action="create",
                                       provider=provider,target=project,receipt=confirmed)
        except Exception:
            # May have created a chat before losing the host response.
            # Preserve original UNKNOWN receipt; no second create on retry.
            return receipt

    def wake(self, actor_ref, target_ref, *, request_id):
        project,actor=self._actor(actor_ref,"wake")
        self._key(request_id)
        target=self.verifier.verify_target(target_ref)
        if (not isinstance(target,dict) or target.get("verified") is not True
                or target.get("project_id")!=project
                or not _identity_string(target.get("session_id"))
                or not _identity_string(target.get("opaque_id"))):
            raise ProjectActionDenied("Wake target must be a verified chat inside the same project.")
        provider=self._provider(target.get("provider"))
        identifier=target["opaque_id"]
        prior=self.store.receipt(project,actor,request_id,
                                 action="wake",provider=provider,target=identifier)
        if prior is not None: return prior
        self._host_capabilities("wake_existing","inspect_chat")
        try:
            readback=self.host.inspect_chat(target)
        except Exception:
            return {"state":"DEFERRED","reason":"HOST_STATE_UNAVAILABLE",
                    "project_id":project,"target_session":identifier}
        if (not isinstance(readback,dict)
                or readback.get("provider")!=provider
                or readback.get("project_id")!=project
                or readback.get("opaque_id")!=identifier
                or readback.get("observed") is not True):
            return {"state":"DEFERRED","reason":"TARGET_UNVERIFIED",
                    "project_id":project,"target_session":identifier}
        if readback.get("state") not in {"suspended","waiting_for_message"}:
            return {"state":"DEFERRED","reason":"TARGET_NOT_SAFE_TO_WAKE",
                    "project_id":project,"target_session":identifier}
        receipt,created=self.store.prepare(project,actor,request_id,
                                           action="wake",provider=provider,target=identifier)
        if not created: return receipt
        try:
            result=self.host.wake_existing(target,request_id)
            if (not isinstance(result,dict)
                    or result.get("observed") is not True
                    or result.get("signalled") is not True
                    or result.get("opaque_id")!=identifier
                    or not isinstance(result.get("host_action_id"),str)
                    or not result["host_action_id"]):
                return receipt
            # Host confirmed the signal, NOT that an idle model was resumed.
            confirmed={**receipt,"state":"WAKE_SIGNAL_OBSERVED",
                       "target_session":identifier,"host_action_id":result["host_action_id"][:200],
                       "model_resumed":False,"scope":"synthetic_host_contract_only"}
            return self.store.complete(project,actor,request_id,
                                       action="wake",provider=provider,target=identifier,
                                       receipt=confirmed)
        except Exception:
            return receipt
