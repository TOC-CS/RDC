"""RDC communication skill discoverability and safety contract.

Documentation tests supplement but cannot replace real agent pressure tests.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "rdc-communications" / "SKILL.md"
REFERENCE = ROOT / "skills" / "rdc-communications" / "references" / "integration.md"
RDC_SKILL = ROOT / "skills" / "rdc" / "SKILL.md"


class RDCCommunicationsSkillTests(unittest.TestCase):
    def test_existing_rdc_skill_points_to_communications_skill(self):
        parent = RDC_SKILL.read_text(encoding="utf-8")
        self.assertIn("rdc-communications", parent)
        self.assertIn("cross-session", parent.lower())

    def test_skill_is_discoverable_with_correct_trigger_and_all_three_lanes(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: rdc-communications\n"))
        self.assertIn("description: Use when", text)
        self.assertIn("message bus", text.lower())
        self.assertIn("terminal", text.lower())
        self.assertIn("direct chat", text.lower())
        self.assertIn("chatgpt", text.lower())
        self.assertIn("claude", text.lower())
        self.assertIn("grok", text.lower())
        self.assertIn("bandmates", text.lower())

    def test_one_skill_supports_rdc_and_dc_for_two_or_three_chatgpt_sessions(self):
        text = SKILL.read_text(encoding="utf-8").lower()
        reference = REFERENCE.read_text(encoding="utf-8").lower()
        self.assertIn("desktop commander", text)
        self.assertIn("rdc_job_run", text)
        self.assertIn("start_process", text)
        self.assertIn("same shared", text)
        self.assertIn("2-way", text)
        self.assertIn("3-way", text)
        self.assertIn("room-send", reference)
        self.assertIn("room-id", reference)
        self.assertIn("rdc.chat_rooms", reference)
        self.assertIn("active chatgpt", reference)
        self.assertIn("cannot automatically wake", reference)

    def test_session_continuity_messages_cannot_stop_or_take_over_active_peer(self):
        text = SKILL.read_text(encoding="utf-8").lower()
        reference = REFERENCE.read_text(encoding="utf-8").lower()
        self.assertIn("continuitygate", text)
        self.assertIn("session_busy", text)
        self.assertIn("session_interrupted", text)
        self.assertIn("delivery_unconfirmed", text)
        self.assertIn("do not stop", text)
        self.assertIn("no automatic wake", text)
        self.assertIn("recipient", text)
        self.assertIn("pull-only", reference)
        self.assertIn("new connection epoch", reference)
        self.assertIn("outcome_unknown", reference)
        self.assertIn("desktop commander", reference)
        self.assertIn("single-flight", text)
        self.assertIn("fresh readiness signal", reference)

    def test_skill_refuses_unverified_real_chat_claims_and_unsafe_replay(self):
        text = SKILL.read_text(encoding="utf-8").lower()
        self.assertIn("synthetic", text)
        self.assertIn("no replay", text)
        self.assertIn("owner", text)
        self.assertIn("unauthorized", text)
        self.assertIn("browser", text)
        self.assertIn("api", text)
        self.assertIn("blocked", text)
        self.assertIn("verify", text)
        self.assertIn("response", text)
        self.assertIn("cursor", text)

    def test_skill_reference_specifies_enrollment_and_live_bandmates_boundaries(self):
        text = REFERENCE.read_text(encoding="utf-8").lower()
        self.assertIn("rdc.chatctl", text)
        self.assertIn("rdc.chat_interconnect", text)
        self.assertIn("rdc.chat_surface", text)
        self.assertIn("real chat", text)
        self.assertIn("operator approval", text)
        self.assertIn("bandmates", text)
        self.assertIn("audio", text)
        self.assertIn("midi", text)
        self.assertIn("atlas.bus.message.v1", text)
        self.assertIn("outcome_unknown", text)


if __name__ == "__main__":
    unittest.main()
