"""Private RDC V2 Secure MCP Tunnel readiness, without reading secrets or dialing.

This is a fail-closed, read-only staging check. It NEVER starts a gateway,
downloads a binary, activates a tunnel, or changes the connected RDC worker.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
from urllib.parse import urlsplit

_REQUIRED = frozenset({
    "tunnel_id", "mcp_server_url", "runtime_key_file", "gateway_client_token_file",
})
_TUNNEL_RE = re.compile(r"tunnel_[A-Za-z0-9]{16,96}\Z")


def _private_file(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    path = Path(value)
    if not path.is_absolute():
        return False
    try:
        # macOS /var and /tmp are OS aliases, so a symlink above a private
        # fixture does not mean its final credential file is a symlink.
        if path.is_symlink():
            return False
        info = path.lstat()
        return (stat.S_ISREG(info.st_mode)
                and (os.name != 'posix' or
                     (info.st_uid == os.getuid() and (info.st_mode & 0o077) == 0)))
    except (OSError, ValueError):
        return False


def _private_loopback_mcp_url(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = urlsplit(value)
        return (parsed.scheme == 'http'
                and parsed.hostname == '127.0.0.1'
                and parsed.port is not None
                and 1 <= parsed.port <= 65535
                and parsed.path == '/v2/mcp'
                and not parsed.username and not parsed.password
                and not parsed.query and not parsed.fragment)
    except (ValueError, TypeError):
        return False


def _executable(value: str | None) -> bool:
    if not isinstance(value, str) or not value:
        return False
    resolved = shutil.which(value)
    if resolved is None:
        return False
    try:
        file = Path(resolved)
        return file.is_file() and os.access(file, os.X_OK)
    except OSError:
        return False


def inspect_tunnel_config(config: dict, *, binary: str | None = None) -> dict:
    if not isinstance(config, dict):
        config = {}
    checks = {
        'schema': set(config) == _REQUIRED,
        'tunnel_identity': isinstance(config.get('tunnel_id'), str) and
                           _TUNNEL_RE.fullmatch(config['tunnel_id']) is not None,
        'loopback_mcp_endpoint': _private_loopback_mcp_url(
            config.get('mcp_server_url')),
        'runtime_key_private': _private_file(config.get('runtime_key_file')),
        'gateway_client_key_private': _private_file(
            config.get('gateway_client_token_file')),
        'distinct_credentials': (
            isinstance(config.get('runtime_key_file'), str)
            and isinstance(config.get('gateway_client_token_file'), str)
            and config.get('runtime_key_file') != config.get('gateway_client_token_file')),
        'tunnel_client_installed': _executable(binary or 'tunnel-client'),
    }
    # Values, keys, paths and tokens never leave the owner machine in this
    # report. A passing filesystem check alone cannot prove key permissions
    # or ChatGPT workspace roles, which require independent live verification.
    blockers = [name for name, passed in checks.items() if not passed]
    return {'transport': 'owner-private-outbound-tunnel',
            'ready': not blockers, 'blockers': blockers, 'checks': checks,
            'requires_owner_platform_and_chatgpt_verification': True}


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Read-only RDC V2 private MCP tunnel readiness. No secrets are read.')
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--binary', default='tunnel-client')
    args = parser.parse_args()
    # Preserve the supplied leaf path so a symlink cannot be hidden by resolve().
    if not _private_file(str(args.config.expanduser().absolute())):
        print(json.dumps({'ready': False, 'blockers': ['private_config_required']}))
        return 2
    try:
        config = json.loads(args.config.read_text(encoding='utf-8'))
    except (ValueError, OSError, UnicodeError):
        print(json.dumps({'ready': False, 'blockers': ['invalid_config']}))
        return 2
    outcome = inspect_tunnel_config(config, binary=args.binary)
    print(json.dumps(outcome, indent=2))
    return 0 if outcome['ready'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
