"""Synthetic, but end-to-end, ChatGPT MCP identity -> project grant -> bus.

No real consumer ChatGPT conversation, subscription, or browser is touched.
"""
from pathlib import Path
import os
import sys
import tempfile
import unittest

from rdc.chatgpt_identity import ChatGPTToolIdentityBroker, ChatGPTIdentityDenied
from rdc.chat_project_actions import ProjectActionStore, ProjectChatActions, ProjectActionDenied
from rdc.chat_interconnect import ChatClient, ChatError
from rdc.chat_rooms import ChatRoom
from rdc.chat_project_messages import ProjectScopedChatMessenger, ProjectMessageDenied

ATLAS = Path(os.environ.get("RDC_ATLAS_BUS_TEST_ROOT","/nonexistent/atlas-bus"))
AVAILABLE = (ATLAS/"atlasbus"/"store.py").is_file()


class TrustedRegistry:
    def find_project(self, subject, conversation):
        project_lookup = {
            ("person-x","alpha"): "rdc-project-one",
            ("person-x","beta"): "rdc-project-one",
            ("person-x","gamma"): "rdc-project-one",
            ("person-x","other"): "rdc-project-two",
        }
        return project_lookup.get((subject,conversation))


class OneTimeAuthority:
    def __init__(self):
        self.checks=0
    def verify_activation(self, proof, project_id, capabilities, *, operation):
        self.checks+=1
        return (proof=="owner-approval-one"
                and project_id=="rdc-project-one"
                and set(capabilities)=={"create","wake","message"}
                and operation=="activate")


class ApprovedHostAdapter:
    def __init__(self):
        self.capabilities={"create_in_project","inspect_chat","wake_existing"}
        self.opened=[]
    def create_in_project(self, provider, project_id, request_id):
        handle={"provider":provider,"project_id":project_id,
                "opaque_id":"new-project-chat-"+str(len(self.opened)+1),
                "mode":"browser","observed":True}
        self.opened.append(handle)
        return handle
    def inspect_chat(self, handle):
        return {"provider":handle["provider"],"project_id":handle["project_id"],
                "opaque_id":handle["opaque_id"],"observed":True,"state":"suspended"}
    def wake_existing(self,handle,request_id):
        return {"observed":True,"signalled":True,
                "opaque_id":handle["opaque_id"],"host_action_id":"verified-wake"}


@unittest.skipUnless(AVAILABLE,"Atlas Bus source unavailable")
class ChatGPTMCPProjectFlowTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0,str(ATLAS))
        from atlasbus.store import BusStore
        self.temp = tempfile.TemporaryDirectory(prefix="rdc-chatgpt-meta-flow-")
        self.store=ProjectActionStore(Path(self.temp.name)/"grants.sqlite3")
        self.bus=BusStore(Path(self.temp.name)/"bus.sqlite3",
                          synthetic_mode=True)
        self.verifier=ChatGPTToolIdentityBroker(
            TrustedRegistry(), secret=b"synthetic-only-test-secret-for-chat-identity-123")
        self.owner=OneTimeAuthority()
        self.host=ApprovedHostAdapter()
        self.actions=ProjectChatActions(self.store,session_verifier=self.verifier,host=self.host)
        self.refs={}
        for s in ("alpha","beta","gamma","other"):
            self.refs[s]=self.verifier.bind_tool_call(
                {"_meta":{"openai/subject":"person-x","openai/session":s}},
                verified_transport=True)
            identity=self.verifier.verify_actor(self.refs[s])
            # Atlas Bus v1 currently defines four platform project domains;
            # ChatGPT project membership is an additional trusted RDC scope.
            self.bus.register_synthetic_session("rdc", identity["session_id"])
    def tearDown(self):
        self.bus.close()
        self.store.close()
        self.temp.cleanup()
        sys.path.remove(str(ATLAS))

    def test_three_mcp_sessions_share_single_owner_grant_and_bus_messages(self):
        with self.assertRaises(ProjectActionDenied):
            self.actions.create(self.refs["alpha"],"chatgpt",request_id="create-before-approval")
        self.store.activate("rdc-project-one",{"create","wake","message"},
                            authority=self.owner,proof="owner-approval-one")
        self.assertEqual(self.owner.checks,1)
        result=[]
        for session in ("alpha","beta","gamma"):
            result.append(self.actions.create(
                self.refs[session],"chatgpt",request_id="create-"+session))
        self.assertTrue(all(x["state"]=="CREATED_VERIFIED" for x in result))
        self.assertEqual(self.owner.checks,1)
        peer = ProjectScopedChatMessenger(self.bus, session_verifier=self.verifier,
                                         grant_store=self.store)
        sent=peer.send(self.refs["alpha"],self.refs["beta"],"Please inspect the source",key="task-1")
        incoming=peer.claim(self.refs["beta"],holder="beta-reader")
        self.assertEqual(incoming["message_id"],sent["receipt"]["message_id"])
        self.assertEqual(incoming["envelope"]["source_project"],"rdc")
        self.assertEqual(incoming["envelope"]["destination_project"],"rdc")
        reply=peer.reply(self.refs["beta"],self.refs["alpha"],"Reviewed",
                         key="reply-1",parent_id=incoming["message_id"])
        readback=peer.claim(self.refs["alpha"],holder="alpha-reader")
        self.assertEqual(readback["message_id"],reply["receipt"]["message_id"])
        self.assertEqual(readback["envelope"]["causation_id"],incoming["message_id"])
        fanout=peer.broadcast(self.refs["alpha"],
                             (self.refs["alpha"],self.refs["beta"],self.refs["gamma"]),
                             "Shared progress",key="progress-1",room_key="toc-session-room-1")
        targets={self.verifier.verify_target(ref)["session_id"]
                 for ref in (self.refs["beta"],self.refs["gamma"])}
        self.assertEqual(set(fanout["receipts"]),targets)

    def test_unrelated_project_has_no_create_authority_from_another_project_grant(self):
        self.store.activate("rdc-project-one",{"create","wake","message"},
                            authority=self.owner,proof="owner-approval-one")
        with self.assertRaises(ProjectActionDenied):
            self.actions.create(self.refs["other"],"chatgpt",request_id="outside")
        self.assertEqual(len(self.host.opened),0)
        peer=ProjectScopedChatMessenger(self.bus,session_verifier=self.verifier,
                                        grant_store=self.store)
        with self.assertRaises(ProjectMessageDenied):
            peer.send(self.refs["other"],self.refs["alpha"],
                      "Unauthorized cross-project message",key="forbidden")
        with self.assertRaises(ProjectMessageDenied):
            peer.send(self.refs["alpha"],self.refs["other"],
                      "Unauthorized cross-project message",key="forbidden2")
        self.assertEqual(self.bus.connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0],0)


if __name__=="__main__":
    unittest.main()
