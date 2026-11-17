"""Local synthetic source-context performance harness for RDC coding agents.

Run from this repository root:
  python -m benchmarks.coding_source_search

This measures the Python RDC Engine only. ChatGPT, cloud/D1, Desktop Commander,
host network and any live owner project are outside the measurement.
"""
from pathlib import Path
import json
import statistics
import tempfile
import time

from rdc.config import Settings
from rdc.engine import Engine

MARKER = "RDC_SOURCE_CONTEXT_PERF_MARKER"


def percentile(values, q):
    values = sorted(values)
    offset = (len(values) - 1) * q
    lower = int(offset)
    upper = min(lower + 1, len(values) - 1)
    return round(values[lower] + (values[upper] - values[lower]) * (offset - lower), 3)


def summarize(samples):
    return {
        "runs": len(samples),
        "p50_ms": round(statistics.median(samples), 3),
        "p95_ms": percentile(samples, 0.95),
        "p99_ms": percentile(samples, 0.99),
        "max_ms": round(max(samples), 3),
    }


def run(trials=30, warmups=3):
    if not 5 <= trials <= 100 or not 0 <= warmups <= 15:
        raise ValueError("Benchmark requires 5-100 trials and 0-15 warmups")
    with tempfile.TemporaryDirectory(prefix="rdc-coding-search-perf-") as tmp:
        home = Path(tmp)
        root = home / "allowed"
        project = root / "project"
        source = project / "src"
        dependency = project / "node_modules" / "subtree"
        git = project / ".git" / "objects"
        source.mkdir(parents=True)
        dependency.mkdir(parents=True)
        git.mkdir(parents=True)
        matching = source / "main.py"
        matching.write_text("def relevant():\n    return '" + MARKER + "'\n", encoding="utf-8")
        for n in range(9):
            (source / f"module_{n}.py").write_text(f"def f_{n}(): return {n}\n", encoding="utf-8")
        for n in range(600):
            (dependency / f"library_{n}.js").write_text(f"export const lib_{n} = {n};\n", encoding="utf-8")
        for n in range(50):
            (git / f"blob_{n}").write_bytes(f"synthetic git contents {n}\n".encode())
        engine = Engine(Settings(state_dir=home / "worker-private", roots=[root],
                                 allow_exec=False, approval_mode="review",
                                 browser_backend="disabled"))
        results = {"source": [], "all": []}
        scans = {"source": [], "all": []}
        try:
            for i in range(trials + warmups):
                modes = ("source", "all") if i % 2 == 0 else ("all", "source")
                for mode in modes:
                    t = time.perf_counter()
                    response = engine.call("rdc_code_context", {
                        "path": str(project), "query": MARKER,
                        "file_paths": ["src/main.py"],
                        "search_mode": mode, "max_files": 1000,
                        "search_limit": 10})
                    elapsed_ms = (time.perf_counter() - t) * 1000
                    assert response["ok"], response
                    assert response["reads"][0]["ok"], response
                    assert response["reads"][0]["text"] == matching.read_text()
                    assert len(response["search"]["matches"]) == 1, response["search"]
                    assert not response["search"]["truncated"], response["search"]
                    if i >= warmups:
                        results[mode].append(elapsed_ms)
                        scans[mode].append(response["search"]["files_scanned"])
        finally:
            engine.close()
    source_summary, full_summary = summarize(results["source"]), summarize(results["all"])
    return {"scope":"local synthetic RDC Engine only",
            "trials_per_mode":trials,"warmups":warmups,
            "files":{"source":10,"generated_or_git":650},
            "results":{"source":{**source_summary,"files_scanned":scans["source"][0],"correct":trials},
                       "all":{**full_summary,"files_scanned":scans["all"][0],"correct":trials}},
            "p50_speedup_ratio_all_over_source":
                round(full_summary["p50_ms"]/max(source_summary["p50_ms"], 0.001),2),
            "limitations":["No live ChatGPT tool overhead","No Desktop Commander execution",
                           "Search modes deliberately vary their included directories"]}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
