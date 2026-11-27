"""Repeatable direct-local RDC terminal latency benchmark, no desktop interaction.

This compares the existing two-tool durable job API with the new single-call
durable fast path inside one Engine process. Tool provider/network latency is
deliberately excluded. Results are NOT a substitute for matched DC benchmarks.
"""
import argparse
import json
import os
import platform
from pathlib import Path
import random
import statistics
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rdc.config import Settings
from rdc.engine import Engine


EXPECTED = "RDC-BENCH-OK" + os.linesep
COMMAND = [sys.executable, "-c", "print('RDC-BENCH-OK')"]
TERMINAL = {"completed", "failed", "timed_out", "cancelled", "interrupted"}


def percentile(values, fraction):
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = fraction * (len(ordered) - 1)
    low = int(index)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def summarize(rows):
    times = [row["elapsed_ms"] for row in rows]
    return {
        "runs": len(rows),
        "correct": sum(row["correct"] for row in rows),
        "failures": sum(not row["correct"] for row in rows),
        "first_call_completed": sum(row["first_call_completed"] for row in rows),
        "p50_ms": round(statistics.median(times), 3),
        "p95_ms": round(percentile(times, 0.95), 3),
        "p99_ms": round(percentile(times, 0.99), 3),
        "stddev_ms": round(statistics.pstdev(times), 3),
        "phase_p50_ms": {
            phase: round(statistics.median(row["phases_ms"][phase] for row in rows), 3)
            for phase in rows[0]["phases_ms"]
        },
        "min_ms": round(min(times), 3),
        "max_ms": round(max(times), 3),
    }


def run_local(trials, warmups=3):
    if type(trials) is not int or type(warmups) is not int or trials<1 or warmups<0 or 2*(trials+warmups)>100:
        raise ValueError('RDC testing hard cap: 100 total terminal trial operations')
    with tempfile.TemporaryDirectory(prefix="rdc-bench-") as temp:
        root = Path(temp)
        engine = Engine(Settings(
            state_dir=root / "state", roots=[root],
            browser_backend="disabled", approval_mode="trusted", allow_exec=True,
        ))
        rows = {"legacy": [], "fast_path": []}

        def finish(identifier, deadline):
            while time.monotonic() < deadline:
                state = engine.call("rdc_job_status", {"job_id": identifier})
                assert state["ok"], state
                if state["job"]["status"] in TERMINAL:
                    return state["job"]
                time.sleep(0.01)
            raise RuntimeError("Benchmark job exceeded deadline")

        try:
            rng = random.Random(42)
            warmup_methods = ["legacy", "fast_path"] * warmups
            measured_methods = ["legacy", "fast_path"] * trials
            rng.shuffle(warmup_methods)
            rng.shuffle(measured_methods)
            schedule = [(method, True) for method in warmup_methods]
            schedule += [(method, False) for method in measured_methods]
            counts = {"legacy": 0, "fast_path": 0}
            for method, warmup in schedule:
                counts[method] += 1
                arguments = {
                    "argv": COMMAND, "cwd": str(root),
                    "idempotency_key": method + "-" + str(counts[method]),
                }
                wall_start = time.time()
                start = time.perf_counter()
                if method == "legacy":
                    queued = engine.call("rdc_job_start", arguments)
                    first_call_ms = (time.perf_counter() - start) * 1000
                    assert queued["ok"], queued
                    first_call_completed = False
                    job = finish(queued["job"]["id"], time.monotonic() + 12)
                    output = engine.call("rdc_job_output", {"job_id": job["id"]})
                else:
                    response = engine.call("rdc_job_run", {
                        **arguments, "wait_ms": 3000, "output_limit": 16384,
                    })
                    first_call_ms = (time.perf_counter() - start) * 1000
                    assert response["ok"], response
                    first_call_completed = response["complete"]
                    job = response["job"]
                    output = response["output"]
                    if not first_call_completed:
                        job = finish(job["id"], time.monotonic() + 12)
                        output = engine.call("rdc_job_output", {"job_id": job["id"]})
                elapsed = (time.perf_counter() - start) * 1000
                wall_collected = time.time()
                assert output.get("ok", True), output
                text = output["text"]
                correct = job["status"] == "completed" and job["exit_code"] == 0 and text == EXPECTED
                row = {
                    "elapsed_ms": round(elapsed, 3),
                    "correct": correct,
                    "first_call_completed": first_call_completed,
                    "bytes": output["bytes_available"],
                    "state": job["status"],
                    "first_call_ms": round(first_call_ms, 3),
                    # Wall-clock phase samples can be affected by clock adjustment.
                    # worker_lifetime includes spawn, capture, and supervision; it
                    # is deliberately not labelled shell computation time.
                    "phases_ms": {
                        "admission": round((job["created_at"] - wall_start) * 1000, 3),
                        "detached_start": round((job["started_at"] - job["created_at"]) * 1000, 3),
                        "worker_lifetime": round((job["finished_at"] - job["started_at"]) * 1000, 3),
                        "result_collection": round((wall_collected - job["finished_at"]) * 1000, 3),
                    },
                }
                if not warmup:
                    rows[method].append(row)
                if not correct:
                    raise RuntimeError("Incorrect benchmark output for " + method)
        finally:
            engine.close()
    return {
        "method": "same Mac/direct-local Engine; 30+ runs recommended",
        "isolated_browser": True,
        "physical_keyboard_mouse_used": False,
        "trials_per_method": trials,
        "warmups_per_method": warmups,
        "python": sys.version,
        "platform": platform.platform(),
        "phase_clock": "worker wall timestamps; end-to-end elapsed uses monotonic perf_counter",
        "summary": {name: summarize(values) for name, values in rows.items()},
        "samples": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=30)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--output", type=Path)
    opts = parser.parse_args()
    if opts.trials < 3 or opts.trials > 1000:
        parser.error("trials must be 3 to 1000")
    if opts.warmups < 0 or opts.warmups > 100:
        parser.error("warmups must be 0 to 100")
    report = run_local(opts.trials, opts.warmups)
    payload = json.dumps(report, indent=2) + "\n"
    if opts.output:
        opts.output.parent.mkdir(parents=True, exist_ok=True)
        opts.output.write_text(payload)
        print(json.dumps(report["summary"], indent=2))
        print("RAW_RESULTS=" + str(opts.output))
    else:
        print(payload)
