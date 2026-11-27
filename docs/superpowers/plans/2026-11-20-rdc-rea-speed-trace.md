# RDC REA Speed Tracing Implementation Plan
For the active owner branch, use Superpowers systematic-debugging, test-driven-development, verification-before-completion and executing-plans. No Atlas Bus, no duplicate workers.

Goal: measure RDC 2.0 gateway phase timing precisely, compare to REA device dispatch stages and verified real MCP client wall-clock, optimize only if evidence shows a specific code bottleneck.
Architecture: one authenticated Python standalone gateway with SQLite journal, one WebSocket relay and the existing V2 source. No production Site changes.
Stack: Python, Starlette, SQLite, MCP SDK, WebSocket, macOS and owner-private VPS.
Spec: docs/superpowers/specs/2026-11-20-rdc-rea-speed-trace-design.md

Global requirements: no replay, owner auth, exact operation IDs and rollback. At most 100 tests per campaign across all categories. No public release without real connected speed proof.

## Task 1: REA and source baselines
- [x] Read completed Desktop Commander REA master and summary with limits
- [x] Compare connected RDC V1, RDC V2 isolated, and REA-backed DC flow
- [x] Identify network/host delay outside local worker and rejected regressions

## Task 2: High-resolution gateway trace (test first)
Files: tests/test_gateway_standalone.py, rdc/gateway_standalone.py, docs/rdc-test-budget-100.json.
- [x] Write tests for bounded monotonic admission-to-claim and claim-to-completion, restart nulls, duplicate immutability, privacy, clock rollback, and cap 512
- [x] Run a <=100 focused source test campaign; verify RED on missing metric
- [x] Implement monotonic stage timestamps without new I/O or network frames
- [x] Verify focused GREEN and separate <=100 core source campaign; commit exact source

## Task 3: Source-connected performance
- [x] Stage exact-source QA gateway only, isolated from production and owner VPS services
- [x] Execute 30 real correct original-output MCP operations and collect wall-clock, gateway, worker trace
- [x] Compare trace phases to observed REA stage map and find dominant residual delay
- [x] Preserve fast baseline and revert any measured regression

## Task 4: ChatGPT protected release gate
- [ ] Investigate separate authenticated V2 ChatGPT connection, Secure MCP Tunnel or verified owner HTTPS; no assumed account privileges
- [ ] Verify exact deployed source, pairings, TLS/WSS, auth and rollback
- [ ] Measure >=30 live correct samples per goal and 30 matched correct RDC/DC pairs, <=100 per campaign
- [ ] Require terminal p50 <=800ms, pickup <=50ms, claim-result <=150ms, actual notification <=1ms, one-call coding p50 <=800ms, and RDC >=2x DC median
- [ ] Keep production V1 intact while any gate is unverified


## Speed-first continuation after isolated trace

Measured source-only terminal p95 is lower with a 3ms early completion check. This remains an opt-in candidate in the source branch until the authenticated real ChatGPT V2 transport can be staged and independently verified. Do not change Site v16, v17, owner live worker, or public DNS merely to claim a speed win.

## Follow-on independent concurrency verification

The 3ms early polling improvement was additionally compared against the 10ms original in 64 read-only, correct, durable local jobs at 8-way concurrency in a disposable QA workspace. Both variants returned 32/32 correct; the candidate reduced p50 62.471 to 56.689ms and p95 91.050 to 73.105ms. Full evidence in RDC-2.0-QA/rdc-jobs-inline-poll-concurrent64-20261120.json. No production worker or site was modified; host-connected and 2x DC gates remain OPEN.


## Protected V2 private connector staging source

Added a read-only source-side tunnel readiness validator, eight focused security tests and a disabled service template under deploy/. No unverified OpenAI Platform runtime key, ChatGPT workspace entitlement, tunnel identity or credential was created. The source validator never reads credential contents and rejects unsafe public endpoints, credential aliases and symlink configs. Actual ChatGPT V2 connection setup remains OPEN until the owner can supply its authorized Platform context and the host can prove the authenticated connection, source SHA and rollback. Secure MCP Tunnel defaults also impose a 120-second deadline and a 10 MiB envelope cap, which need independent real-endpoint verification.

## Verified tunnel-client QA staging (Nov 20)

Official Linux amd64 tunnel-client v0.0.21 was checksum-verified and staged on the owner VPS in a standalone QA folder, without launching the daemon. The real on-VPS preflight correctly refused activation because the tunnel identity, restricted runtime key and separate gateway client credential remain unprovisioned. Full receipt and exact binary checksum are documented in docs/rdc2/RDC2-SECURE-MCP-TUNNEL-QA-20261120.md. No ChatGPT-hosted V2 performance receipt exists yet.

## Exact-source reproduction

Verified the same rdc/gateway_standalone.py SHA-256 on separate isolated Mac and VPS QA servers, then ran two 60-operation interleaved A/B campaigns on the same isolated worker. Coding p50 8.906ms local against 88.698ms VPS, terminal p50 91.725ms local against 176.692ms VPS, 120/120 correct across TWO separate campaigns each below the 100-operation limit. The strong single-host fast-path conclusion remains source and isolated transport evidence, not a ChatGPT-hosted release approval. See docs/rdc2/RDC2-SINGLE-MAC-SPEED-20261121.md.
