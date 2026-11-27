"""Owner-mandated maximum of 100 RDC test executions per campaign."""
import unittest
from pathlib import Path
from scripts.rdc_test_budget import (
    MAX_RDC_TESTS, TestBudgetExceeded, validate_budget,
    distribute_security_checks, count_node_test_cases, preflight_campaign,
    load_policy,
)

ROOT = Path(__file__).resolve().parent.parent


class RDC100BudgetTests(unittest.TestCase):
    def test_absolute_cap_is_exactly_100(self):
        self.assertEqual(MAX_RDC_TESTS, 100)
        self.assertEqual(validate_budget({"javascript": 86, "python": 14}), 100)
        self.assertEqual(validate_budget({"security": 100}), 100)

    def test_101_or_multiplying_three_categories_fails_before_execution(self):
        for parts in ({"security": 101}, {"a": 34, "b": 34, "c": 33},
                      {"security_a": 100, "security_b": 100, "security_c": 100}):
            with self.subTest(parts=parts), self.assertRaises(TestBudgetExceeded):
                validate_budget(parts)

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

    def test_default_core_campaign_cannot_exceed_100(self):
        data = preflight_campaign(ROOT, "local-core")
        self.assertEqual(data["max_cases"], 100)
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

    def test_policy_rejects_oversized_override_even_if_requested(self):
        with self.assertRaises(TestBudgetExceeded):
            validate_budget({"name": 100}, limit=101)

    def test_ci_workflow_uses_shared_100_case_governor(self):
        workflow = (ROOT / ".github/workflows/test.yml").read_text()
        self.assertIn("scripts/rdc_test_budget.py", workflow)
        self.assertEqual(workflow.count("test_budget: "), 3)
        self.assertIn("test_budget: 34", workflow)
        self.assertEqual(workflow.count("test_budget: 33"), 2)
        self.assertNotIn("run: python -m unittest discover", workflow)
        self.assertNotIn("run: node --test", workflow)

    def test_101_node_declarations_rejected_before_runner_start(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "overbudget.test.mjs"
            path.write_text("import test from 'node:test';\n" +
                            "test('case', () => {});\n" * 101)
            with self.assertRaises(TestBudgetExceeded):
                count_node_test_cases(path)

if __name__ == "__main__":
    unittest.main()
