# Claimed Completion Polling Implementation Plan

> **For agentic workers:** Use superpowers:test-driven-development and superpowers:executing-plans; preserve current branch and prior evidence.

**Goal:** Cut avoidable result-detection delay for claimed short cloud commands with bounded database reads.

**Architecture:** The existing `dispatch()` operation state determines the polling interval. It keeps 500ms while queued and after three 100ms claimed-only probes. No new API or persisted state.

**Tech Stack:** JavaScript (Cloudflare Worker), Node.js test runner, D1-compatible in-memory test fixture.

**Spec:** docs/superpowers/specs/2026-11-16-claimed-completion-polling-design.md

## Global Constraints
- Do not mutate installed worker, private gateway deployment, plugins, permissions, BandMates or sessions.
- Only the existing draft PR branch. Preserve existing rollback checkpoint.
- Verify failing tests, minimal fix, 28 existing gateway tests plus new tests, production build, source publication and exact Git tree check.

## Review Focus
- Queued until deadline continues using original interval.
- Three claimed-only fast probes, then 500ms.
- Completion after first observed claim returns early.
- Unknown/expired state exits promptly.
- Cloud cancellation and original durable operation identity remain unchanged.

### Task 1: Claimed-only fast detection
**Files:** Modify: `cloud-gateway/tests/gateway.test.mjs`, `cloud-gateway/lib/rdc-gateway-core.mjs`
**Interfaces:** Consumes `dispatch()` existing `op.state`, `L.pollStepMs` and `clock/sleep`; produces unchanged `CallToolResult` contract.
- [ ] Add a test that records sleep intervals and simulates a claim at the first 500ms callback, then completion at the next callback. Require an early first-call result under 700ms simulated time.
- [ ] Add a test that leaves a claimed operation pending, asserting exactly three 100ms probes before 500ms intervals resume. Verify no claim means only 500ms intervals.
- [ ] Run each new test and verify expected failures against old behavior.
- [ ] Implement a local `claimedFastProbes` counter in `dispatch()`; when `op.state==='claimed'`, poll with `Math.min(100, L.pollStepMs)` no more than three times, else use `L.pollStepMs`.
- [ ] Run focused and full gateway Node tests; run gateway production build and git diff check.
- [ ] Publish only after clean local verification; keep PR draft and read back exact remote tree.
