"""Isolated local Engine benchmark for one-call search-to-source behavior.

This is never an RDC cloud/ChatGPT latency measurement. It checks equal
text/hash output while comparing one API request with two.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import tempfile
import time
import sys

from rdc.config import Settings
from rdc.engine import Engine


def summarize(samples):
    ranked = sorted(samples)
    return {
        "count":len(ranked),
        "p50_ms":round(statistics.median(ranked),3),
        "p95_ms":round(ranked[int(0.95 * (len(ranked)-1))],3),
        "min_ms":round(ranked[0],3),
        "max_ms":round(ranked[-1],3),
    }


def compare(rounds=30, warmup=5):
    if type(rounds) is not int or type(warmup) is not int or rounds<1 or warmup<0 or 2*(rounds+warmup)>100:
        raise ValueError('RDC testing hard cap: 100 total benchmark trials')
    samples = {"one_call":[], "two_calls":[]}
    with tempfile.TemporaryDirectory(prefix="rdc-auto-read-bench-") as td:
        home = Path(td)
        project = home / "allowed" / "project"
        project.mkdir(parents=True)
        selected = project / "00_source.py"
        selected.write_text("SEARCH_ANCHOR = 1\n" + "x = 123\n" * 100, encoding="utf-8")
        for i in range(50):
            (project / f"{i+1:03d}_file.py").write_text(f"value = {i}\n", encoding="utf-8")
        expected = selected.read_text()
        digest = hashlib.sha256(selected.read_bytes()).hexdigest()
        engine = Engine(Settings(
            state_dir=home/"state", roots=[home/"allowed"],
            allow_exec=False, browser_backend="disabled", approval_mode="review"))
        try:
            def perform(kind):
                t0 = time.perf_counter_ns()
                if kind == "one_call":
                    response = engine.call("rdc_code_context", {
                        "path":str(project), "query":"SEARCH_ANCHOR", "read_matches":1})
                    assert response["ok"] and response["auto_read_count"] == 1, response
                    source = response["reads"][0]
                else:
                    response = engine.call("rdc_code_context", {
                        "path":str(project), "query":"SEARCH_ANCHOR"})
                    assert response["ok"] and response["search"]["matches"], response
                    filename = response["search"]["matches"][0]["file_path"]
                    source = engine.call("rdc_file_read", {
                        "file_path":filename, "limit":16384})
                elapsed_ms = (time.perf_counter_ns() - t0)/1e6
                assert source["ok"] and source["text"] == expected, source
                assert source["sha256"] == digest and not source["truncated"], source
                return elapsed_ms
            for _ in range(warmup):
                perform("one_call")
                perform("two_calls")
            for i in range(rounds):
                order = ("one_call","two_calls") if i%2 == 0 else ("two_calls","one_call")
                for kind in order:
                    samples[kind].append(perform(kind))
        finally:
            engine.close()
    return {
        "scope":"local Python Engine only; no cloud/gateway or ChatGPT host timing",
        "utc":datetime.now(timezone.utc).isoformat(),
        "rounds":rounds,"warmups":warmup,
        "source_files":51,
        "result_equivalence_verified":True,
        "api_call_count_per_round":{"one_call":1,"two_calls":2},
        "summary":{name:summarize(values) for name,values in samples.items()},
        "samples_ms":samples
    }


if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("Usage: python benchmarks/search_to_source_compare.py OUTPUT.json")
    report=compare()
    target=Path(sys.argv[1])
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="samples_ms"}, indent=2))
