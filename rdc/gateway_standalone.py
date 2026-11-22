"""Independent single-operator RDC V2 gateway, with no Sites or Cloudflare runtime.

One gateway instance belongs to one operator and one paired device. It binds to
loopback; a separately authenticated TLS reverse proxy is required for remote
clients. Public multi-user OAuth/OIDC is NOT implemented by this single-operator
gateway. No publisher workstation or ChatGPT subscription is required.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import hashlib
import hmac
import importlib
import json
import os
import re
from pathlib import Path
import secrets
import sqlite3
import stat
import time
from urllib.parse import urlparse
from uuid import UUID, uuid4

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

MAX_REQUEST = 1_048_576
MAX_FRAME = 1_572_864
MAX_BULK = 12 * 1024 * 1024
MAX_BODY_BULK = 16 * 1024 * 1024
MAX_QUEUE = 64
ONLINE_MS = 35_000
UNKNOWN_MS = 120_000

def now_ms():
    return int(time.time() * 1000)

def sha256(raw):
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def fail(code, status=400):
    return JSONResponse({"ok": False, "error": {"code": code}}, status_code=status,
                        headers={"Cache-Control": "no-store"})

def result(value, status=200):
    return JSONResponse(value, status_code=status, headers={"Cache-Control": "no-store"})

async def bounded_body(request: Request, limit: int):
    declared=request.headers.get("content-length")
    if declared is not None:
        if not declared.isdecimal():
            raise ValueError("invalid_request")
        if int(declared)>limit:
            raise ValueError("payload_too_large")
    total=0
    parts=[]
    async for chunk in request.stream():
        total+=len(chunk)
        if total>limit:
            raise ValueError("payload_too_large")
        parts.append(chunk)
    return b"".join(parts)

def read_secret(path):
    path = Path(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags), "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or (
                os.name == "posix" and (info.st_uid != os.getuid() or info.st_mode & 0o077)):
            raise ValueError("gateway token must be an owner-only regular file")
        value = handle.read(1025).decode("ascii").strip()
    if not 40 <= len(value) <= 1024:
        raise ValueError("gateway token length invalid")
    return value

def initialize(directory, device_id=None):
    if device_id is None:
        device_id = str(uuid4())
    else:
        try:
            if not isinstance(device_id, str) or str(UUID(device_id)) != device_id:
                raise ValueError
        except (ValueError, AttributeError, TypeError):
            raise ValueError("paired device ID must be a canonical UUID") from None
    root = Path(directory).expanduser().absolute()
    if root.is_symlink() or root.exists():
        raise ValueError("gateway state already exists; refusing to overwrite credentials or journal")
    root.mkdir(mode=0o700, parents=True)
    for name in ("client-token", "device-token"):
        fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                     getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(secrets.token_urlsafe(48) + "\n")
    (root / "device-id").write_text(device_id + "\n")
    os.chmod(root / "device-id", 0o600)
    return root

@dataclass(eq=False)
class DeviceSocket:
    ws: WebSocket
    pending: bool = False
    active: str | None = None

class StandaloneGateway:
    """Single-owner journal. SQL commits precede every operation notification."""

    def __init__(self, directory, *, catalog=None, clock=now_ms):
        self.root = Path(directory).expanduser().absolute()
        # Runtime readback is the digest of the actual imported gateway source,
        # rather than a caller-supplied release string. Calculate once at
        # startup so normal operation and WebSocket hot paths stay unchanged.
        self.gateway_source_sha256 = hashlib.sha256(
            Path(__file__).resolve().read_bytes()).hexdigest()
        self.client_token = read_secret(self.root / "client-token")
        self.device_token = read_secret(self.root / "device-token")
        self.device_id = (self.root / "device-id").read_text().strip()
        if not self.device_id or len(self.device_id) > 100:
            raise ValueError("invalid gateway device ID")
        self.clock = clock
        self.root.joinpath("results").mkdir(mode=0o700, exist_ok=True)
        self.db = sqlite3.connect(self.root / "journal.sqlite3",
                                  isolation_level=None, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=3000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS operations (
            id TEXT PRIMARY KEY, request_key TEXT NOT NULL UNIQUE,
            request_digest TEXT NOT NULL, request_json TEXT,
            tool TEXT NOT NULL, mutating INTEGER NOT NULL,
            state TEXT NOT NULL, created_ms INTEGER NOT NULL,
            expires_ms INTEGER NOT NULL, claimed_ms INTEGER,
            claim_id TEXT, completed_ms INTEGER,
            result_json TEXT, result_file TEXT, result_digest TEXT)""")
        self.db.execute("CREATE INDEX IF NOT EXISTS operations_queue ON operations(state,created_ms)")
        self.sockets: set[DeviceSocket] = set()
        self.waiters: dict[str, set[asyncio.Event]] = {}
        self.gateway_sends: dict[str,float] = {}
        # Volatile same-process monotonic stage samples. No arguments, output
        # or secret values, no extra wire frame, bounded to 512 original IDs.
        # A restarted gateway reports null rather than inventing a duration.
        self.phase_ns: dict[str,list[int | None]] = {}
        self.last_heartbeat = 0
        self.catalog = catalog or [
            {"name": "rdc_job_run", "description": "Run a bounded authorized command on the paired worker.",
             "inputSchema": {"type": "object", "properties": {
                 "argv": {"type": "array", "items": {"type": "string"}},
                 "cwd": {"type": "string"}, "timeout": {"type": "number"},
                 "wait_ms": {"type": "integer"}, "output_limit": {"type": "integer"}},
                 "required": ["argv", "cwd"]}},
            {"name": "rdc_file_read", "description": "Read an authorized UTF-8 file from the paired worker.",
             "inputSchema": {"type": "object", "properties": {"file_path": {"type": "string"}},
                             "required": ["file_path"]}},
            {"name": "rdc_system_status", "description": "Read the paired worker capabilities and granted permissions.",
             "inputSchema": {"type": "object", "properties": {}}},
        ]
        self.names = {entry["name"] for entry in self.catalog}
        if any(not isinstance(name, str) or not name.startswith("rdc_") for name in self.names):
            raise ValueError("invalid worker catalog")

    def register_catalog(self, tools):
        """Atomically replace only this authenticated device's advertised tools.

        Registration never grants OS permissions and never accepts a client
        identity, gateway administrative tool or executable payload.
        """
        reserved={"rdc_connection_status","rdc_operation_status",
                  "rdc_recent_operation_metrics"}
        if not isinstance(tools,list) or not 1<=len(tools)<=256:
            raise ValueError("invalid_catalog")
        names=set()
        validated=[]
        try:
            for tool in tools:
                if not isinstance(tool,dict):
                    raise ValueError
                name=tool.get("name")
                description=tool.get("description","")
                schema=tool.get("inputSchema")
                if not (isinstance(name,str) and
                        re.fullmatch(r"rdc_[a-z0-9_]{1,95}",name) and
                        name not in names and name not in reserved and
                        isinstance(description,str) and len(description)<=512 and
                        isinstance(schema,dict) and schema.get("type")=="object" and
                        isinstance(schema.get("properties",{}),dict) and
                        len(schema.get("properties",{}))<=128):
                    raise ValueError
                required=schema.get("required",[])
                if not (isinstance(required,list) and len(required)<=128 and
                        all(isinstance(x,str) and x in schema.get("properties",{})
                            for x in required)):
                    raise ValueError
                names.add(name)
                validated.append({"name":name,"description":description,
                                  "inputSchema":schema})
            data=json.dumps(validated,separators=(",",":"),ensure_ascii=False)
            if len(data.encode("utf-8"))>1_048_576:
                raise ValueError
        except (ValueError,TypeError,RecursionError):
            raise ValueError("invalid_catalog") from None
        self.catalog=validated
        self.names=names
        return len(validated)

    def client_authorized(self, request: Request):
        header = request.headers.get("authorization", "")
        if not header.startswith("Bearer "):
            return False
        return hmac.compare_digest(header[7:], self.client_token)

    def device_authorized(self, key):
        return isinstance(key, str) and hmac.compare_digest(key, self.device_token)

    def row(self, sql, *args):
        return self.db.execute(sql, args).fetchone()

    def online(self):
        return bool(self.sockets) and self.clock() - self.last_heartbeat <= ONLINE_MS and (
            self.clock() >= self.last_heartbeat)

    def status(self):
        count = self.row("SELECT COUNT(*) AS n FROM operations WHERE state IN ('queued','claimed')")
        return {"online": self.online(), "pending_operations": count["n"],
                "protocol_version": 2, "transport": "standalone",
                "gatewaySourceSha256": self.gateway_source_sha256}

    def phase_metrics(self, limit=30):
        if type(limit) is not int or not 1<=limit<=100:
            raise ValueError("invalid_arguments")
        # Owner-only read of journal phase timing. Never return arguments or
        # result payloads. A backwards clock must never appear as zero latency.
        rows=self.db.execute("""SELECT id,created_ms,claimed_ms,completed_ms
            FROM operations WHERE state='completed'
              AND claimed_ms IS NOT NULL AND completed_ms IS NOT NULL
            ORDER BY completed_ms DESC LIMIT ?""",(limit,)).fetchall()
        samples=[]
        for row in rows:
            stamps=[row["created_ms"],row["claimed_ms"],row["completed_ms"]]
            valid=all(type(t) is int and 0<=t<2**53 for t in stamps)
            valid=valid and stamps[0]<=stamps[1]<=stamps[2]
            phase=self.phase_ns.get(row["id"])
            queue_ns=(phase[1]-phase[0] if phase is not None and
                      phase[0] is not None and phase[1] is not None and
                      phase[1]>=phase[0] else None)
            result_ns=(phase[2]-phase[1] if phase is not None and
                       phase[1] is not None and phase[2] is not None and
                       phase[2]>=phase[1] else None)
            samples.append({
                "operationId":row["id"],
                "queuePickupMs":stamps[1]-stamps[0] if valid else None,
                "claimToResultMs":stamps[2]-stamps[1] if valid else None,
                "gatewaySendMs":self.gateway_sends.get(row["id"]),
                "monotonicQueuePickupMs":round(queue_ns/1_000_000,3) if queue_ns is not None else None,
                "monotonicClaimToResultMs":round(result_ns/1_000_000,3) if result_ns is not None else None,
                "timingStatus":"valid" if valid else "invalid_clock_order"
            })
        valid_count=sum(x["timingStatus"]=="valid" for x in samples)
        return {"source":"standalone-sqlite-journal","sampleCount":len(samples),
                "validSampleCount":valid_count,
                "invalidSampleCount":len(samples)-valid_count,
                "resolutionMs":1,"samples":samples}

    def enqueue(self, key, raw, name, mutating):
        admission_ns=time.perf_counter_ns()
        digest = sha256(raw)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            existing = self.row("SELECT * FROM operations WHERE request_key=?", key)
            if existing:
                if (existing["request_digest"] != digest or existing["tool"] != name or
                    bool(existing["mutating"]) != mutating):
                    raise ValueError("request_id_conflict")
                self.db.execute("COMMIT")
                return existing["id"], False
            now = self.clock()
            if not self.online():
                raise ValueError("device_offline")
            if self.row("SELECT COUNT(*) AS n FROM operations WHERE state IN ('queued','claimed')")["n"] >= MAX_QUEUE:
                raise ValueError("queue_full")
            operation_id = str(uuid4())
            self.db.execute("""INSERT INTO operations
                (id,request_key,request_digest,request_json,tool,mutating,state,created_ms,expires_ms)
                VALUES (?,?,?,?,?,?,'queued',?,?)""",
                (operation_id,key,digest,raw,name,int(mutating),now,now+30_000))
            self.db.execute("COMMIT")
            if len(self.phase_ns)>=512:
                self.phase_ns.pop(next(iter(self.phase_ns)))
            self.phase_ns[operation_id]=[admission_ns,None,None]
            return operation_id, True
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def claim(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            now = self.clock()
            row = self.row("""SELECT * FROM operations WHERE state='queued' AND expires_ms>?
                              ORDER BY created_ms, rowid LIMIT 1""", now)
            if not row:
                self.db.execute("COMMIT")
                return None
            claim_id = str(uuid4())
            self.db.execute("""UPDATE operations SET state='claimed',claimed_ms=?,claim_id=?
                               WHERE id=? AND state='queued'""", (now,claim_id,row["id"]))
            self.db.execute("COMMIT")
            phase=self.phase_ns.get(row["id"])
            if phase is not None and phase[1] is None:
                phase[1]=time.perf_counter_ns()
            return {"id": row["id"], "claimId": claim_id, "requestJson": row["request_json"],
                    "requestDigest": row["request_digest"], "tool": row["tool"],
                    "mutating": bool(row["mutating"]), "expiresAtMs": row["expires_ms"],
                    "serverTimeMs": now}
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def recover(self, operation_id):
        row = self.row("SELECT * FROM operations WHERE id=?", operation_id)
        if not row:
            raise ValueError("operation_not_found")
        state = row["state"]
        now = self.clock()
        if state == "queued" and now >= row["expires_ms"]:
            return {"id": operation_id, "state": "expired"}
        if state == "claimed" and now - row["claimed_ms"] > UNKNOWN_MS:
            return {"id": operation_id, "state": "unknown"}
        if state == "completed":
            raw = row["result_json"]
            if row["result_file"]:
                path = self.root / "results" / row["result_file"]
                try:
                    raw = path.read_text(encoding="utf-8")
                except OSError:
                    raise ValueError("result_unavailable") from None
                if sha256(raw) != row["result_digest"]:
                    raise ValueError("result_unavailable")
            return {"id": operation_id, "state": state, "resultJson": raw}
        return {"id": operation_id, "state": state}

    def complete(self, frame):
        try:
            identifier, claim_id, reqdigest = (frame[x] for x in ("id","claimId","requestDigest"))
            raw, outdigest = (frame[x] for x in ("resultJson","resultDigest"))
        except (KeyError, TypeError):
            raise ValueError("invalid_result") from None
        if not all(isinstance(x,str) for x in (identifier,claim_id,reqdigest,raw,outdigest)):
            raise ValueError("invalid_result")
        size = len(raw.encode("utf-8"))
        if size > MAX_BULK or sha256(raw) != outdigest:
            raise ValueError("invalid_result")
        try:
            envelope = json.loads(raw)
        except (ValueError, TypeError):
            raise ValueError("invalid_result") from None
        if not isinstance(envelope,dict) or not isinstance(envelope.get("content"),list):
            raise ValueError("invalid_result")
        row = self.row("SELECT * FROM operations WHERE id=?",identifier)
        if not row:
            raise ValueError("operation_not_found")
        if row["claim_id"] != claim_id or row["request_digest"] != reqdigest:
            raise ValueError("claim_mismatch")
        if row["state"] == "completed":
            if row["result_digest"] != outdigest:
                raise ValueError("result_conflict")
            return {"id":identifier,"state":"completed","duplicate":True}
        if row["state"] != "claimed":
            raise ValueError("operation_not_claimed")
        result_json, result_file = raw, None
        if size > 262_144:
            result_file = identifier+"-"+outdigest+".json"
            path = self.root / "results" / result_file
            # A crashed writer may leave an earlier .pending file. Each
            # attempt owns a fresh temporary name, so recovery of the original
            # claim never depends on deleting an uncertain previous attempt.
            temp = self.root / "results" / (result_file+"."+str(uuid4())+".pending")
            try:
                with os.fdopen(os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),"w") as out:
                    out.write(raw)
                    out.flush()
                    os.fsync(out.fileno())
                os.replace(temp,path)
            finally:
                temp.unlink(missing_ok=True)
            result_json = None
        self.db.execute("BEGIN IMMEDIATE")
        try:
            current = self.row("SELECT state,claim_id FROM operations WHERE id=?",identifier)
            if current["state"] != "claimed" or current["claim_id"] != claim_id:
                raise ValueError("operation_not_claimed")
            self.db.execute("""UPDATE operations SET state='completed',completed_ms=?,
                 result_json=?,result_file=?,result_digest=?,request_json=NULL
                 WHERE id=?""",(self.clock(),result_json,result_file,outdigest,identifier))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise
        phase=self.phase_ns.get(identifier)
        if phase is not None and phase[1] is not None and phase[2] is None:
            phase[2]=time.perf_counter_ns()
        for event in self.waiters.get(identifier,()):
            event.set()
        return {"id":identifier,"state":"completed","duplicate":False}

    async def send_claim(self, socket, operation):
        """Measure only server-side ASGI WebSocket send, not client receipt."""
        start_ns=time.perf_counter_ns()
        await socket.ws.send_json({"version":2,"type":"claimed",
                                   "operation":operation})
        elapsed_ns=time.perf_counter_ns()-start_ns
        if elapsed_ns>=0:
            self.gateway_sends[operation["id"]]=round(elapsed_ns/1_000_000,6)
            if len(self.gateway_sends)>512:
                self.gateway_sends.pop(next(iter(self.gateway_sends)))

    async def deliver(self):
        for socket in list(self.sockets):
            if socket.pending and not socket.active:
                operation = self.claim()
                if operation:
                    socket.pending=False
                    socket.active=operation["id"]
                    try:
                        await self.send_claim(socket,operation)
                    except Exception:
                        # Claimed original stays committed, never dispatch it again.
                        pass
                    return
        for socket in list(self.sockets):
            if not socket.active and not socket.pending:
                try:
                    await socket.ws.send_json({"version":2,"type":"work_available"})
                except Exception:
                    pass

    async def wait_for(self, operation_id, ms=2500):
        initial = self.recover(operation_id)
        if initial["state"] not in ("queued","claimed"):
            return initial
        events = self.waiters.setdefault(operation_id,set())
        if len(events) >= 16 or sum(map(len,self.waiters.values())) >= 128:
            return initial
        signal=asyncio.Event()
        events.add(signal)
        try:
            latest=self.recover(operation_id)
            if latest["state"] in ("queued","claimed"):
                try:
                    await asyncio.wait_for(signal.wait(),ms/1000)
                except TimeoutError:
                    pass
            return self.recover(operation_id)
        finally:
            events.discard(signal)
            if not events:self.waiters.pop(operation_id,None)

