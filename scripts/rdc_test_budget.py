"""TOC RDC test-execution governor. Hard cap: 100 total cases per campaign.

Use this entry point for local/CI RDC testing. Counts are checked before
executing any test. Source tests remain preserved for later, separately
authorized bounded campaigns. Local results never qualify hosted speed gates.
"""
from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import unittest

MAX_RDC_TESTS = 100
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
NODE_DECLARATION = re.compile(r"(?m)^\s*(?:test|it)\s*\(")
NODE_REPORTED = re.compile(r"(?m)^(?:#\s*tests\s+|ℹ\s+tests\s+)(\d+)\s*$")


class TestBudgetExceeded(ValueError):
    """Request was refused before running more than 100 RDC test cases."""


def _integer(value, name: str, *, positive: bool = False) -> int:
    if type(value) is not int or value < (1 if positive else 0):
        raise TestBudgetExceeded(f"{name} must be a nonnegative integer")
    return value


def validate_budget(allocations: dict[str, int], *, limit: int = MAX_RDC_TESTS) -> int:
    _integer(limit, "budget", positive=True)
    if limit > MAX_RDC_TESTS:
        raise TestBudgetExceeded("RDC hard ceiling is 100 tests. Override refused.")
    if not isinstance(allocations, dict) or not allocations:
        raise TestBudgetExceeded("Test allocation is missing")
    total = 0
    for name, count in allocations.items():
        if not isinstance(name, str) or not name.strip():
            raise TestBudgetExceeded("Invalid test category")
        _integer(count, name)
        total += count
    if total > limit:
        raise TestBudgetExceeded(
            f"Rejected before execution: {total} RDC cases across categories; maximum {limit}."
        )
    return total


def distribute_security_checks(total: int = MAX_RDC_TESTS) -> dict[str, int]:
    _integer(total, "security total", positive=True)
    validate_budget({"all hostile categories combined": total})
    groups = ("unauthenticated", "wrong_owner", "wrong_socket_key")
    quotient, remainder = divmod(total, len(groups))
    return {name: quotient + (index < remainder) for index, name in enumerate(groups)}


def count_node_test_cases(path: Path) -> int:
    path = Path(path)
    if not path.is_file() or path.suffix != ".mjs" or path.stat().st_size > 1024 * 1024:
        raise TestBudgetExceeded(f"Missing or oversized Node test: {path.name}")
    content = path.read_text(encoding="utf-8")
    count = len(NODE_DECLARATION.findall(content))
    if not 1 <= count <= MAX_RDC_TESTS:
        raise TestBudgetExceeded(
            f"Unsafe Node test declaration count for {path.name}: {count}"
        )
    return count


def load_policy(root: Path = ROOT) -> dict:
    doc = Path(root) / "docs/rdc-test-budget-100.json"
    policy = json.loads(doc.read_text(encoding="utf-8"))
    if policy.get("schema_version") != 1 or policy.get("max_cases") != MAX_RDC_TESTS:
        raise TestBudgetExceeded("Policy must pin hard ceiling to exactly 100")
    if not isinstance(policy.get("campaigns"), dict):
        raise TestBudgetExceeded("Missing test campaigns")
    return policy


def preflight_campaign(root: Path, campaign: str) -> dict:
    root = Path(root).resolve()
    policy = load_policy(root)
    entry = policy["campaigns"].get(campaign)
    if not isinstance(entry, dict):
        raise TestBudgetExceeded(f"Unknown campaign: {campaign}")
    files = entry.get("node_files")
    if not isinstance(files, list) or len(files) > MAX_RDC_TESTS:
        raise TestBudgetExceeded("Invalid Node test file manifest")
    node_cases = 0
    paths = []
    for name in files:
        if not isinstance(name, str):
            raise TestBudgetExceeded("Invalid Node test path")
        resolved = (root / name).resolve()
        safe_tree = resolved.is_relative_to(root / "cloud-gateway/tests")
        safe_gate = (campaign == "speed-acceptance-contract" and
                     resolved == root / "benchmarks/rdc_speed_acceptance.test.mjs")
        if not (safe_tree or safe_gate):
            raise TestBudgetExceeded("Node tests cannot escape the authorized source test trees")
        node_cases += count_node_test_cases(resolved)
        paths.append(str(resolved.relative_to(root)))
    python_cases = _integer(entry.get("python_take"), "Python count")
    offset = _integer(entry.get("python_offset"), "Python offset")
    if python_cases and not (entry.get("python_discovery") is True or
                             isinstance(entry.get("python_module"), str)):
        raise TestBudgetExceeded("Python selection is missing")
    planned = validate_budget({"node": node_cases, "python": python_cases})
    return {"campaign": campaign, "max_cases": MAX_RDC_TESTS,
            "planned_total": planned, "node_cases": node_cases,
            "python_cases": python_cases, "python_offset": offset,
            "node_files": paths, "python_discovery": bool(entry.get("python_discovery")),
            "python_module": entry.get("python_module")}


