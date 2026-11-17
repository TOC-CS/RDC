"""Contract tests for authorized provider chat surfaces (fake host, no model calls)."""
import unittest

from rdc.chat_surface import ChatSurfaceGateway, ChatSurfaceUnavailable, ChatSurfaceError


class FakeChatSurface:
    def __init__(self):
        self.capabilities = {"open_new", "attach_existing", "submit_once", "observe", "reconcile"}
        self.open_calls = []
        self.attach_calls = []
        self.submit_calls = []
        self.observe_calls = []
        self.known = {}
        self.timeout_on_submit = False
        self.timeout_on_open = False
        self.next_observation = []
        self.reconcile_receipt = None

    def open_new(self, provider):
        self.open_calls.append(provider)
        number = len(self.open_calls)
        handle = {"provider": provider, "opaque_id": f"{provider}-fixture-{number}",
                  "mode": "browser", "observed": True}
        self.known[handle["opaque_id"]] = handle
        if self.timeout_on_open:
            raise TimeoutError("Host did not confirm whether a new chat was opened")
        return handle

    def attach_existing(self, provider, reference):
        self.attach_calls.append((provider, reference))
        if reference != "owner-approved-existing-tab":
            raise PermissionError("No verified owner binding")
        handle = {"provider": provider, "opaque_id": f"{provider}-existing",
                  "mode": "browser", "observed": True}
        self.known[handle["opaque_id"]] = handle
        return handle

    def submit_once(self, handle, text, request_id):
        self.submit_calls.append((handle["opaque_id"], text, request_id))
        if self.timeout_on_submit:
            raise TimeoutError("Host lost response after possible submit")
        return {"submitted": True, "observed": True, "host_message_id": "message-1"}

    def observe(self, handle, after):
        self.observe_calls.append((handle["opaque_id"], after))
        return {"messages": self.next_observation, "cursor": "next-visible-cursor"}

    def reconcile(self, handle, request_id):
        return self.reconcile_receipt


