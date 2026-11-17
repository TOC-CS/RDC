"""ChatGPT MCP tool-context session identities and project-scoped enrollment.

The host supplies _meta['openai/session'] and _meta['openai/subject'] for
trusted plugin tool calls. Project membership MUST come from a separately
trusted host project registry, never a model-filled tool argument.
"""
import unittest
from rdc.chatgpt_identity import ChatGPTToolIdentityBroker, ChatGPTIdentityDenied


class FakeTrustedProjectRegistry:
    def __init__(self):
        self.registered = {
            ("user-alpha", "conversation-A"): "toc-rdc-project",
            ("user-alpha", "conversation-B"): "toc-rdc-project",
            ("user-alpha", "conversation-C"): "toc-rdc-project",
            ("user-alpha", "outside-conversation"): "other-project",
            ("user-beta", "conversation-A"): "other-project",
        }
        self.calls = []
    def find_project(self, subject, session):
        self.calls.append((subject, session))
        return self.registered.get((subject, session))


class ChatGPTToolIdentityTests(unittest.TestCase):
    def setUp(self):
        self.registry = FakeTrustedProjectRegistry()
        self.broker = ChatGPTToolIdentityBroker(self.registry, secret=b"synthetic-local-test-hmac-key-32-bytes-okay")

    def bind(self, subject="user-alpha", session="conversation-A", **kwargs):
        return self.broker.bind_tool_call(
            {"_meta":{"openai/subject":subject,"openai/session":session}},
            verified_transport=True, **kwargs)

    def test_same_chat_rebinds_stably_across_tool_calls_without_exposing_raw_ids(self):
        opaque1 = self.bind()
        first = self.broker.verify_actor(opaque1)
        opaque2 = self.bind()
        second = self.broker.verify_actor(opaque2)
        self.assertEqual(first["session_id"], second["session_id"])
        self.assertEqual(first["project_id"], "toc-rdc-project")
        self.assertTrue(first["authenticated"])
        self.assertTrue(first["session_id"].startswith("chatgpt-"))
        self.assertNotIn("conversation-A", str(first))
        self.assertNotIn("user-alpha", str(first))
        self.assertNotEqual(opaque1, opaque2, "Each tool invocation has an independent opaque handle")

    def test_two_or_three_chats_in_one_project_get_distinct_actor_ids(self):
        identities = [self.broker.verify_actor(self.bind(session=s)) for s in
                      ("conversation-A","conversation-B","conversation-C")]
        self.assertEqual(len({i["session_id"] for i in identities}), 3)
        self.assertEqual({i["project_id"] for i in identities}, {"toc-rdc-project"})
        for result in identities:
            self.assertTrue(result["authenticated"])

    def test_different_account_with_same_conversation_text_is_isolated(self):
        a = self.broker.verify_actor(self.bind(subject="user-alpha", session="conversation-A"))
        b = self.broker.verify_actor(self.bind(subject="user-beta", session="conversation-A"))
        self.assertNotEqual(a["session_id"], b["session_id"])
        self.assertNotEqual(a["project_id"], b["project_id"])

    def test_host_project_registry_is_authority_not_model_project_argument(self):
        ref = self.broker.bind_tool_call(
            {"_meta":{"openai/subject":"user-alpha","openai/session":"outside-conversation"},
             "arguments":{"project_id":"toc-rdc-project"}},
            verified_transport=True)
        actual = self.broker.verify_actor(ref)
        self.assertEqual(actual["project_id"], "other-project")
        self.assertNotEqual(actual["project_id"], "toc-rdc-project")

    def test_missing_project_registry_enrollment_refused(self):
        with self.assertRaises(ChatGPTIdentityDenied):
            self.bind(session="arbitrary-guess-unregistered")
        self.assertEqual(self.broker.verify_actor("copied-opaque-handle"), None)

    def test_unverified_host_metadata_and_missing_ids_denied(self):
        with self.assertRaises(ChatGPTIdentityDenied):
            self.broker.bind_tool_call(
                {"_meta":{"openai/subject":"user-alpha","openai/session":"conversation-A"}},
                verified_transport=False)
        for wrong in ({}, {"_meta":{}}, {"_meta":{"openai/session":"conversation-A"}},
                      {"_meta":{"openai/subject":"user-alpha"}},
                      {"_meta":{"openai/subject":"user-alpha","openai/session":""}}):
            with self.subTest(wrong=wrong), self.assertRaises(ChatGPTIdentityDenied):
                self.broker.bind_tool_call(wrong, verified_transport=True)

    def test_actor_ref_has_no_cross_session_impersonation_via_tool_arguments(self):
        a = self.bind()
        actor = self.broker.verify_actor(a)
        self.assertEqual(actor["project_id"], "toc-rdc-project")
        malicious_tool_args={"actor":a, "source_session":"chatgpt-other", "project_id":"other-project"}
        other = self.broker.bind_tool_call(
            {"_meta":{"openai/subject":"user-alpha","openai/session":"outside-conversation"},
             "arguments":malicious_tool_args},
            verified_transport=True)
        verified = self.broker.verify_actor(other)
        self.assertNotEqual(verified["session_id"], actor["session_id"])
        self.assertEqual(verified["project_id"], "other-project")

    def test_target_registry_only_returns_host_enrolled_sessions(self):
        a = self.bind()
        b = self.bind(session="conversation-B")
        original = self.broker.verify_actor(b)
        lookup = self.broker.verify_target(b)
        self.assertEqual(lookup["session_id"], original["session_id"])
        self.assertEqual(lookup["project_id"], "toc-rdc-project")
        self.assertTrue(lookup["verified"])
        self.assertEqual(self.broker.verify_target("unknown-target"), None)


if __name__ == "__main__":
    unittest.main()