def mcp_failure(code, rpc_id=None, status=400):
    return result({"jsonrpc":"2.0","id":rpc_id,
                  "error":{"code":-32000,"message":"RDC request unavailable","data":{"code":code}}},status)

def mcp_tool(body, error=False):
    return {"content":[{"type":"text","text":json.dumps(body,separators=(",",":"))}],
            "structuredContent":body,"isError":error}

def create_app(state: StandaloneGateway):
    async def health(request):
        return result({"service":"rdc-standalone-v2","ready":True})

    async def mcp(request):
        if not state.client_authorized(request):
            return mcp_failure("unauthorized",status=401)
        if request.method!="POST":
            return mcp_failure("invalid_request",status=405)
        body=None
        try:
            raw=await bounded_body(request,MAX_REQUEST)
            body=json.loads(raw)
            if not isinstance(body,dict):raise ValueError("invalid_request")
            rpc_id=body.get("id")
            method=body.get("method")
            if method=="server/discover":
                # Official MCP SDK probes the modern discovery endpoint first.
                # The standalone gateway supports the legacy initialize route,
                # so reply with the *standard* JSON-RPC method-not-found code.
                # A generic gateway failure would break the SDK's fallback.
                return result({"jsonrpc":"2.0","id":rpc_id,
                               "error":{"code":-32601,"message":"Method not found"}})
            if method=="initialize":
                return result({"jsonrpc":"2.0","id":rpc_id,
                    "result":{"protocolVersion":"2025-11-25",
                    "serverInfo":{"name":"rdc-standalone","version":"2.0.0-dev"},
                    "capabilities":{"tools":{"listChanged":False}}}})
            if method=="tools/list":
                catalog=list(state.catalog)
                catalog.extend([
                    {"name":"rdc_connection_status","description":"Standalone pairing status.",
                     "inputSchema":{"type":"object","properties":{}}},
                    {"name":"rdc_operation_status","description":"Recover one original durable operation.",
                     "inputSchema":{"type":"object","properties":{
                         "operation_id":{"type":"string"}},"required":["operation_id"]}},
                    {"name":"rdc_recent_operation_metrics",
                     "description":"Owner-only sanitized queue pickup and claim-to-result timings.",
                     "inputSchema":{"type":"object","properties":{
                         "limit":{"type":"integer","minimum":1,"maximum":100}}}}])
                return result({"jsonrpc":"2.0","id":rpc_id,"result":{"tools":catalog}})
            if method!="tools/call":raise ValueError("invalid_method")
            params=body.get("params")
            if not isinstance(params,dict):raise ValueError("invalid_arguments")
            name=params.get("name"); args=params.get("arguments",{})
            if not isinstance(args,dict):raise ValueError("invalid_arguments")
            if name=="rdc_connection_status":
                tool_result=mcp_tool({"ok":True,**state.status()})
            elif name=="rdc_recent_operation_metrics":
                if any(key!="limit" for key in args):
                    raise ValueError("invalid_arguments")
                tool_result=mcp_tool({"ok":True,**state.phase_metrics(args.get("limit",30))})
            elif name=="rdc_operation_status":
                original=args.get("operation_id","")
                if not isinstance(original,str) or len(original)>100:raise ValueError("invalid_arguments")
                outcome=state.recover(original)
                tool_result=(json.loads(outcome["resultJson"]) if
                             outcome["state"]=="completed" else
                             mcp_tool({"ok":True,"operation_id":original,"status":outcome["state"]}))
            else:
                if name not in state.names:raise ValueError("unknown_tool")
                request_key=args.get("_rdc_request_id") or str(uuid4())
                if not isinstance(request_key,str) or not 1<=len(request_key)<=200:
                    raise ValueError("invalid_request_id")
                other={key:value for key,value in args.items() if key!="_rdc_request_id"}
                raw_request=json.dumps({"name":name,"arguments":other},separators=(",",":"),sort_keys=True)
                if len(raw_request.encode())>MAX_REQUEST:raise ValueError("payload_too_large")
                operation_id,fresh=state.enqueue(request_key,raw_request,name,True)
                if fresh:await state.deliver()
                outcome=await state.wait_for(operation_id)
                tool_result=(json.loads(outcome["resultJson"]) if outcome["state"]=="completed"
                             else mcp_tool({"ok":True,"pending":True,
                                            "operation_id":operation_id,"status":outcome["state"],
                                            "recovery_tool":"rdc_operation_status"}))
            return result({"jsonrpc":"2.0","id":rpc_id,"result":tool_result})
        except ValueError as error:
            # Never echo parser text or private request details to remote callers.
            known={"invalid_request","payload_too_large","invalid_method",
                   "invalid_arguments","unknown_tool","invalid_request_id",
                   "device_offline","queue_full","request_id_conflict",
                   "operation_not_found","result_unavailable"}
            code=str(error) if str(error) in known else "invalid_request"
            return mcp_failure(code,body.get("id") if isinstance(body,dict) else None,
                               413 if code=="payload_too_large" else
                               409 if code=="request_id_conflict" else
                               503 if code=="device_offline" else 400)
        except Exception:
            return mcp_failure("server_unavailable",status=503)

    async def bulk(request):
        if not state.device_authorized(request.headers.get("x-rdc-device-key")):
            return fail("unauthorized",401)
        try:
            raw=await bounded_body(request,MAX_BODY_BULK)
            frame=json.loads(raw)
            if not isinstance(frame,dict):raise ValueError("invalid_result")
            receipt=state.complete(frame)
            if not receipt["duplicate"]:
                for socket in list(state.sockets):
                    if socket.active != receipt["id"]:
                        continue
                    socket.active=None
                    try:
                        await socket.ws.send_json({"version":2,
                            "type":"result_available","id":receipt["id"]})
                    except Exception:
                        # The durable completion remains recoverable.
                        pass
            return result({"ok":True,"operation_id":receipt["id"],
                           "status":receipt["state"],"duplicate":receipt["duplicate"]})
        except (ValueError,TypeError) as error:
            known={"payload_too_large","invalid_result","operation_not_found",
                   "claim_mismatch","operation_not_claimed","result_conflict"}
            code=str(error) if str(error) in known else "invalid_result"
            return fail(code,413 if code=="payload_too_large" else
                        409 if code in ("claim_mismatch","result_conflict") else 400)

    async def device(websocket):
        if not state.device_authorized(websocket.headers.get("x-rdc-device-key")):
            await websocket.close(code=4401)
            return
        if len(state.sockets)>=8:
            await websocket.close(code=4429)
            return
        await websocket.accept()
        socket=DeviceSocket(websocket)
        state.sockets.add(socket)
        state.last_heartbeat=state.clock()
        try:
            while True:
                raw=await websocket.receive_text()
                if len(raw.encode("utf-8"))>MAX_FRAME:
                    await websocket.send_json({"version":2,"type":"protocol_error","code":"invalid_frame"})
                    continue
                try:
                    frame=json.loads(raw)
                    if not isinstance(frame,dict) or frame.get("version")!=2:
                        raise ValueError("invalid_frame")
                    kind=frame.get("type")
                    if kind=="heartbeat":
                        state.last_heartbeat=state.clock()
                        await websocket.send_json({"version":2,"type":"heartbeat_ack",
                            "lastSeenMs":state.last_heartbeat,
                            "claimWaitSupported":True,"heartbeatNoAckSupported":True})
                    elif kind=="heartbeat_no_ack":
                        state.last_heartbeat=state.clock()
                    elif kind=="register_catalog":
                        tool_count=state.register_catalog(frame.get("tools"))
                        await websocket.send_json({"version":2,"type":"catalog_ack",
                                                   "toolCount":tool_count})
                    elif kind in ("claim_wait","claim"):
                        if socket.active:
                            if kind=="claim":await websocket.send_json(
                                {"version":2,"type":"claimed","operation":None})
                            continue
                        if socket.pending and kind=="claim_wait":continue
                        operation=state.claim()
                        if operation:
                            socket.active=operation["id"]
                            await state.send_claim(socket,operation)
                        elif kind=="claim_wait":
                            socket.pending=True
                        else:
                            await websocket.send_json(
                                {"version":2,"type":"claimed","operation":None})
                    elif kind=="complete":
                        if len(frame.get("resultJson","").encode("utf-8"))>262_144:
                            raise ValueError("payload_too_large")
                        receipt=state.complete(frame)
                        if socket.active==receipt["id"]:socket.active=None
                        await websocket.send_json({"version":2,"type":"result_ack",
                            "id":receipt["id"],"duplicate":receipt["duplicate"]})
                    else:
                        raise ValueError("unknown_frame")
                except (ValueError,KeyError,TypeError) as error:
                    await websocket.send_json(
                        {"version":2,"type":"operation_error","code":str(error)[:80]})
        except WebSocketDisconnect:
            pass
        finally:
            state.sockets.discard(socket)
            socket.pending=False
            # Original claimed work is not requeued on disconnect.
    return Starlette(routes=[
        Route("/health",health,methods=["GET"]),
        Route("/v2/mcp",mcp,methods=["POST"]),
        Route("/v2/device/result",bulk,methods=["POST"]),
        WebSocketRoute("/v2/device/socket",device),
    ])

