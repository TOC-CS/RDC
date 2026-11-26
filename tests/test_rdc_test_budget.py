"""RDC scope-based test planning and accounting."""
import unittest
from pathlib import Path
from scripts.rdc_test_budget import (
    TestBudgetExceeded, validate_budget,
    distribute_security_checks, count_node_test_cases, preflight_campaign,
    load_policy,
)

ROOT = Path(__file__).resolve().parent.parent


class RDCBudgetTests(unittest.TestCase):
    def test_default_accepts_more_than_one_hundred(self):
        self.assertEqual(validate_budget({"javascript": 86, "python": 14}), 100)
        self.assertEqual(validate_budget({"security": 101}), 101)
        self.assertEqual(validate_budget({"a": 120, "b": 80}), 200)

    def test_explicit_campaign_limit_is_still_enforced(self):
        self.assertEqual(validate_budget({"a": 120, "b": 80}, limit=200), 200)
        with self.assertRaises(TestBudgetExceeded):
            validate_budget({"a": 120, "b": 81}, limit=200)

    def test_boolean_negative_and_noninteger_budgets_rejected(self):
        for value in (True, 3.5, -1, "100", None):
            with self.subTest(value=value), self.assertRaises(TestBudgetExceeded):
                validate_budget({"security": value})

    def test_security_distributes_one_shared_budget_over_three_categories(self):
        self.assertEqual(distribute_security_checks(),
                         {"unauthenticated": 34, "wrong_owner": 33,
                          "wrong_socket_key": 33})
        self.assertEqual(sum(distribute_security_checks().values()), 100)

    def test_node_suite_admission_count_is_derived_from_source(self):
        self.assertEqual(count_node_test_cases(
            ROOT / "cloud-gateway/tests/v2/actor.test.mjs"), 34)

    def test_default_core_campaign_retains_its_existing_selection(self):
        data = preflight_campaign(ROOT, "local-core")
        self.assertIsNone(data["max_cases"])
        self.assertEqual(data["planned_total"], 100)
        self.assertEqual(data["node_cases"], 86)
        self.assertEqual(data["python_cases"], 14)

    def test_matrix_allocations_sum_to_one_hundred_across_all_os(self):
        policy = load_policy(ROOT)
        matrix = policy["ci_matrix"]
        self.assertEqual(sum(policy["campaigns"][name]["python_take"] +
                             sum(count_node_test_cases(ROOT / path)
                                 for path in policy["campaigns"][name]["node_files"])
                             for name in matrix.values()), 100)

    def test_explicit_larger_security_selection(self):
        self.assertEqual(sum(distribute_security_checks(301).values()), 301)

    def test_ci_workflow_keeps_test_execution_and_evidence(self):
        workflow = (ROOT / ".github/workflows/test.yml").read_text()
        self.assertTrue("scripts/rdc_test_budget.py" in workflow or
                        "python -m unittest discover -s tests" in workflow)
        self.assertTrue("scripts/rdc_test_budget.py" in workflow or
                        "node --test cloud-gateway/tests/" in workflow)
        self.assertIn("actions/upload-artifact", workflow)
        self.assertIn("if: always()", workflow)

    def test_101_node_declarations_admitted_before_runner_start(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "overbudget.test.mjs"
            path.write_text("import test from 'node:test';\n" +
                            "test('case', () => {});\n" * 101)
            self.assertEqual(count_node_test_cases(path), 101)

    def test_manifest_can_plan_more_than_one_hundred(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            manifest = {"schema_version": 1, "max_cases": None,
                        "campaigns": {"extended": {"node_files": [],
                            "python_take": 180, "python_offset": 0,
                            "python_module": "tests.test_mobile"}}}
            (root / "docs/rdc-test-budget-100.json").write_text(json.dumps(manifest))
            self.assertEqual(preflight_campaign(root, "extended")["planned_total"], 180)

if __name__ == "__main__":
    unittest.main()
