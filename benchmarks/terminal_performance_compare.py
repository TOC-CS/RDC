"""Compare terminal sources in disposable copies, without touching live workers.

Only jobs.py and worker.py are restored from --baseline-ref for the baseline.
All other code and the instrumented benchmark are identical for both variants.
Rounds alternate variant order; each child creates a fresh temporary profile.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from terminal_fast_path import summarize


def compare(baseline_ref, rounds, trials, warmups):
    repo = Path(__file__).resolve().parent.parent
    rows = {variant: {"legacy": [], "fast_path": []} for variant in ("baseline", "candidate")}
    reports = []
    manifests = {}
    with tempfile.TemporaryDirectory(prefix="rdc-terminal-compare-") as temp:
        roots = {}
        for variant in rows:
            root = Path(temp) / variant
            roots[variant] = root
            root.mkdir()
            shutil.copytree(repo / "rdc", root / "rdc", ignore=shutil.ignore_patterns("__pycache__"))
            (root / "benchmarks").mkdir()
            shutil.copy2(repo / "benchmarks/terminal_fast_path.py", root / "benchmarks/terminal_fast_path.py")
            if variant == "baseline":
                for name in ("jobs.py", "worker.py"):
                    content = subprocess.check_output(["git", "show", baseline_ref + ":rdc/" + name], cwd=repo)
                    (root / "rdc" / name).write_bytes(content)
            manifests[variant] = {
                str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(root.rglob("*.py"))
            }
        for round_number in range(rounds):
            order = ("baseline", "candidate") if round_number % 2 == 0 else ("candidate", "baseline")
            for variant in order:
                root = roots[variant]
                payload = subprocess.check_output([
                    sys.executable, str(root / "benchmarks/terminal_fast_path.py"),
                    "--trials", str(trials), "--warmups", str(warmups),
                ], cwd=root, text=True)
                report = json.loads(payload)
                reports.append({"round": round_number + 1, "variant": variant, "report": report})
                for method, samples in report["samples"].items():
                    rows[variant][method].extend(samples)
                print(f"Finished round {round_number + 1}/{rounds}: {variant}", file=sys.stderr, flush=True)
    return {
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_ref": baseline_ref,
        "candidate_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
        "comparison_scope": "Only jobs.py and worker.py differ; no deployed worker, network/provider, GUI, or BandMates interaction",
        "rounds": rounds, "trials_per_method_per_variant": trials * rounds,
        "warmups_per_method_per_variant": warmups * rounds,
        "summary": {variant: {method: summarize(samples) for method, samples in methods.items()}
                    for variant, methods in rows.items()},
        "source_sha256": manifests,
        "round_reports": reports,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-ref", default="8a4a86e788be9b91eb8143d4d475c10e56524842")
    parser.add_argument("--rounds", type=int, default=4)
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 2 <= args.rounds <= 20 or args.rounds % 2:
        parser.error("rounds must be an even number from 2 to 20 for balanced ordering")
    if not 3 <= args.trials <= 1000 or not 0 <= args.warmups <= 100:
        parser.error("trials must be 3 to 1000 and warmups 0 to 100")
    report = compare(args.baseline_ref, args.rounds, args.trials, args.warmups)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"], indent=2))
    print("RAW_RESULTS=" + str(args.output))
