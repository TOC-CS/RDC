"""RDC live ChatGPT and independently approved Atlas routing skill contract."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SKILL=(ROOT/"skills/rdc-communications/SKILL.md")
LIVE=(ROOT/"skills/rdc-communications/references/live-chat-interface.md")
ROUTES=(ROOT/"skills/rdc-communications/references/cross-project-routing.md")

class LiveChatSkillTests(unittest.TestCase):
    def test_live_tools_are_described_without_false_activated_claim(self):
        text=LIVE.read_text().lower()
        for name in ("rdc_chat_inbox","rdc_chat_send","rdc_chat_reply","rdc_chat_ack",
                     "rdc_chat_create","rdc_chat_wake","rdc_chat_route_status",
                     "rdc_chat_cross_project_send"):
            self.assertIn(name,text)
        for phrase in ("not deployed","independently verified","session membership",
                       "host adapter","outcome_unknown","no replay","no browser takeover"):
            self.assertIn(phrase,text)
    def test_atlas_manager_routes_require_independent_per_direction_approval(self):
        text=ROUTES.read_text().lower()
        for phrase in ("atlas","rdc","bandmates","presentation","bus",
                       "cross_project_denied","cross-project","independent approval",
                       "reverse direction","recipient acknowledgment",
                       "reply readback","no competing bus"):
            self.assertIn(phrase,text)
        self.assertIn("project owner",text)
    def test_communication_skill_links_to_live_and_route_references(self):
        root=SKILL.read_text().lower()
        self.assertIn("live-chat-interface.md",root)
        self.assertIn("cross-project-routing.md",root)
        self.assertIn("not deployed",root)
        self.assertIn("public release",root)
        self.assertIn("on hold",root)

if __name__=="__main__":
    unittest.main()
