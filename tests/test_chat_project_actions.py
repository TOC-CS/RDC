"""One-time project activation for authenticated chat create/wake adapter actions.

These are synthetic host/project session tests. They do not create or wake
consumer ChatGPT conversations, bypass provider permissions, or automate UI.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import tempfile
from pathlib import Path
import unittest

from rdc.chat_project_actions import (
    ProjectActionStore, ProjectChatActions, ProjectActionDenied,
)


class FakeOwnerAuthority:
    def __init__(self):
        self.grants = {}
        self.checks = []
    def verify_activation(self, proof, project_id, capabilities, *, operation):
        self.checks.append((proof, project_id, tuple(sorted(capabilities)), operation))
        return self.grants.get(proof) == (project_id, tuple(sorted(capabilities)), operation)
    def approve(self, proof, project_id, capabilities, operation="activate"):
        self.grants[proof] = (project_id, tuple(sorted(capabilities)), operation)


class FakeSessionVerifier:
    """Only this injected host verifier can resolve a synthetic session handle."""
    def __init__(self):
        self.identities = {
            "opaque-A": {"project_id":"toc-project","session_id":"chatgpt-A","authenticated":True},
            "opaque-B": {"project_id":"toc-project","session_id":"chatgpt-B","authenticated":True},
            "opaque-C": {"project_id":"toc-project","session_id":"chatgpt-C","authenticated":True},
            "opaque-foreign": {"project_id":"other-project","session_id":"chatgpt-X","authenticated":True},
            "opaque-unverified": {"project_id":"toc-project","session_id":"chatgpt-Z","authenticated":False},
        }
        self.targets = {
            "target-B": {"project_id":"toc-project","session_id":"chatgpt-B",
                "provider":"chatgpt","opaque_id":"chatgpt-B","verified":True},
            "target-foreign": {"project_id":"other-project","session_id":"chatgpt-X",
                "provider":"chatgpt","opaque_id":"chatgpt-X","verified":True},
        }
    def verify_actor(self, session_handle):
        return self.identities.get(session_handle)
    def verify_target(self, target_ref):
        return self.targets.get(target_ref)


class FakeChatHost:
    def __init__(self):
        self.capabilities = {"create_in_project","wake_existing","inspect_chat"}
        self.created = []
        self.wakes = []
        self.timeout_create = False
        self.timeout_wake = False
        self.force_mismatch = False
        self.state = "suspended"
    def create_in_project(self, provider, project_id, request_id):
        self.created.append((provider,project_id,request_id))
        handle = {
            "provider": provider, "project_id": project_id, "opaque_id": "created-"+str(len(self.created)),
            "observed": True, "mode": "browser"}
        if self.force_mismatch: handle["project_id"]="other-project"
        if self.timeout_create: raise TimeoutError("The host might have created the chat.")
        return handle
    def inspect_chat(self, handle):
        return {"provider":handle["provider"],
                "project_id":handle["project_id"],
                "opaque_id":handle["opaque_id"],
                "observed":True, "state":self.state}
    def wake_existing(self, handle, request_id):
        self.wakes.append((handle["opaque_id"],request_id))
        if self.timeout_wake: raise TimeoutError("Unknown host signal result.")
        return {"observed":True,"signalled":True,
                "opaque_id":handle["opaque_id"],"host_action_id":"wake-action-1"}


class ProjectActivationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="rdc-chat-project-actions-")
        self.path=Path(self.temp.name)/"project-actions.sqlite3"
        self.store=ProjectActionStore(self.path)
        self.authority=FakeOwnerAuthority()
        self.verifier=FakeSessionVerifier()
        self.host=FakeChatHost()
        self.broker=ProjectChatActions(self.store, session_verifier=self.verifier, host=self.host)
        self.authority.approve("activate-one-time","toc-project",{"create","wake"})
    def tearDown(self):
        self.store.close()
        self.temp.cleanup()
    def activate(self):
        return self.store.activate("toc-project", {"create","wake"},
                                   authority=self.authority, proof="activate-one-time")

    def test_one_time_activation_allows_all_verified_sessions_in_project_without_prompt(self):
        with self.assertRaises(ProjectActionDenied):
            self.broker.create("opaque-A", "chatgpt", request_id="create-A")
        self.assertEqual(self.host.created, [])
        activated=self.activate()
        self.assertTrue(activated["active"])
        self.assertEqual(len(self.authority.checks),1)
        one=self.broker.create("opaque-A","chatgpt",request_id="create-A")
        two=self.broker.create("opaque-B","chatgpt",request_id="create-B")
        three=self.broker.create("opaque-C","chatgpt",request_id="create-C")
        self.assertEqual([x["state"] for x in (one,two,three)],["CREATED_VERIFIED"]*3)
        self.assertEqual(len(self.host.created),3)
        self.assertEqual(len(self.authority.checks),1, "No fresh owner prompt for another project chat")

    def test_activation_survives_restart_and_does_not_leak_to_another_project(self):
        self.activate()
        self.store.close()
        self.store=ProjectActionStore(self.path)
        self.broker=ProjectChatActions(self.store, session_verifier=self.verifier, host=self.host)
        result=self.broker.create("opaque-B","chatgpt",request_id="after-restart")
        self.assertEqual(result["state"],"CREATED_VERIFIED")
        self.assertEqual(len(self.authority.checks),1)
        with self.assertRaises(ProjectActionDenied):
            self.broker.create("opaque-foreign","chatgpt",request_id="outside-project")

    def test_unknown_or_unverified_actor_or_missing_capability_denied_without_host_call(self):
        self.activate()
        for identity in ("untrusted-input","opaque-unverified"):
            with self.subTest(identity=identity),self.assertRaises(ProjectActionDenied):
                self.broker.create(identity,"chatgpt",request_id="untrusted-"+identity)
        self.host.capabilities.remove("create_in_project")
        with self.assertRaises(ProjectActionDenied):
            self.broker.create("opaque-A","chatgpt",request_id="unsupported")
        self.assertEqual(self.host.created,[])

    def test_create_idempotent_per_authenticated_source_and_persists_after_restart(self):
        self.activate()
        a=self.broker.create("opaque-A","chatgpt",request_id="stable-001")
        self.assertEqual(a["state"],"CREATED_VERIFIED")
        self.store.close()
        self.store=ProjectActionStore(self.path)
        self.broker=ProjectChatActions(self.store, session_verifier=self.verifier, host=self.host)
        again=self.broker.create("opaque-A","chatgpt",request_id="stable-001")
        self.assertEqual(again,a)
        self.assertEqual(len(self.host.created),1)
        with self.assertRaises(ProjectActionDenied):
            self.broker.create("opaque-A","claude",request_id="stable-001")
        other=self.broker.create("opaque-B","chatgpt",request_id="stable-001")
        self.assertEqual(other["state"],"CREATED_VERIFIED")
        self.assertEqual(len(self.host.created),2)

    def test_uncertain_create_is_persistent_and_never_blindly_replayed(self):
        self.activate()
        self.host.timeout_create=True
        first=self.broker.create("opaque-A","chatgpt",request_id="unknown-create")
        self.assertEqual(first["state"],"OUTCOME_UNKNOWN")
        self.store.close()
        self.store=ProjectActionStore(self.path)
        self.broker=ProjectChatActions(self.store, session_verifier=self.verifier, host=self.host)
        self.host.timeout_create=False
        repeated=self.broker.create("opaque-A","chatgpt",request_id="unknown-create")
        self.assertEqual(repeated,first)
        self.assertEqual(len(self.host.created),1)

    def test_create_mismatched_project_readback_cannot_claim_verified(self):
        self.activate()
        self.host.force_mismatch=True
        result=self.broker.create("opaque-A","chatgpt",request_id="mismatch")
        self.assertEqual(result["state"],"OUTCOME_UNKNOWN")
        self.assertEqual(len(self.host.created),1)

    def test_wake_supported_suspended_chat_without_injecting_message(self):
        self.activate()
        result=self.broker.wake("opaque-A","target-B",request_id="wake-001")
        self.assertEqual(result["state"],"WAKE_SIGNAL_OBSERVED")
        self.assertEqual(result["model_resumed"],False)
        self.assertEqual(len(self.host.wakes),1)
        duplicate=self.broker.wake("opaque-A","target-B",request_id="wake-001")
        self.assertEqual(duplicate,result)
        self.assertEqual(len(self.host.wakes),1)
        self.assertEqual(len(self.authority.checks),1)

    def test_wake_denies_busy_interrupted_and_cross_project_without_mutation(self):
        self.activate()
        for state in ("generating","busy","interrupted","disconnected","unknown"):
            self.host.state=state
            result=self.broker.wake("opaque-A","target-B",request_id="wake-"+state)
            self.assertEqual(result["state"],"DEFERRED")
        with self.assertRaises(ProjectActionDenied):
            self.broker.wake("opaque-A","target-foreign",request_id="foreign")
        self.assertEqual(self.host.wakes,[])

    def test_wake_missing_host_capability_or_forged_grant_does_not_send(self):
        self.activate()
        self.host.capabilities.remove("wake_existing")
        with self.assertRaises(ProjectActionDenied):
            self.broker.wake("opaque-A","target-B",request_id="unsupported")
        with self.assertRaises(ProjectActionDenied):
            self.store.activate("toc-project", {"create","wake","admin"},
                                authority=self.authority, proof="activate-one-time")
        self.assertEqual(self.host.wakes,[])

    def test_uncertain_wake_is_never_replayed_across_process_lifetime(self):
        self.activate()
        self.host.timeout_wake=True
        result=self.broker.wake("opaque-A","target-B",request_id="lost-signal")
        self.assertEqual(result["state"],"OUTCOME_UNKNOWN")
        self.store.close()
        self.store=ProjectActionStore(self.path)
        self.broker=ProjectChatActions(self.store, session_verifier=self.verifier, host=self.host)
        self.host.timeout_wake=False
        repeated=self.broker.wake("opaque-A","target-B",request_id="lost-signal")
        self.assertEqual(repeated,result)
        self.assertEqual(len(self.host.wakes),1)

    def test_one_time_owner_revocation_applies_to_all_project_sessions(self):
        self.activate()
        self.authority.approve("revoke-once","toc-project",{"create","wake"},operation="revoke")
        self.store.revoke("toc-project",authority=self.authority,proof="revoke-once")
        with self.assertRaises(ProjectActionDenied):
            self.broker.create("opaque-B","chatgpt",request_id="after-revocation")
        with self.assertRaises(ProjectActionDenied):
            self.broker.wake("opaque-A","target-B",request_id="after-revocation")

    def test_revoked_project_cannot_reactivate_with_stale_one_time_owner_proof(self):
        self.activate()
        self.authority.approve("revoke-2", "toc-project", {"create","wake"}, operation="revoke")
        self.store.revoke("toc-project", authority=self.authority, proof="revoke-2")
        with self.assertRaises(ProjectActionDenied):
            self.activate()
        self.authority.approve("new-owner-activation", "toc-project", {"create","wake"})
        renewed = self.store.activate("toc-project", {"create","wake"},
                                      authority=self.authority, proof="new-owner-activation")
        self.assertTrue(renewed["active"])
        self.assertEqual(self.broker.create("opaque-C", "chatgpt", request_id="renewed")["state"],
                         "CREATED_VERIFIED")

    def test_simultaneous_identical_create_request_invokes_host_once(self):
        self.activate()
        with ThreadPoolExecutor(max_workers=12) as pool:
            results=list(pool.map(lambda _: self.broker.create("opaque-A","chatgpt",
                                  request_id="concurrent-create"),range(30)))
        self.assertEqual(len(self.host.created),1)
        self.assertTrue(all(x["state"] in ("CREATED_VERIFIED","OUTCOME_UNKNOWN") for x in results))


if __name__ == "__main__":
    unittest.main()