class ChatSurfaceGatewayTests(unittest.TestCase):
    def setUp(self):
        self.host = FakeChatSurface()
        self.gateway = ChatSurfaceGateway(self.host, authorized_providers={"chatgpt", "claude", "grok", "bandmates"},
                                          operator_authorized=True)

    def test_open_send_observe_reply_and_continue_same_verified_chat(self):
        session = self.gateway.open_new("chatgpt", request_id="open-chatgpt")
        self.assertEqual(session["provider"], "chatgpt")
        self.assertEqual(session["mode"], "browser")
        self.assertTrue(session["observed"])
        first = self.gateway.submit(session, "Request analysis", request_id="rdc-chat-req-1")
        self.assertEqual(first["state"], "SUBMITTED_OBSERVED")
        self.host.next_observation = [{"text": "The analysis is complete", "role": "assistant",
                                       "message_id": "reply-1"}]
        observed = self.gateway.observe(session, after="before-request")
        self.assertEqual(observed["messages"][0]["text"], "The analysis is complete")
        self.assertEqual(observed["cursor"], "next-visible-cursor")
        followup = self.gateway.submit(session, "Please provide follow-up", request_id="rdc-chat-req-2")
        self.assertEqual(followup["state"], "SUBMITTED_OBSERVED")
        self.assertEqual(self.host.open_calls, ["chatgpt"])
        self.assertEqual(len(self.host.submit_calls), 2)

    def test_existing_chat_attachment_requires_owner_verified_binding(self):
        session = self.gateway.attach_existing("claude", "owner-approved-existing-tab")
        self.assertTrue(session["observed"])
        self.assertEqual(session["provider"], "claude")
        with self.assertRaises(ChatSurfaceUnavailable):
            self.gateway.attach_existing("claude", "unverified-tab")
        self.assertEqual(len(self.host.known), 1)

    def test_unapproved_provider_or_unavailable_host_capability_does_not_launch(self):
        disallowed = ChatSurfaceGateway(self.host, authorized_providers={"chatgpt"},
                                        operator_authorized=False)
        with self.assertRaises(ChatSurfaceUnavailable):
            disallowed.open_new("chatgpt", request_id="open-chatgpt")
        with self.assertRaises(ChatSurfaceUnavailable):
            self.gateway.open_new("unapproved-provider", request_id="open-unapproved-provider")
        self.host.capabilities.remove("open_new")
        with self.assertRaises(ChatSurfaceUnavailable):
            self.gateway.open_new("grok", request_id="open-grok")
        self.assertEqual(self.host.open_calls, [])

    def test_new_chat_requires_two_way_host_capabilities_before_opening(self):
        self.host.capabilities.remove("observe")
        with self.assertRaises(ChatSurfaceUnavailable):
            self.gateway.open_new("chatgpt", request_id="missing-observe")
        self.assertEqual(self.host.open_calls, [])
        self.host.capabilities.add("observe")
        self.host.capabilities.remove("submit_once")
        with self.assertRaises(ChatSurfaceUnavailable):
            self.gateway.open_new("chatgpt", request_id="missing-send")
        self.assertEqual(self.host.open_calls, [])

    def test_uncertain_new_chat_open_is_not_automatically_repeated(self):
        self.host.timeout_on_open = True
        first = self.gateway.open_new("chatgpt", request_id="new-chat-1")
        self.assertEqual(first["state"], "OUTCOME_UNKNOWN")
        second = self.gateway.open_new("chatgpt", request_id="new-chat-1")
        self.assertEqual(second, first)
        self.assertEqual(len(self.host.open_calls), 1)
        with self.assertRaises(ChatSurfaceError):
            self.gateway.open_new("claude", request_id="new-chat-1")

    def test_exact_request_is_idempotent_but_changed_text_conflicts(self):
        session = self.gateway.open_new("grok", request_id="open-grok")
        a = self.gateway.submit(session, "Analyze this", request_id="stable-key-1")
        b = self.gateway.submit(session, "Analyze this", request_id="stable-key-1")
        self.assertEqual(a, b)
        self.assertEqual(len(self.host.submit_calls), 1)
        with self.assertRaises(ChatSurfaceError):
            self.gateway.submit(session, "Changed instruction", request_id="stable-key-1")
        self.assertEqual(len(self.host.submit_calls), 1)

    def test_uncertain_chat_submit_never_replays_without_verified_reconcile(self):
        session = self.gateway.open_new("claude", request_id="open-claude")
        self.host.timeout_on_submit = True
        result = self.gateway.submit(session, "Check code", request_id="uncertain-send-1")
        self.assertEqual(result["state"], "OUTCOME_UNKNOWN")
        again = self.gateway.submit(session, "Check code", request_id="uncertain-send-1")
        self.assertEqual(again, result)
        self.assertEqual(len(self.host.submit_calls), 1)
        self.host.reconcile_receipt = {"request_id": "uncertain-send-1", "observed": True,
                                      "submitted": True, "host_message_id": "verified-1"}
        recovered = self.gateway.reconcile(session, request_id="uncertain-send-1")
        self.assertEqual(recovered["state"], "SUBMITTED_OBSERVED")
        self.assertEqual(len(self.host.submit_calls), 1)

    def test_foreign_handle_or_unverified_host_evidence_is_rejected(self):
        a = self.gateway.open_new("bandmates", request_id="open-bandmates")
        foreign = {"provider": "bandmates", "opaque_id": "not-bound", "observed": True}
        with self.assertRaises(ChatSurfaceUnavailable):
            self.gateway.submit(foreign, "Go live", request_id="wrong-handle")
        with self.assertRaises(ChatSurfaceError):
            self.gateway.submit(a, "password: secret", request_id="credential")
        self.assertEqual(self.host.submit_calls, [])

    def test_observation_must_not_claim_unsupported_host_permissions(self):
        session = self.gateway.open_new("chatgpt", request_id="open-chatgpt")
        self.host.capabilities.remove("observe")
        with self.assertRaises(ChatSurfaceUnavailable):
            self.gateway.observe(session, after="cursor")
        self.assertEqual(self.host.observe_calls, [])


if __name__ == "__main__":
    unittest.main()
