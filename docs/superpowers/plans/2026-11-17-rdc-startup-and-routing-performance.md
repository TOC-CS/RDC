# RDC startup and routing performance implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development, superpowers:systematic-debugging, and superpowers:verification-before-completion. Execute tasks in order. Do not activate production.

**Goal:** Reduce RDC cloud dispatch latency and first browser workflow round trips without sacrificing reliability.
**Architecture:** Specialize gateway online-only admission checks while retaining owner-authenticated status endpoint. Add a browser start/navigate/observe composite on the current isolated browser-owner thread. All mutations retain stable cloud request IDs.
**Tech Stack:** Node.js ESM Cloudflare gateway, Python 3.14 RDC adapter, Playwright/WebDriver, Node tests, unittest.
**Spec:** docs/superpowers/specs/2026-11-17-rdc-startup-and-routing-performance.md

## Global constraints
- Work in exclusive worktree `perf/rdc-startup-cloud-fastpath-20261117`.
- No edits to existing 3-way chat code, Atlas Bus owners, credentials, deployment or live daemon.
- Current private Site v16 and worker 0.1.0a8 remain untouched; do not claim live candidate activation.
- Preserve browser source binding, owner approvals, no-replay semantics, and error readback.
- Use actual RDC connected ChatGPT calls to run and inspect tests.

## Task 1: Gateway liveness check
**Files:** cloud-gateway/lib/rdc-gateway-core.mjs, cloud-gateway/tests/gateway.test.mjs
- [ ] Write a failing test that captures issued D1 queries and proves new dispatch skips the pending-operation COUNT while connection_status retains it.
- [ ] Verify RED from the live RDC terminal.
- [ ] Add a dedicated online-only liveness helper with one heartbeat lookup and no queue COUNT.
- [ ] Re-run gateway suite to GREEN; verify all owner and capacity gates unchanged.

## Task 2: Single-call browser startup
**Files:** rdc/adapters.py, tests/test_adapters.py, docs/...
- [ ] Add failing adapter tests for start+navigate+observe success, invalid URL before launch and navigation failure retaining recoverable session ID.
- [ ] Verify RED.
- [ ] Advertise `rdc_browser_start_navigate_observe` in catalog, mutating=true with required url and optional browser/width/height.
- [ ] Implement by reusing existing start, navigate, observe on one browser-owner thread. Return fresh controls on success; bounded nonsecret failure plus session ID if started.
- [ ] Verify GREEN and no changes in original browser tools.

## Task 3: Gateway catalog / full verification
**Files:** synced cloud-gateway/lib/rdc-assets.json, cloud-gateway/tests/gateway.test.mjs
- [ ] Sync catalog from the isolated worktree.
- [ ] Validate gateway tool contract for new composite (stable request ID).
- [ ] Run entire Python suite, entire Node gateway suite, diff --check and safe source hash review through RDC.
- [ ] Commit scoped changes and save a source bundle and test evidence at an RDC checkpoint.
- [ ] Flag pending independent review, production activation, real ChatGPT A/B benchmarking and startup p50/p95.

## Review focus
- Active owner desktop must never be activated by new browser commands.
- Invalid URL and unsupported browser must not leak sessions or credentials.
- Failed observation after browser creation must return the exact session ID for inspection rather than suggesting retry.
- Duplicate cloud mutations must not create second sessions.
- Cloud admission must reject offline and full backlog exactly as before.