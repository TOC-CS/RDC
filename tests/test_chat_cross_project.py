"""Atlas-approved cross-project routing contract for the RDC communications skill.

Synthetic approval and dispatcher only. Actual Atlas Bus v1 still denies
cross-project messages. No approval of a real project is implied.
"""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from rdc.chat_cross_project import CrossProjectChatRouter, RouteDenied


class FakeIdentity:
    def __init__(self):
        self.sessions = {
            "manager": {"project_id":"atlas","session_id":"atlas-manager","authenticated":True},
            "rdc": {"project_id":"rdc","session_id":"rdc-owner","authenticated":True},
            "bandmates": {"project_id":"bandmates","session_id":"bandmates-owner","authenticated":True},
            "presentation": {"project_id":"presentation","session_id":"presentation-owner","authenticated":True},
            "unverified": {"project_id":"atlas","session_id":"atlas-unknown","authenticated":False},
        }
    def verify_actor(self,ref):
        return self.sessions.get(ref)
    def verify_target(self,ref):
        row=self.sessions.get(ref)
        return {**row,"verified":row["authenticated"]} if row else None


class FakeIndependentApproval:
    def __init__(self):
        self.approved={}
        self.calls=[]
    def approve(self,source,target,kind,grant_id):
        self.approved[source,target,kind]={"approved":True,"grant_id":grant_id,
                                           "authorized_by":"atlas-independent-review",
                                           "operation":kind,"source_project":source,
                                           "destination_project":target}
    def resolve(self,source,target,operation):
        self.calls.append((source,target,operation))
        return self.approved.get((source,target,operation))


class FakeDispatcher:
    def __init__(self):
        self.accepted={}
        self.called=[]
    def send_once(self,grant,envelope):
        identity=(envelope["source_session_id"],envelope["idempotency_key"])
        self.called.append((grant["grant_id"],envelope["destination_project"]))
        if identity in self.accepted:
            old=self.accepted[identity]
            if old["envelope"]!=envelope:
                raise ValueError("IDEMPOTENCY_CONFLICT")
            return {"receipt":old["receipt"],"duplicate":True}
        receipt={"message_id":envelope["message_id"],"state":"QUEUED"}
        self.accepted[identity]={"envelope":envelope,"receipt":receipt}
        return {"receipt":receipt,"duplicate":False}


