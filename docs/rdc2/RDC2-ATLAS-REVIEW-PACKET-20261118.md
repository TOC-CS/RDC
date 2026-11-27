# RDC 2.0 independent Atlas review packet
Owner: TOC Ministries
Status: READY FOR INDEPENDENT REVIEW OF SOURCE FOUNDATION ONLY
Atlas delivery: UNVERIFIED; current bus has no real ChatGPT session adapter
Target branch: rewrite/rdc-2-transport-20261118
Commit SHA: see exact Git history after source qualification and publishing.

## Decision request
Assess the source-only private SQLite Durable Object event-driven architecture for performance potential, strict original operation identity, owner isolation, restart recovery, and compatibility. Return ACCEPT for this scoped source foundation only if test evidence warrants it, otherwise REWORK with exact reproduction. Full V2 feature parity and live acceptance remain OPEN. No independent Atlas reviewer has authenticated this change.

## Reviewed source paths
cloud-gateway/lib/v2/rdc2-journal.mjs
cloud-gateway/lib/v2/rdc2-actor.mjs
cloud-gateway/lib/v2/rdc2-edge.mjs
cloud-gateway/lib/v2/rdc2-edge.ts
cloud-gateway/scripts/rdc2-bindings.mjs
cloud-gateway/app/v2/mcp/route.ts
cloud-gateway/vite.config.ts and worker/index.ts
rdc/relay_v2.py, pyproject.toml, rdc/cli.py
tests/test_relay_v2.py and cloud-gateway/tests/v2/

## Evidence and strict boundaries
Complete Node and Python regression, local Workerd SQLite and actual WebSocket, separate synthetic hostile tests and protected default build. Read the accompanying status for exact counts and caveats. No v1 production mutations or original active worker restarts occurred. External adversarial test scripts exist only outside source/release and use disposable credentials. Strict 30+ authenticated production speed receipts, protected rollback and private Site release control are missing.

## Review priorities
Exact owner identity and grant, immutable request hashes and original claims, never replay of unknown mutations, no secrets in socket hints, fail closed on unauthorized public routing, DO WebSocket hibernation and SQLite limits, optional Python socket compatibility, bulk result feature parity, modern MCP negotiation, release rollback compatibility.
