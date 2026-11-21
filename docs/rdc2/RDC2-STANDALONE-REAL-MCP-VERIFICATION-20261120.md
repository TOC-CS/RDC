# RDC 2.0 official MCP bridge over independent VPS: verified 2026-11-20

Source branch: local/rdc2-owner-hot-path-20261119. Owner requested speed-first independent VPS transport with no ChatGPT Sites, and local-first public open-source RDC.

## Verified functional flow

Official MCP client -> `rdc gateway-connect` stdio bridge -> authenticated VPS gateway over an encrypted SSH tunnel -> outbound paired RDC2 device WebSocket -> isolated RDC worker -> actual source-context/file read -> retained original result -> MCP bridge -> official client.

The gateway now accepts and bounds the actual authenticated worker catalog rather than advertising three hard-coded device tools. Exact registration ACK enforces the count; gateway-reserved MCP names are rejected. Catalog updates never broaden the local worker's permission rules. A standalone-only registration frame preserves compatibility with existing private Sites transports. Standard MCP `server/discover` receives JSON-RPC method-not-found code -32601 so clients can fall back to legacy `initialize`. The bridge accepts an explicitly provided private client-token file instead of reusing the worker's local agent token.

## Connected two-machine coding benchmark

Thirty independent, read-only `rdc_code_context` invocations discovered and read two real fixture files from the worker's restricted project through exactly one MCP call each.

- Correct original outputs: **30/30**.
- Tools discovered: **67** (real device catalog plus three gateway controls).
- Median end-to-end MCP call: **95.508 ms**; p95 **114.446 ms**; p99 **118.179 ms**.
- Min **82.387 ms**, max **118.803 ms**.
- MCP bridge initialization and tool listing: **410.561 ms** (one-time, separately measured).
- JSON evidence: `~/RDC-Development/workspace/RDC-2.0-QA/rdc2-vps-official-mcp-coding30-20261120.json`.
- Authorized isolated worker: no shared input or browser; source files under disposable QA project.
- Isolated private VPS test instance: loopback 127.0.0.1:18786; no user-facing public TLS.
- A prior direct real-worker SSH/VPS terminal benchmark: 30/30 at p50 **163.015 ms** on isolated optimized worker.

## Still open

No new publicly reachable TLS hostname, cert or automatic reboot supervision has been verified. The current ChatGPT app still points at the older private Site/worker version 0.1.0a8. The user-facing ChatGPT roundtrip of that app is not improved until a new authenticated MCP connector is actually connected. Multi-user OAuth/OIDC and tenant isolation remain unimplemented; this gateway is one owner per instance. The VPS or any operator's own server is optional for remote access; local RDC use stays subscription-free.

## Additional high-resolution isolated gateway diagnostic

A second 30-operation real coding-context campaign used the same independent MCP/SSH/VPS/isolated-worker route and returned 30/30 correct original outputs, exactly one MCP call per request, p50 **96.775 ms**, p95 **123.407 ms**, and 67 discoverable tools. Retained private evidence: `RDC-2.0-QA/rdc2-vps-official-mcp-coding30-highres-20261120.json`.

The gateway's most recent 30 completed operations had queue pickup p50 **9.0 ms**, p95 **24.85 ms**, and claim-to-result p50 **49.0 ms**, p95 **61.2 ms**. New monotonic nanosecond instrumentation measured **server-side WebSocket send** p50 **0.254 ms**, p95 **0.318 ms** across 30/30 recorded operations. This timing begins immediately before ASGI `send_json` and ends when that server API returns. It does **not** include device network receipt, deserialization or worker scheduling, and should never be misrepresented as complete notification delivery timing. These diagnostics are in-memory for server-send duration and do not survive gateway restart.

Public release acceptance remains separate: exact deployed source SHA, protected rollback, public TLS and DNS control, >=30 live correct operations per speed dimension, and >=2x over Desktop Commander in matched real-world requests, all within <=100 tests per campaign.