def _iter_python_cases(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter_python_cases(item)
        else:
            yield item


def _select_python_tests(root: Path, plan: dict):
    if plan["python_cases"] == 0:
        return []
    loader = unittest.TestLoader()
    if plan["python_discovery"]:
        suite = loader.discover(str(root / "tests"), pattern="test_*.py",
                                top_level_dir=str(root))
    else:
        suite = loader.loadTestsFromName(plan["python_module"])
    candidates = sorted(_iter_python_cases(suite), key=lambda case: case.id())
    end = plan["python_offset"] + plan["python_cases"]
    if end > len(candidates):
        raise TestBudgetExceeded("Python suite has fewer tests than the declared allocation")
    selected = candidates[plan["python_offset"]:end]
    if any(case.id().startswith("unittest.loader._FailedTest") for case in selected):
        raise TestBudgetExceeded("Python discovery failed; no tests executed")
    return selected


def _run_campaign(root: Path, plan: dict, output_dir: Path) -> dict:
    # Prepare *all* case identities before running Node or Python tests.
    root = Path(root).resolve()
    selected = _select_python_tests(root, plan)
    validate_budget({"node": plan["node_cases"], "python": len(selected)})
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "scope": "RDC local or CI capped test campaign",
        "campaign": plan["campaign"],
        "limit": MAX_RDC_TESTS,
        "planned_total": plan["planned_total"],
        "executed_total": 0,
        "node": {"planned": plan["node_cases"], "executed": 0},
        "python": {"planned": len(selected), "executed": 0},
        "source": str(root),
        "passed": False,
        "untested_cases_remain": True,
    }
    try:
        if plan["node_cases"]:
            names = plan["node_files"]
            result = subprocess.run(
                ["node", "--test", *names], cwd=root, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120,
                check=False,
            )
            (output_dir / f"{plan['campaign']}-node.log").write_text(
                result.stdout, encoding="utf-8"
            )
            match = NODE_REPORTED.search(result.stdout)
            if not match:
                raise TestBudgetExceeded("Node did not report its exact executed test count")
            actual = int(match.group(1))
            if actual != plan["node_cases"]:
                raise TestBudgetExceeded(
                    f"Node discovered {actual} cases vs preflight {plan['node_cases']}"
                )
            report["node"] = {"planned": plan["node_cases"], "executed": actual,
                              "exit_code": result.returncode}
            report["executed_total"] += actual
            if result.returncode:
                return report
        if selected:
            out = io.StringIO()
            result = unittest.TextTestRunner(stream=out, verbosity=1).run(
                unittest.TestSuite(selected)
            )
            (output_dir / f"{plan['campaign']}-python.log").write_text(
                out.getvalue(), encoding="utf-8"
            )
            report["python"] = {
                "planned": len(selected), "executed": result.testsRun,
                "failures": len(result.failures), "errors": len(result.errors),
                "skipped": len(result.skipped),
            }
            report["executed_total"] += result.testsRun
            if not result.wasSuccessful():
                return report
        report["passed"] = True
        return report
    finally:
        if report["executed_total"] > MAX_RDC_TESTS:
            report["passed"] = False
            raise TestBudgetExceeded("Unexpected test count over hard ceiling")


def main() -> int:
    parser = argparse.ArgumentParser(description="RDC max-100 test governor")
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()
    try:
        plan = preflight_campaign(ROOT, args.campaign)
        policy = load_policy(ROOT)
        # Enforce the TOTAL CI matrix budget before allowing any platform job.
        if args.campaign in policy["ci_matrix"].values():
            allocations = {
                os_name: preflight_campaign(ROOT, name)["planned_total"]
                for os_name, name in policy["ci_matrix"].items()
            }
            validate_budget(allocations)
        if args.dry_run:
            print(json.dumps({**plan, "status": "preflight-only", "passed": True},
                             indent=2))
            return 0
        destination = args.report or (
            ROOT / "test-results" / (args.campaign + "-100-budget.json")
        )
        report = _run_campaign(ROOT, plan, destination.parent)
        destination.write_text(json.dumps(report, indent=2) + "\n",
                               encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0 if report["passed"] else 1
    except (TestBudgetExceeded, OSError, ValueError) as error:
        print("RDC TEST BUDGET REJECTED:", error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
