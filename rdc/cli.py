"""Owner initialization and local process entry points."""
from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import sys
import webbrowser


def default_state_dir():
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'RDC'
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'RDC'
    return Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local' / 'state'))) / 'rdc'


def private_state(path):
    path = Path(path).expanduser().absolute()
    if path.is_symlink():
        raise ValueError('state directory must not be a symlink')
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != 'nt':
        if path.stat().st_uid != os.getuid():
            raise ValueError('state directory must belong to the current account')
        os.chmod(path, 0o700)
    return path


def write_secret(path):
    token = secrets.token_urlsafe(48)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(token + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    return token


def read_secret(path):
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'r') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('token must be a regular file')
        if os.name != 'nt' and (info.st_uid != os.getuid() or info.st_mode & 0o077):
            raise ValueError('token must be private to the current account (chmod 600)')
        token = stream.read(1025).strip()
    if len(token) < 40 or len(token) > 1024:
        raise ValueError('invalid token file; initialize RDC with private token files')
    return token


def parser():
    command = argparse.ArgumentParser(prog='rdc', description='Independent local agent workspaces (alpha).')
    sub = command.add_subparsers(dest='command', required=True)
    for name in ('init', 'stdio', 'connect', 'relay', 'serve', 'doctor', 'owner-token', 'diagnostics'):
        action = sub.add_parser(name)
        action.add_argument('--state-dir', type=Path, default=default_state_dir())
        if name == 'diagnostics':
            action.add_argument('--limit', type=int, choices=range(1,51), default=50)
        if name == 'init':
            action.add_argument('--root', type=Path, action='append', help='Allowed workspace root, repeatable (default: current directory)')
            action.add_argument('--allow-exec', action='store_true', help='Grant shell execution as this OS account')
            action.add_argument('--access-mode', choices=['workspace', 'full-host'], default='workspace')
            action.add_argument('--approval-mode', choices=['review', 'trusted'], default='review')
            action.add_argument('--desktop-mode', choices=['disabled', 'shared', 'isolated'], default='disabled')
            action.add_argument('--browser-backend', choices=['playwright', 'webdriver', 'disabled'], default='playwright')
            action.add_argument('--webdriver-url')
            action.add_argument('--webdriver-capabilities', type=json.loads, help='JSON WebDriver capabilities')
            action.add_argument('--adb-serial')
            action.add_argument('--allowed-origin', action='append', default=[])
        if name == 'connect':
            action.add_argument('--url', default='http://127.0.0.1:8765/mcp', help='Running worker MCP endpoint: loopback HTTP or HTTPS')
            action.add_argument('--timeout', type=float, default=60, help='Upstream request timeout in seconds; actions are never retried')
        if name == 'relay':
            action.add_argument('--config', type=Path, required=True,
                                help='Private gateway pairing JSON file; secrets remain on this device')
        if name == 'serve':
            action.add_argument('--host', choices=['127.0.0.1', 'localhost', '::1'], default='127.0.0.1', help='Loopback listener; use an authenticated TLS gateway for remote access')
            action.add_argument('--port', type=int, default=8765)
            action.add_argument('--open', action='store_true', help='Open the local owner dashboard')
    return command


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        from .config import Settings
        state = Path(args.state_dir).expanduser().absolute()
        if args.command == 'diagnostics':
            from .diagnostics import Diagnostics
            print(json.dumps(Diagnostics.read_status(state,args.limit), indent=2))
            return 0
        if args.command == 'init':
            state = private_state(state)
            if any((state / name).exists() or (state / name).is_symlink() for name in ('config.json', 'agent-token', 'owner-token')):
                raise ValueError('RDC is already initialized or contains token files; preserve or move the existing state before initializing')
            settings = Settings(state_dir=state, roots=args.root or [Path.cwd()],
                                allow_exec=args.allow_exec, access_mode=args.access_mode,
                                approval_mode=args.approval_mode, desktop_mode=args.desktop_mode,
                                browser_backend=args.browser_backend, webdriver_url=args.webdriver_url,
                                webdriver_capabilities=args.webdriver_capabilities, adb_serial=args.adb_serial,
                                allowed_origins=args.allowed_origin)
            write_secret(state / 'agent-token')
            write_secret(state / 'owner-token')
            settings.save(state / 'config.json')
            print(f'Initialized RDC at {state}. Shell: {settings.allow_exec}; approvals: {settings.approval_mode}; desktop: {settings.desktop_mode}.')
            print('Run rdc serve, connect your AI client, and ask it to open the RDC preview. Owner administration is available locally.')
            return 0
        if args.command == 'owner-token':
            print(read_secret(state / 'owner-token'))
            return 0
        if args.command == 'connect':
            import anyio
            from .proxy import run_connect, validate_endpoint
            validate_endpoint(args.url)
            anyio.run(run_connect, args.url, read_secret(state / 'agent-token'), args.timeout)
            return 0
        if args.command == 'relay':
            import anyio
            from .relay import run_relay
            anyio.run(run_relay, args.config, state)
            return 0
        settings = Settings.load(state / 'config.json')
        if settings.state_dir != state:
            raise ValueError('config state_dir differs from selected state directory')
        if args.command == 'doctor':
            modules = ('mcp', 'uvicorn', 'playwright', 'selenium', 'pyautogui')
            report = {'python': sys.version.split()[0], 'platform': sys.platform,
                      'config': settings.public(),
                      'modules': {name: importlib.util.find_spec(name) is not None for name in modules},
                      'adb': shutil.which('adb'),
                      'token_files_private': bool(read_secret(state / 'owner-token') and read_secret(state / 'agent-token')),
                      'status': 'local dependency check only; devices and client integrations require real tests'}
            try:
                report['mcp_sdk_version'] = importlib.metadata.version('mcp')
            except importlib.metadata.PackageNotFoundError:
                report['mcp_sdk_version'] = None
            print(json.dumps(report, indent=2))
            return 0
        from .engine import Engine
        from .server import create_app, run_stdio
        engine = Engine(settings)
        if args.command == 'stdio':
            import anyio
            anyio.run(run_stdio, engine)
        elif args.command == 'serve':
            if not 1 <= args.port <= 65535:
                raise ValueError('port must be between 1 and 65535')
            import uvicorn
            app = create_app(engine, read_secret(state / 'agent-token'), read_secret(state / 'owner-token'))
            host = f'[{args.host}]' if ':' in args.host else args.host
            url = f'http://{host}:{args.port}/'
            if args.open:
                # The public shell can load before the listener; it retries on connection.
                import threading
                timer = threading.Timer(1.0, webbrowser.open, args=(url,))
                timer.daemon = True
                timer.start()
            print(f'Owner dashboard: {url}', file=sys.stderr)
            uvicorn.run(app, host=args.host, port=args.port, proxy_headers=False)
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f'rdc: {exc}', file=sys.stderr)
        return 1
