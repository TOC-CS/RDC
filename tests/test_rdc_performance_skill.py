"""Portable RDC coding/batching skill must match the integrated tool catalog."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CODING = ROOT / "skills" / "rdc-coding" / "SKILL.md"
MAIN = ROOT / "skills" / "rdc" / "SKILL.md"


class RDCPerformanceSkillContracts(unittest.TestCase):
    def test_coding_skill_has_portable_frontmatter_and_guarded_batch_contract(self):
        text = CODING.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: rdc-coding\n"))
        for term in ("rdc_code_context", "rdc_code_edit_many", "search_mode",
                     "expected_sha256", "rdc_job_run", "rdc_recent_operation_metrics",
                     "Desktop Commander", "partial", "no replay"):
            self.assertIn(term.lower(), text.lower())

    def test_single_call_browser_actions_are_documented_without_claiming_live_deployment(self):
        root = MAIN.read_text(encoding="utf-8")
        for name in ("rdc_browser_start_navigate_observe",
                     "rdc_browser_navigate_observe", "rdc_browser_click_observe",
                     "rdc_browser_fill_observe"):
            self.assertIn(name, root)
        self.assertIn("rdc-coding/SKILL.md", root)
        self.assertIn("deployed", root.lower())
