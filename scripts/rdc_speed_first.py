#!/usr/bin/env python3
"""Direct, single-owner RDC speed verification. Never starts Atlas Bus or deploys.

Commands:
  status: Show exact source revision and local speed-work prerequisites.
  test:   Run one preflighted, combined <=100 case regression campaign.
  gate:   Fail closed without an authenticated real ChatGPT-connected receipt.

This utility deliberately has no worker/bus scheduler, background process,
cloud credential dependency, retry of mutations, or release mechanism.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
GOVERNOR = ROOT / 'scripts' / 'rdc_test_budget.py'
ACCEPTANCE = ROOT / 'benchmarks' / 'rdc_speed_acceptance.mjs'
REPORT = ROOT / 'test-results' / 'rdc-speed-first-local100.json'
RETIRED_MODULES = (
    'chatctl.py', 'chat_interconnect.py', 'chat_rooms.py',
    'chat_cross_project.py', 'chat_project_messages.py',
    'chat_project_actions.py', 'chat_surface.py',
    'chat_continuity.py', 'chatgpt_identity.py',
)


def command(argv: list[str], *, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=ROOT, check=False, text=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None)


def source_status() -> dict:
    head = command(['git', 'rev-parse', 'HEAD'], capture=True)
    branch = command(['git', 'branch', '--show-current'], capture=True)
    dirty = command(['git', 'status', '--porcelain'], capture=True)
    if any(item.returncode for item in (head, branch, dirty)):
        raise RuntimeError('RDC source Git identity is unavailable')
    stale = [name for name in RETIRED_MODULES if (ROOT / 'rdc' / name).exists()]
    if (ROOT / 'skills' / 'rdc-communications').exists():
        stale.append('skills/rdc-communications')
    return {
        'workflow': 'direct-single-owner-speed-first',
        'atlas_bus': 'disabled', 'swarm_handoff': 'disabled',
        'source_branch': branch.stdout.strip(),
        'source_revision': head.stdout.strip(),
        'working_tree_clean': not dirty.stdout.strip(),
        'retired_modules_still_present': stale,
        'campaign_max_cases': 100,
        'live_speed_required': True,
        'deployment_authorized': False,
    }



def test_python() -> str:
    """Prefer a ready RDC virtualenv; never install dependencies in a live worker."""
    candidates = [sys.executable,
                  str(ROOT / '.venv' / 'bin' / 'python'),
                  str(ROOT.parent.parent / 'rdc' / '.venv' / 'bin' / 'python')]
    for executable in dict.fromkeys(candidates):
        if not Path(executable).is_file():
            continue
        check = command([executable, '-c',
                         'import anyio, httpx, jsonschema, rdc.relay_v2'],
                        capture=True)
        if check.returncode == 0:
            return executable
    raise RuntimeError('No RDC testing Python has all required dependencies. '
                       'Install source test dependencies in an isolated env, '
                       'never in the live worker.')


def preflight(python: str) -> bool:
    result = command([python, str(GOVERNOR),
                      '--campaign', 'local-core', '--dry-run'], capture=True)
    if result.returncode:
        print(result.stderr, file=sys.stderr)
        return False
    data = json.loads(result.stdout)
    if data.get('max_cases') != 100 or data.get('planned_total', 101) > 100:
        print('RDC 100-check budget preflight failed closed.', file=sys.stderr)
        return False
    print(f"RDC regression preflight: {data['planned_total']}/100 checks")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description='Atlas-free direct RDC speed workflow')
    parser.add_argument('action', choices=['status', 'test', 'gate'])
    parser.add_argument('--receipt', type=Path,
                        help='Independently obtained real live acceptance receipt for gate')
    args = parser.parse_args()
    try:
        status = source_status()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.action == 'status':
        print(json.dumps(status, indent=2))
        return 1 if status['retired_modules_still_present'] else 0
    if status['retired_modules_still_present']:
        print('Atlas Bus cleanup incomplete; refusing a new RDC campaign.', file=sys.stderr)
        return 2
    if args.action == 'test':
        try:
            python = test_python()
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        if not preflight(python):
            return 2
        print(f'RDC test Python: {python}', flush=True)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        return command([python, str(GOVERNOR), '--campaign', 'local-core',
                        '--report', str(REPORT)]).returncode
    if args.action == 'gate':
        # No receipt means FAIL CLOSED; stale localhost measurements never count.
        args_list = ['node', str(ACCEPTANCE)]
        if args.receipt:
            if not args.receipt.is_file():
                print('Live acceptance receipt not found.', file=sys.stderr)
                return 2
            args_list.append(str(args.receipt.resolve()))
        return command(args_list).returncode
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
