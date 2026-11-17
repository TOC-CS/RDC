"""Documentation checks for trusted ChatGPT in-model tool-call integration."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT/"skills/rdc-communications/SKILL.md"
REFERENCE = ROOT/"skills/rdc-communications/references/chatgpt-host-integration.md"
PROJECT = ROOT/"skills/rdc-communications/references/project-activation.md"


class HostIntegrationSkillTests(unittest.TestCase):
    def test_chatgpt_native_host_metadata_and_verified_project_membership(self):
        content = REFERENCE.read_text(encoding="utf-8").lower()
        for phrase in ("openai/session","openai/subject","_meta",
                       "trusted project registry","chatgpttoolidentitybroker",
                       "projectscopedchatmessenger","one-time project activation",
                       "atlas bus", "rdc", "cross-project", "not supplied",
                       "unverified project"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase,content)

    def test_wake_only_via_supported_subscription_and_user_chosen_chat(self):
        text=REFERENCE.read_text(encoding="utf-8").lower()
        for phrase in ("mcp events","work chats","subscription",
                       "no automatic wake","cannot guarantee","actual chatgpt",
                       "host permissions","model-resumed","no direct browser injection"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase,text)

    def test_release_held_and_shared_instructions_explicit(self):
        s=SKILL.read_text(encoding="utf-8").lower()
        self.assertIn("chatgpt-host-integration.md",s)
        self.assertIn("public release",s)
        self.assertIn("on hold",s)
        self.assertIn("host metadata",s)
        self.assertIn("message",PROJECT.read_text(encoding="utf-8").lower())

if __name__=="__main__":
    unittest.main()
