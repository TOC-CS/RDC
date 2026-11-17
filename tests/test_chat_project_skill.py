"""Public RDC/DC one-time project activation skill contract tests.

Documentation tests do not establish actual ChatGPT host capabilities.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "rdc-communications" / "SKILL.md"
PROJECT = ROOT / "skills" / "rdc-communications" / "references" / "project-activation.md"
REFERENCE = ROOT / "skills" / "rdc-communications" / "references" / "integration.md"

class ProjectActivationSkillTests(unittest.TestCase):
    def test_one_activation_covers_verified_chats_without_repeated_owner_prompts(self):
        text = SKILL.read_text(encoding="utf-8").lower()
        reference = PROJECT.read_text(encoding="utf-8").lower()
        for term in ("one-time project activation", "rdc", "desktop commander",
                     "create", "wake", "no repeated approval", "revocation",
                     "host-authenticated", "scope"):
            with self.subTest(term=term):
                self.assertIn(term, text + "\n" + reference)
        self.assertIn("rdc.chat_project_actions", reference)
        self.assertIn("projectactionstore", reference)
        self.assertIn("projectchatactions", reference)

    def test_public_instruction_distinguishes_host_wake_from_model_resume(self):
        text = PROJECT.read_text(encoding="utf-8").lower()
        for term in ("model_resumed", "false", "outcome_unknown",
                     "busy", "interrupted", "source project", "consumer chatgpt",
                     "capability", "without side effects", "credentials", "public"):
            with self.subTest(term=term):
                self.assertIn(term, text)
        self.assertIn("no guaranteed wake", text)
        self.assertIn("verified readback", text)
        self.assertIn("direct chat", REFERENCE.read_text(encoding="utf-8").lower())

    def test_public_skill_does_not_claim_live_enrollment(self):
        text=SKILL.read_text(encoding="utf-8").lower()
        self.assertIn("synthetic", text)
        self.assertIn("real host", text)
        self.assertIn("github", text)
        self.assertIn("public", text)
        self.assertIn("not yet", text)

if __name__ == "__main__":
    unittest.main()