def require_websocket_backend() -> bool:
    """Fail closed before /health can report ready without the device socket.

    Uvicorn can otherwise serve regular HTTP while returning HTTP 404 for a
    device WebSocket upgrade when its optional WebSocket runtime is absent.
    The documented V2 extra installs websockets on every supported host.
    """
    try:
        importlib.import_module('websockets.asyncio.server')
    except ImportError:
        raise RuntimeError(
            'RDC 2.0 standalone gateway requires WebSocket support. '
            "Install the optional dependency with pip install 'rdc[v2]' "
            'in the isolated gateway environment before starting serve.'
        ) from None
    return True


def main():
    parser=argparse.ArgumentParser(prog="rdc-standalone-gateway")
    parser.add_argument("action",choices=["init","serve"])
    parser.add_argument("--state-dir",required=True)
    parser.add_argument("--port",type=int,default=18782)
    parser.add_argument("--device-id",help="Existing worker device UUID for first-time pairing")
    opts=parser.parse_args()
    if opts.action=="init":
        root=initialize(opts.state_dir,device_id=opts.device_id)
        print("Standalone RDC gateway initialized privately in "+str(root)+
              ". Token values have not been printed.")
        return
    import uvicorn
    require_websocket_backend()
    state=StandaloneGateway(opts.state_dir)
    uvicorn.run(create_app(state),host="127.0.0.1",port=opts.port,
                proxy_headers=False,ws="auto",workers=1)

if __name__=="__main__":
    main()