class CrossProjectRoutingTests(unittest.TestCase):
    def setUp(self):
        self.identity=FakeIdentity()
        self.approvals=FakeIndependentApproval()
        self.dispatcher=FakeDispatcher()
        self.router=CrossProjectChatRouter(self.identity,self.approvals,self.dispatcher)

    def test_default_denies_atlas_manager_to_other_projects(self):
        for target in ("rdc","bandmates","presentation"):
            with self.subTest(target=target),self.assertRaises(RouteDenied):
                self.router.send("manager",target,"Status please",key="task-"+target)
        self.assertEqual(self.dispatcher.called,[])

    def test_approved_atlas_management_routes_to_exact_projects_only(self):
        for target in ("rdc","bandmates","presentation"):
            self.approvals.approve("atlas",target,"message",grant_id="reviewed-"+target)
            sent=self.router.send("manager",target,"Status please",key="status-"+target)
            self.assertFalse(sent["duplicate"])
            self.assertEqual(sent["receipt"]["state"],"QUEUED")
            self.assertEqual(self.dispatcher.accepted[
                ("atlas-manager","status-"+target)]["envelope"]["destination_project"],
                target)
        self.assertEqual(len(self.dispatcher.called),3)
        self.assertEqual({x[0] for x in self.dispatcher.called},
                         {"reviewed-rdc","reviewed-bandmates","reviewed-presentation"})

    def test_reverse_direction_requires_separate_independent_approval(self):
        self.approvals.approve("atlas","bandmates","message","manager-to-studio")
        self.router.send("manager","bandmates","Status",key="request")
        with self.assertRaises(RouteDenied):
            self.router.send("bandmates","manager","Studio reply",key="reply")
        self.approvals.approve("bandmates","atlas","message","studio-to-manager")
        self.assertEqual(self.router.send("bandmates","manager","Studio reply",
                                          key="reply")["receipt"]["state"],"QUEUED")

    def test_wrong_project_grant_and_spoofed_identity_cannot_dispatch(self):
        self.approvals.approve("atlas","rdc","message","approved-rdc")
        with self.assertRaises(RouteDenied):
            self.router.send("unverified","rdc","Spoof",key="spoof")
        with self.assertRaises(RouteDenied):
            self.router.send("manager","presentation","Wrong grant",key="wrong")
        with self.assertRaises(RouteDenied):
            self.router.send("some-id","rdc","Wrong actor",key="not-enrolled")
        self.assertEqual(self.dispatcher.called,[])

    def test_same_key_duplicate_and_altered_payload_conflict(self):
        self.approvals.approve("atlas","rdc","message","grant-1")
        first=self.router.send("manager","rdc","Original content",key="stable")
        second=self.router.send("manager","rdc","Original content",key="stable")
        self.assertEqual(first["receipt"],second["receipt"])
        self.assertTrue(second["duplicate"])
        with self.assertRaisesRegex(ValueError,"IDEMPOTENCY_CONFLICT"):
            self.router.send("manager","rdc","Changed content",key="stable")
        self.assertEqual(len(self.dispatcher.accepted),1)

    def test_cross_project_grant_does_not_allow_code_execution_or_sensitive_commands(self):
        self.approvals.approve("atlas","rdc","message","status-only")
        with self.assertRaises(RouteDenied):
            self.router.send("manager","rdc","run terminal shell command",
                             key="bad",kind="execute")
        self.assertEqual(self.dispatcher.called,[])

    def test_bypass_raw_atlas_store_remains_blocked_without_owner_route(self):
        # A route grant is not registered into the original Atlas BusStore.
        # The normal core remains CROSS_PROJECT_DENIED unless an independent
        # approved dispatcher is installed by the Atlas project owner.
        self.assertEqual(self.router.live_configured,False)
        with self.assertRaises(RouteDenied):
            CrossProjectChatRouter(self.identity,self.approvals,None).send(
                "manager","rdc","Try bypass",key="no-dispatch")

ATLAS_SOURCE = Path(os.environ.get("RDC_ATLAS_BUS_TEST_ROOT","/nonexistent/atlas-bus"))

@unittest.skipUnless((ATLAS_SOURCE/"atlasbus/store.py").is_file(),
                     "Independent Atlas Bus source unavailable")
class OriginalAtlasBusStillDeniesCrossProjectTests(unittest.TestCase):
    def test_even_a_synthetic_approval_does_not_reconfigure_real_bus_owner_gate(self):
        sys.path.insert(0,str(ATLAS_SOURCE))
        try:
            from atlasbus.store import BusStore
            from atlasbus.contract import BusError
            with tempfile.TemporaryDirectory(prefix="rdc-independent-atlas-cross-") as root:
                bus=BusStore(Path(root)/"atlas.sqlite3",synthetic_mode=True)
                try:
                    bus.register_synthetic_session("atlas","atlas-manager")
                    bus.register_synthetic_session("rdc","rdc-owner")
                    identities=FakeIdentity()
                    approval=FakeIndependentApproval()
                    dispatcher=FakeDispatcher()
                    approval.approve("atlas","rdc","message","synthetic-route-only")
                    router=CrossProjectChatRouter(identities,approval,dispatcher)
                    router.send("manager","rdc","Status request",key="test-cross")
                    proposed=dispatcher.accepted[("atlas-manager","test-cross")]["envelope"]
                    with self.assertRaisesRegex(BusError,"CROSS_PROJECT_DENIED"):
                        bus.enqueue("atlas-manager",proposed)
                    self.assertEqual(bus.connection.execute(
                        "SELECT COUNT(*) FROM messages").fetchone()[0],0)
                finally:
                    bus.close()
        finally:
            sys.path.remove(str(ATLAS_SOURCE))
