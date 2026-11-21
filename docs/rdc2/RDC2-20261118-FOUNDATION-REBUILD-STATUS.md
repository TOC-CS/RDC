# RDC 2.0 clean replacement transport: source build and qualification
Date: 2026-11-18, America/Chicago
Owner: TOC Ministries
Source branch: rewrite/rdc-2-transport-20261118
Integration base: 3371045 (the isolated earlier performance candidate)
Status: SOURCE READY FOR DRAFT REVIEW, NOT LIVE AND NOT RELEASED.

## Objective and protected work
The required 2.0 mission is a replacement architecture rather than additional patches to the installed gateway. Preserve the current Site, app identity, local v1 relay and existing private execution grants. The measured old connected RDC median was 3178 ms across 30 matched shell operations versus Desktop Commander 1820 ms. Owner acceptance medians remain live terminal <=800ms; queue pickup <=50ms; claim-to-result <=150ms; notification <=1ms; and coding discovery plus selected source read <=800ms in one cloud request. Each metric requires 30+ correctly timed genuine live operations and p50/p95/p99 with deployed revisions.

## V2 source implemented
1. New colocated SQLite-backed Durable Object journal: owner identity, original request keys and digests, bounded admissions, FIFO claims, conditional exact claim-result identity, restart recovery, retention, no replay and strict malformed-input rejection.
2. Private V2 actor: hibernating WebSocket, queue notifications without data, heartbeat, claim, completion ACK and bounded admit-and-wait results. The same actor request performs original owner enrollment or equality, avoiding an extra network hop.
3. Completely separate private Site /v2/mcp endpoint and /v2/device/socket route. Both inactive unless RDC2_RUNTIME_ENABLED=1. Opt-in RDC2_DEVICE namespace requires RDC_ENABLE_V2_BINDING=1, and the default has zero new DO bindings. Existing /mcp remains unchanged.
4. Separate Python relay-v2 mode using an authenticated persistent WebSocket, event-driven original claims and durable local execution journal. Original relay mode unchanged. A single exclusive local relay lock prevents concurrent v1/v2 action loops. Python websockets>=16,<18 is an optional dependency, installed only in a disposable external test directory.
5. Default, V2 and combined v1-wake+V2 builds preserve the original D1 and R2 definitions while new source is off by default.

## Superpowers, Atlas and adversarial execution
Superpowers 7.0.1 skill documents were used as TDD, systematic debugging, brainstorming, worktree isolation and verification methodology. Actual independent reasoning subagent dispatch was unavailable. Deterministic Node, Python, builds and stress simulations ran as distinct processes; these are separate test lanes, not independent AI agents.

The existing Atlas Build Bus currently supports synthetic SQLite coordination only. Four synthetic RDC2 evidence packets were queued, claimed and acknowledged in an external disposable SQLite database. Integrity check returned ok, and real session enrollment was correctly blocked with REAL_ENROLLMENT_BLOCKED. No real Atlas Dot callback, independent model-worker session, or cross-chat communication was activated. The separate Atlas source checkout was not modified.

Hostile traffic and fault injection scripts live outside distributable source under RDC-Development/checkpoints/rdc2-hostile-regression-20261118. Scenarios include 250 unauthorized calls, 200 forged hashes, 128 concurrent admissions/duplicates, 144 claims with zero duplicate actions, saturation, dropped wake, malformed messages, oversize payload, restart, lost ACK and cross-owner denial.

## Evidence verified so far
- Standalone V2 Node suite: 36 passing.
- Combined original gateway + new V2 suite: 147 passing, zero failures, after server deadline clock verification.
- Existing full Python suite before new client: 487 tests, 43 skipped, zero failures. New full suite rerun with additional V2 client tests is recorded independently.
- Separate new Python WebSocket relay unit tests: 10 passed.
- Three Site build modes succeeded; TypeScript passed and ESLint had 0 errors and the existing Next image warning.
- Harsh external scenarios: 14 passing; 128 LOCAL admission samples p50 about 8.54ms, p95 about 10.89ms, p99 about 11.11ms. These cannot be conflated with live cloud latency.
- Real local Miniflare/workerd SQLite Durable Object test: 13 calls, persistence across restart, one original result and no reexecution.
- Real local WebSocket smoke: successful native handshake, private wake and exact completion on 127.0.0.1.
- Python WebSocket through real local workerd, existing RelayPump and synthetic worker: exactly one execution, local durable journal marked delivered, result recovered by cloud actor, duplicate rejected; ~1018ms total including fixture setup. This does not represent live ChatGPT latency.

## OPEN gates before replacing live RDC
A. Modern host MCP negotiation/metadata parity and connected ChatGPT private Site/App readback.
B. Direct V2 result limit is currently 256 KiB. Implement and regression-test bulk media/large-file result fallback with R2 or chunked transport before replacing the original 12 MiB capability.
C. Obtain legitimate owner-private Site release control, exact current Site version, protected inactive rollback compatibility and deployment opt-in.
D. Verify Cloudflare account cost/limits, owner-private audience and TLS WebSocket in real production.
E. Run at least 30 fresh matched live operations per owner speed metric with exact revision and no gateway_busy.
F. Independent code review and cross-platform GitHub CI on the final exact SHA.

The installed worker and private Site were not modified or restarted. No production credentials, user data or hostile test drivers enter source/release artifacts.
