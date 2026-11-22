#!/usr/bin/env python3
"""Install an optional RDC direct-local Codex MCP alias, without copying secrets.

Dry-run by default. The worker's existing private agent-token remains in its
original state directory and is read only by the normal RDC client at startup.
This script never authenticates to the OpenAI Platform or makes model calls.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tomllib
from urllib.parse import urlsplit


_ALIAS = re.compile(r'[a-z][a-z0-9-]{0,63}\Z')


def _require_owner_private(path: Path) -> None:
    try:
        info = path.lstat()
        if path.is_symlink() or not stat.S_ISREG(info.st_mode):
            raise ValueError
        if os.name == 'posix' and (
            info.st_uid != os.getuid() or (stat.S_IMODE(info.st_mode) & 0o077)
        ):
            raise ValueError
    except (OSError, ValueError):
        raise ValueError(
            'RDC local worker credentials/configuration must be original private regular files.'
        ) from None


def _valid_local_worker_url(value: str) -> bool:
    if not isinstance(value, str) or len(value) > 2048:
        return False
    try:
        parts = urlsplit(value)
        if (
            parts.scheme != 'http' or parts.hostname != '127.0.0.1'
            or parts.port is None or not 1 <= parts.port <= 65535
            or parts.path != '/mcp' or parts.query or parts.fragment
            or parts.username is not None or parts.password is not None
        ):
            return False
        return value == f'http://127.0.0.1:{parts.port}/mcp'
    except (ValueError, TypeError):
        return False


def build_local_codex_registration(
    *, state_dir, worker_url: str, alias: str,
    python, source_root,
) -> dict:
    """Return a literal, reversible Codex CLI argv with no credential bytes."""
    state = Path(state_dir).expanduser().absolute()
    interpreter = Path(python).expanduser().absolute()
    source = Path(source_root).expanduser().absolute()
    if not isinstance(alias, str) or not _ALIAS.fullmatch(alias):
        raise ValueError('Invalid Codex MCP alias.')
    if not _valid_local_worker_url(worker_url):
        raise ValueError('RDC direct MCP URL must use the exact loopback /mcp endpoint.')
    if state.is_symlink() or not state.is_dir():
        raise ValueError('RDC local worker state must be a real directory.')
    _require_owner_private(state / 'agent-token')
    _require_owner_private(state / 'config.json')
    try:
        settings = json.loads((state / 'config.json').read_text(encoding='utf-8'))
        if (not isinstance(settings, dict)
                or settings.get('state_dir') != str(state)
                or not isinstance(settings.get('roots'), list)
                or not settings['roots']):
            raise ValueError
    except (OSError, ValueError, UnicodeError):
        raise ValueError(
            'RDC local worker configuration does not match the selected state.'
        ) from None
    if (not interpreter.is_file() or not os.access(interpreter, os.X_OK)
            or source.is_symlink()
            or not (source / 'rdc' / 'cli.py').is_file()):
        raise ValueError('RDC Python executable or source module is unavailable.')

    return {
        'alias': alias,
        'worker_url': worker_url,
        'argv': [
            'codex', 'mcp', 'add', '--env', 'PYTHONPATH=' + str(source),
            alias, '--', str(interpreter), '-B', '-m', 'rdc', 'connect',
            '--url', worker_url, '--state-dir', str(state), '--timeout', '15',
        ],
        'secret_contents_read': False,
        'openai_api_calls_required': 0,
    }


def install_if_absent(plan: dict) -> str:
    """Register one new alias only, refusing to overwrite an existing entry."""
    if not shutil.which('codex'):
        raise RuntimeError('Codex CLI must already be installed to register this optional alias.')

    check = subprocess.run(
        ['codex', 'mcp', 'get', plan['alias']],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
        check=False)
    if check.returncode == 0:
        raise RuntimeError(
            'The Codex MCP alias already exists. Inspect it; this installer never overwrites it.'
        )
    subprocess.run(plan['argv'], check=True, stdout=subprocess.PIPE,
                   stderr=subprocess.PIPE, text=True, timeout=20)

    config = Path.home() / '.codex' / 'config.toml'
    try:
        aliases = tomllib.loads(config.read_text())['mcp_servers']
        entry = aliases[plan['alias']]
        expected = plan['argv']
        interpreter_index = expected.index('--')
        if (entry.get('command') != expected[interpreter_index + 1]
                or entry.get('args') != expected[interpreter_index + 2:]
                or entry.get('env', {}).get('PYTHONPATH') != expected[4].split('=', 1)[1]):
            raise ValueError
    except (KeyError, ValueError, OSError):
        raise RuntimeError(
            'Codex registration returned without an exact configuration readback.'
        ) from None
    return 'registered'


def main() -> int:
    cli = argparse.ArgumentParser(
        description='Add an authorized local RDC worker to Codex without copying any credentials.')
    cli.add_argument('--state-dir', type=Path, required=True)
    cli.add_argument('--worker-url', default='http://127.0.0.1:8765/mcp')
    cli.add_argument('--alias', default='rdc2-fast-local')
    cli.add_argument('--python', type=Path, default=Path(sys.executable))
    cli.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parent.parent)
    cli.add_argument('--apply', action='store_true',
                     help='Register a new Codex MCP alias; dry-run is the default.')
    args = cli.parse_args()
    try:
        plan = build_local_codex_registration(
            state_dir=args.state_dir, worker_url=args.worker_url,
            alias=args.alias, python=args.python, source_root=args.source_root)
        outcome = install_if_absent(plan) if args.apply else 'dry_run'
    except (ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}))
        return 2
    print(json.dumps({
        'ok': True, 'alias': plan['alias'], 'worker_url': plan['worker_url'],
        'result': outcome, 'existing_aliases_preserved': True,
        'credential_copy': False, 'paid_api_calls': 0,
    }, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
