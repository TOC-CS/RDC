"""RDC coding and terminal workload, using disposable local files only.

This measures deterministic Engine calls and separate synthetic worker
processes. It does NOT compare RDC against Desktop Commander or claim
that separate Python processes are independent AI agents. There are no
network requests, owner desktop actions, real repositories or hosted AI calls.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rdc.config import Settings
from rdc.engine import Engine


SOURCE_BROKEN = "# coding test: שלום\ndef add(a, b):\n    return a - b\n"
SOURCE_FIXED = SOURCE_BROKEN.replace("return a - b", "return a + b")
TEST_ORIGINAL = (
    "import unittest\n"
    "from calc import add\n"
    "class AddTests(unittest.TestCase):\n"
    "    def test_simple(self): self.assertEqual(add(3, 2), 5)\n"
)
TEST_NEW = (
    "import unittest\n"
    "from calc import add\n"
    "class EdgeTests(unittest.TestCase):\n"
    "    def test_negatives(self): self.assertEqual(add(-2, 7), 5)\n"
)
TERMINAL_STATES = {"completed", "failed", "timed_out", "cancelled", "interrupted"}


def percentile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        raise ValueError("Cannot summarize empty benchmark")
    index = (len(ordered) - 1) * fraction
    low = int(index)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def summarize(samples):
    times = [s["elapsed_ms"] for s in samples]
    return {
        "runs": len(times),
        "correct": sum(bool(s["correct"]) for s in samples),
        "failures": sum(not s["correct"] for s in samples),
        "p50_ms": round(statistics.median(times), 3),
        "p95_ms": round(percentile(times, 0.95), 3),
        "p99_ms": round(percentile(times, 0.99), 3),
        "min_ms": round(min(times), 3),
        "max_ms": round(max(times), 3),
        "stddev_ms": round(statistics.pstdev(times), 3),
    }


def _must(response, name):
    if response.get("ok") is not True:
        raise AssertionError(name + " failed: " + repr(response.get("error", response)))
    return response


def _job(engine, args, stages, stage):
    t = time.perf_counter()
    response = _must(engine.call("rdc_job_run", args), stage)
    identifier = response["job"]["id"]
    if not response["complete"]:
        deadline = time.monotonic() + 18
        while time.monotonic() < deadline:
            state = _must(engine.call("rdc_job_status", {"job_id": identifier}), stage + " status")
            if state["job"]["status"] in TERMINAL_STATES:
                break
            time.sleep(0.015)
        else:
            raise RuntimeError("Durable job did not reach terminal state")
        output = _must(engine.call("rdc_job_output", {"job_id": identifier, "offset": 0}), stage + " output")
        response = {**response, "job": state["job"], "output": output, "complete": True}
    stages[stage] = round((time.perf_counter() - t) * 1000, 3)
    return response


def execute_case(case_id=0):
    """One independent actual coding workflow, with its own Engine and state."""
    start = time.perf_counter()
    stages = {}
    with tempfile.TemporaryDirectory(prefix="rdc-code-agent-bench-") as scratch:
        scratch = Path(scratch)
        project = scratch / "project"
        test_dir = project / "tests"
        test_dir.mkdir(parents=True)
        source = project / "calc.py"
        source.write_text(SOURCE_BROKEN, encoding="utf-8")
        original_test = test_dir / "test_calc.py"
        original_test.write_text(TEST_ORIGINAL, encoding="utf-8")
        added_test = test_dir / "test_extra.py"
        outside = scratch / "outside-denied.txt"
        engine = Engine(Settings(
            state_dir=scratch / "engine-private-state",
            roots=[project], browser_backend="disabled",
            approval_mode="trusted", allow_exec=True,
        ))
        try:
            begin = time.perf_counter()
            listing = _must(engine.call("rdc_file_list", {"path": str(project)}), "list")
            assert {"calc.py", "tests"}.issubset({e["name"] for e in listing["entries"]})
            stages["list"] = round((time.perf_counter() - begin) * 1000, 3)

            begin = time.perf_counter()
            found = _must(engine.call("rdc_file_search", {"path": str(project), "query": "return a - b"}), "search")
            assert len(found["matches"]) == 1 and found["matches"][0]["line"] == 3
            stages["search"] = round((time.perf_counter() - begin) * 1000, 3)

            begin = time.perf_counter()
            read = _must(engine.call("rdc_file_read_many",
                                     {"file_paths": [str(source), str(original_test)]}), "read_many")
            assert len(read["results"]) == 2
            assert all(x["ok"] for x in read["results"])
            assert read["results"][0]["text"] == SOURCE_BROKEN
            original_sha = read["results"][0]["sha256"]
            assert original_sha == hashlib.sha256(SOURCE_BROKEN.encode()).hexdigest()
            stages["read_many"] = round((time.perf_counter() - begin) * 1000, 3)

            # The failing and corrected source lines have identical byte length. A
            # timestamp-based .pyc cache can otherwise reuse the old code if
            # the two tests start inside the same filesystem mtime tick.
            # Both runs use -B to execute the actual edited source deterministically.
            command = [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-q"]
            test_args = {"argv": command, "cwd": str(project), "timeout": 20,
                         "wait_ms": 3000, "output_limit": 8192,
                         "idempotency_key": f"code-verified-{case_id}"}
            initial = _job(engine, {**test_args, "idempotency_key": f"code-broken-{case_id}"},
                           stages, "initial_failing_test")
            assert initial["job"]["exit_code"] == 1
            assert "FAIL" in initial["output"]["text"]

            begin = time.perf_counter()
            edit = _must(engine.call("rdc_file_edit", {
                "file_path": str(source), "old_text": "return a - b",
                "new_text": "return a + b", "expected_sha256": original_sha,
                "expected_count": 1,
            }), "edit")
            assert edit["replacements"] == 1
            expected_sha = hashlib.sha256(SOURCE_FIXED.encode()).hexdigest()
            assert edit["sha256"] == expected_sha
            stages["edit"] = round((time.perf_counter() - begin) * 1000, 3)

            begin = time.perf_counter()
            new_file = _must(engine.call("rdc_file_write", {
                "file_path": str(added_test), "content": TEST_NEW,
            }), "new test")
            assert new_file["sha256"] == hashlib.sha256(TEST_NEW.encode()).hexdigest()
            stages["create"] = round((time.perf_counter() - begin) * 1000, 3)

            fixed = _job(engine, test_args, stages, "corrected_tests")
            assert fixed["job"]["exit_code"] == 0 and fixed["job"]["status"] == "completed", {"exit": fixed["job"]["exit_code"], "output": fixed["output"]["text"][:850]}
            assert "OK" in fixed["output"]["text"]
            original_job_id = fixed["job"]["id"]
            begin = time.perf_counter()
            replay = _must(engine.call("rdc_job_run", test_args), "idempotent recovery")
            same_job = replay["reused"] is True and replay["job"]["id"] == original_job_id
            assert same_job
            stages["idempotent_recovery"] = round((time.perf_counter() - begin) * 1000, 3)

            negative = _job(engine, {
                "argv": [sys.executable, "-c",
                         "import sys;sys.stderr.write('RDC-CODE-EXPECTED-23\\n');sys.exit(23)"],
                "cwd": str(project), "timeout": 20, "wait_ms": 3000,
                "output_limit": 8192, "idempotency_key": f"code-nonzero-{case_id}",
            }, stages, "nonzero_terminal")
            assert negative["job"]["exit_code"] == 23
            assert "RDC-CODE-EXPECTED-23" in negative["output"]["text"]

            begin = time.perf_counter()
            stale = engine.call("rdc_file_edit", {
                "file_path": str(source), "old_text": "return a + b",
                "new_text": "return b - a", "expected_sha256": original_sha,
                "expected_count": 1,
            })
            stale_blocked = stale.get("ok") is False and stale["error"]["code"] == "conflict"
            assert stale_blocked
            denied = engine.call("rdc_file_write", {
                "file_path": str(outside), "content": "ACCESS_DENIED",
            })
            outside_blocked = denied.get("ok") is False and denied["error"]["code"] == "path_denied"
            assert outside_blocked and not outside.exists()
            stages["isolation_and_conflict"] = round((time.perf_counter() - begin) * 1000, 3)

            begin = time.perf_counter()
            verified = _must(engine.call("rdc_file_read", {
                "file_path": str(source), "offset": 0,
            }), "final readback")
            assert verified["text"] == SOURCE_FIXED
            assert verified["sha256"] == expected_sha
            assert added_test.read_text(encoding="utf-8") == TEST_NEW
            stages["readback"] = round((time.perf_counter() - begin) * 1000, 3)
            result = {
                "correct": True,
                "initial_test_exit_code": initial["job"]["exit_code"],
                "corrected_test_exit_code": fixed["job"]["exit_code"],
                "negative_terminal_exit_code": negative["job"]["exit_code"],
                "idempotent_recovery_same_job": same_job,
                "stale_sha_conflict_blocked": stale_blocked,
                "outside_root_blocked": outside_blocked,
                "patched_source": "return a + b",
                "expected_sha256": expected_sha,
                "read_back_sha256": verified["sha256"],
                "stages_ms": stages,
            }
        finally:
            engine.close()
    result["elapsed_ms"] = round((time.perf_counter() - start) * 1000, 3)
    return result


def run_local(trials=30, warmups=3, concurrency=(), concurrent_tasks_per_worker=2):
    if not 1 <= trials <= 200 or not 0 <= warmups <= 20:
        raise ValueError("Invalid counted trials or warmups")
    if not 1 <= concurrent_tasks_per_worker <= 8:
        raise ValueError("Invalid parallel task count")
    if any(level not in (1, 2, 4, 8, 16) for level in concurrency):
        raise ValueError("Unsupported benchmark concurrency")
    for i in range(warmups):
        execute_case(-i - 1)
    samples = [execute_case(i + 1) for i in range(trials)]
    if not all(s["correct"] for s in samples):
        raise AssertionError("Benchmark accuracy regression")
    summary = {**summarize(samples), "samples": samples}
    concurrent = []
    for workers in concurrency:
        cases = workers * concurrent_tasks_per_worker
        started = time.perf_counter()
        # Each process gets an independent Engine, workspace, SQLite state and job set.
        with ProcessPoolExecutor(max_workers=workers) as pool:
            rows = list(pool.map(execute_case, range(10000 + workers * 100, 10000 + workers * 100 + cases)))
        elapsed = time.perf_counter() - started
        if not all(row["correct"] for row in rows):
            raise AssertionError("Parallel benchmark accuracy regression")
        concurrent.append({
            "workers": workers, "tasks": cases, "correct": cases, "failures": 0,
            "wall_ms": round(elapsed * 1000, 3),
            "throughput_correct_tasks_per_s": round(cases / elapsed, 3),
            "per_task": summarize(rows),
            "samples": rows,
            "isolation": "separate system processes with independent temporary RDC Engine roots",
            "agent_claim": "synthetic coding workers, not independent AI model agents",
        })
    return {
        "source": "isolated RDC Engine",
        "comparison": "direct local synthetic coding workload; NO DC head-to-head evidence",
        "python_version": sys.version.split()[0], "os": platform.system(),
        "trials_per_method": trials, "warmups": warmups,
        "sequential": summary, "concurrency": concurrent,
        "limitations": [
            "Host/connector latency is excluded",
            "Independent model-driven multi-agent coding remains unverified",
            "No owner files, actual browser, AI API, production gateway, or BandMates touched",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=30)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--concurrency", default="1,2,4",
                        help="Comma-separated isolated worker process counts (1,2,4,8,16)")
    parser.add_argument("--tasks-per-worker", type=int, default=2)
    parser.add_argument("--output", type=Path, help="Write raw results JSON here")
    args = parser.parse_args()
    levels = tuple(int(x) for x in args.concurrency.split(",") if x.strip())
    report = run_local(args.trials, args.warmups, levels, args.tasks_per_worker)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sequential": {k: v for k, v in report["sequential"].items() if k != "samples"},
                      "concurrency": [{k: v for k, v in x.items() if k != "samples"} for x in report["concurrency"]]}, indent=2))
    if args.output:
        print("RAW_RESULTS=" + str(args.output))
