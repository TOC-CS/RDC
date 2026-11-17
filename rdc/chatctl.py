"""RDC chat bus terminal interface. SYNTHETIC FIXTURES ONLY, never live enrollment.

python -m rdc.chatctl --synthetic-only --atlas-source PATH --db PATH init --session a --session b
Use the exact Atlas Bus v1 core and its transaction, retry, identity and TTL logic.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from .chat_interconnect import ChatClient, ChatError


MARKER_VERSION = "rdc.chat.synthetic.v1"


def parser():
    p = argparse.ArgumentParser(
        prog="python -m rdc.chatctl",
        description="Synthetic-only RDC/Atlas chat bus terminal interface. Never contacts real AI sessions.",
    )
    p.add_argument("--synthetic-only", action="store_true",
                   help="Required. Enable isolated synthetic fixture identities only.")
    p.add_argument("--atlas-source", type=Path,
                   help="Existing owner-authorized Atlas Build Bus source directory (read-only).")
    p.add_argument("--db", type=Path, help="Isolated sandbox SQLite database location.")
    sub = p.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Create an isolated synthetic session sandbox.")
    init.add_argument("--session", action="append", required=True)
    sub.add_parser("sessions", help="List synthetic fixtures, never consumer chat tabs.")
    send = sub.add_parser("send", help="Queue a message by stable idempotency key.")
    send.add_argument("--from", dest="source", required=True)
    send.add_argument("--to", required=True)
    send.add_argument("--key", required=True)
    send.add_argument("--text", required=True)
    claim = sub.add_parser("claim", help="Claim the next queued message for a fixture.")
    claim.add_argument("--as", dest="principal", required=True)
    claim.add_argument("--holder", required=True)
    fetch = sub.add_parser("fetch", help="Record explicit adapter fetch using the claim revision.")
    fetch.add_argument("--as", dest="principal", required=True)
    fetch.add_argument("--holder", required=True)
    fetch.add_argument("--message-id", required=True)
    fetch.add_argument("--revision", type=int, required=True)
    ack = sub.add_parser("ack", help="Acknowledge receipt at the enrolled synthetic destination.")
    ack.add_argument("--as", dest="principal", required=True)
    ack.add_argument("--message-id", required=True)
    confirm = sub.add_parser("confirm", help="Record synthetic verified action evidence.")
    confirm.add_argument("--as", dest="principal", required=True)
    confirm.add_argument("--message-id", required=True)
    confirm.add_argument("--evidence-sha256", required=True)
    reply = sub.add_parser("reply", help="Respond using the root correlation and causation IDs.")
    reply.add_argument("--as", dest="principal", required=True)
    reply.add_argument("--to", required=True)
    reply.add_argument("--key", required=True)
    reply.add_argument("--parent-id", required=True)
    reply.add_argument("--text", required=True)
    status = sub.add_parser("status", help="Inspect a message only as one of its participants.")
    status.add_argument("--as", dest="principal", required=True)
    status.add_argument("--message-id", required=True)
    return p


def _safe_db_path(value: Path) -> Path:
    raw = value.expanduser()
    # Resolving first hides a final-component symlink and could redirect
    # synthetic state to an unexpected database location.
    if raw.is_symlink():
        raise ChatError("Refusing a symlinked chat sandbox database path.")
    result = raw.resolve()
    if result.suffix not in {".sqlite", ".sqlite3", ".db"}:
        raise ChatError("A SQLite sandbox filename is required.")
    live_dirs = [
        Path.home() / "Library" / "Application Support" / "RDC",
        Path.home() / "Library" / "Application Support" / "AtlasBuildBus",
        Path.home() / ".local" / "state" / "rdc",
    ]
    if any(result == x.resolve() or x.resolve() in result.parents for x in live_dirs):
        raise ChatError("Refusing to access a live worker or Atlas runtime state directory.")
    if not result.parent.is_dir():
        raise ChatError("Sandbox parent directory does not exist.")
    if result.is_symlink():
        raise ChatError("Sandbox database cannot be a symlink.")
    return result


def _marker(db_path: Path) -> Path:
    return db_path.with_name(db_path.name + ".rdc-chat-fixture")


def _verify_marker(db_path: Path):
    marker = _marker(db_path)
    if not marker.is_file() or marker.is_symlink():
        raise ChatError("This file has no verified synthetic sandbox marker. Run init on a fresh path.")
    data = json.loads(marker.read_text(encoding="utf-8"))
    if data != {"format": MARKER_VERSION, "database": str(db_path)}:
        raise ChatError("Synthetic sandbox marker does not match the selected database.")


def _write_marker(db_path: Path):
    marker = _marker(db_path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    payload = json.dumps({"format": MARKER_VERSION, "database": str(db_path)}) + "\n"
    fd = os.open(marker, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _load_bus(source: Path):
    source = source.expanduser().resolve()
    if not (source / "atlasbus" / "contract.py").is_file() or not (source / "atlasbus" / "store.py").is_file():
        raise ChatError("An existing Atlas Bus v1 source tree is required.")
    sys.path.insert(0, str(source))
    from atlasbus.store import BusStore  # type: ignore[import-not-found]
    return BusStore


def run(argv=None):
    args = parser().parse_args(argv)
    if not args.synthetic_only:
        raise ChatError("Explicit --synthetic-only is required. Real chat enrollment is disabled.")
    if args.db is None or args.atlas_source is None:
        raise ChatError("An existing Atlas source and isolated --db location are required.")
    db_path = _safe_db_path(args.db)
    marker = _marker(db_path)
    if args.command == "init":
        if not args.session or len(args.session) > 20:
            raise ChatError("Specify one to twenty synthetic session fixtures.")
        if db_path.exists() and not marker.exists():
            raise ChatError("Refusing to modify an unmarked, potentially real database.")
        if marker.exists():
            _verify_marker(db_path)
    else:
        _verify_marker(db_path)

    BusStore = _load_bus(args.atlas_source)
    bus = BusStore(db_path, synthetic_mode=True)
    try:
        if args.command == "init":
            if not marker.exists():
                _write_marker(db_path)
            before = {
                row[0] for row in bus.connection.execute("SELECT session_id FROM synthetic_sessions")
            }
            for session in args.session:
                if session not in before:
                    bus.register_synthetic_session("rdc", session)
            result = {"sessions": sorted(
                row[0] for row in bus.connection.execute("SELECT session_id FROM synthetic_sessions")
            )}
        elif args.command == "sessions":
            result = {"sessions": [
                row[0] for row in bus.connection.execute(
                    "SELECT session_id FROM synthetic_sessions ORDER BY session_id"
                )
            ]}
        elif args.command == "send":
            client = ChatClient(bus, args.source)
            result = client.send(args.to, args.text, key=args.key)
        elif args.command == "claim":
            client = ChatClient(bus, args.principal)
            result = {"claim": client.claim(holder=args.holder)}
        elif args.command == "fetch":
            client = ChatClient(bus, args.principal)
            row = bus.get_message(args.message_id)
            claim = {
                "message_id": args.message_id,
                "revision": args.revision,
                "envelope": json.loads(row["content_json"]),
            }
            result = {"receipt": client.mark_fetched(claim, holder=args.holder)}
        elif args.command == "ack":
            client = ChatClient(bus, args.principal)
            result = {"receipt": client.ack(args.message_id)}
        elif args.command == "confirm":
            client = ChatClient(bus, args.principal)
            result = {"receipt": client.confirm(args.message_id, evidence_digest=args.evidence_sha256)}
        elif args.command == "reply":
            client = ChatClient(bus, args.principal)
            result = client.send(args.to, args.text, key=args.key, reply_to=args.parent_id)
        elif args.command == "status":
            client = ChatClient(bus, args.principal)
            result = {"message": client.status(args.message_id)}
        else:
            raise ChatError("Unknown command.")
        return {"ok": True, "scope": "synthetic_fixture_only", **result}
    finally:
        bus.close()


def main(argv=None):
    try:
        print(json.dumps(run(argv), ensure_ascii=False))
        return 0
    except Exception as exc:
        # A failed request cannot expose payloads, account details or source
        # paths. Keep exact known Atlas error codes for local diagnosis.
        code = getattr(exc, "code", None)
        if isinstance(exc, ChatError):
            code = "ACCESS_DENIED" if "no access to this message" in str(exc).lower() else "INVALID_REQUEST"
        if not isinstance(code, str):
            value = str(exc).split(":")[0]
            code = value if value.isupper() and value.replace("_", "").isalpha() else "OPERATION_DENIED"
        print(json.dumps({"ok": False, "error": code, "scope": "synthetic_fixture_only"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
