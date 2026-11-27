# RDC Owner-Direct Local Codex MCP Speed

Date: November 21, 2026. Scope: one authorized owner device, not a public hosted gateway. The old ChatGPT private Site is preserved.

## Why this route exists

The same owner can use the official Codex MCP local stdio bridge against the authenticated RDC worker already running on their own machine. The bridge connects over loopback with the existing private agent-token handled by the RDC client. It does not copy token bytes to the AI prompt, plugin source or shell arguments, does not restart the worker, and does not replace the existing ChatGPT connector. A local user does not need the maintainer's VPS, Site or computer, and the public product must never route other users through the maintainer's workstation.

A distinct Codex MCP entry named rdc-owner-direct was registered using the source-controlled credential-free helper scripts/rdc_setup_codex_local.py. Existing rdc and rdc2-fast-local aliases were preserved. The existing installed worker had full-host access and shell execution enabled before this change; the new alias inherits precisely those prior permissions and is intentionally owner-only. Treat globally registered direct aliases as sensitive and remove them when no longer wanted.

## Authenticated real MCP evidence

The local worker returned HTTP 401 for an unauthenticated MCP request. An official Python MCP SDK client read the exact saved Codex alias and executed a 61-operation campaign: 30 correct system-status reads, 30 correct independent two-file reads, and one harmless exact-output terminal echo.

- Source-only MCP startup and tool discovery: 306.960 ms, 58 advertised worker tools.
- System status p50 92.161 ms, p95 111.654 ms.
- Two-file read p50 2.063 ms, p95 2.546 ms.
- One original terminal echo: 105.258 ms, completed exit code zero.

A separate original-output terminal campaign executed 30 independent durable echo jobs through the same saved alias, 30/30 correct. Exact results:

| Direct local original terminal | Measured |
| --- | ---: |
| p50 | 104.380 ms |
| p95 | 112.182 ms |
| p99 | 126.477 ms |
| Startup plus tool discovery | 301.764 ms |

The latter campaign initially failed before any tool action because a local test assertion incorrectly searched for a URL substring as a complete list member; the harness was corrected and its bounded 30-call campaign then passed. No uncertain mutation was replayed. Both private receipts are retained under RDC-2.0-QA/rdc2-owner-direct-mcp61-20261121.json and RDC-2.0-QA/rdc-owner-direct-terminal30-20261121.json.

## Security, cost and limits

This path gives the owner a fast working local Codex connection immediately and avoids the overhead of the private hosted Site. It does not modify the installed worker release, which still identifies as RDC 0.1.0a8. It does not connect the faster V2 standalone source to the current ChatGPT-hosted MCP tool, make a new public service, or satisfy the six ChatGPT-connected speed acceptance gates.

No OpenAI Platform API calls, paid model inference, credit purchases, auto-recharge changes, VPN routing or Cloudflare were used for this path. Local MCP measurements have a different host boundary than the original ChatGPT Desktop Commander comparison. Do not label them matched host performance or proof of the >=2x live superiority target.

To retire only this owner-specific Codex connection, use the supported Codex command: codex mcp remove rdc-owner-direct. The original and QA aliases remain available. The optional local alias may be retained solely while the owner wants that trusted computer available to Codex.

## Connection follow-up

Independent ChatGPT custom MCP connection currently requires a remote HTTPS endpoint or Secure MCP Tunnel, plus account/workspace permissions. Full custom MCP use and write actions are plan-restricted, and Platform billing credits do not confer workspace permissions. The current ChatGPT private plugin 1.0.30 and old connected worker must remain operational until the owner-authorized separate V2 gateway has authenticated deployment, actual notification timing, protected rollback and correct 30+ matched ChatGPT/DC latency receipts.
