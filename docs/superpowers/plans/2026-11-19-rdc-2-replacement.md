# RDC 2.0 Clean Replacement Implementation Plan

> For agentic workers: required Superpowers workflow is test-driven development, systematic debugging, isolated worktrees, verification-before-completion. No agent dispatch may be asserted without an authenticated running worker.

**Goal:** Replace the high-latency RDC gateway and relay with a low-latency, durable, owner-authorized 2.0 system that exceeds Desktop Commander performance without losing tool capabilities.

**Architecture:** Introduce a new versioned ID-only event protocol, then connect it to a durable gateway journal and authenticated worker. Keep current production traffic on the old version until an independent canary is proved correct, fast and rollback-safe.

**Tech stack:** Node 24, ECMAScript modules, Cloudflare D1/R2/Durable Objects, Python 3.14, MCP, git worktrees, Node test and Python unittest.

**Spec:** docs/RDC-2.0-REPLACEMENT-ARCHITECTURE-20261119.md

## Global Constraints

- All hostile and fault-injection executables belong exclusively to the SIBLING ../RDC-2.0-QA directory.
- Release source must not include hostile fixtures or synthetic secrets.
- Never touch the active private ChatGPT App, Site, worker or TOC production data during isolated qualification.
- Keep authorized owner, file-path restrictions, approvals, hashes, durable outcomes and no-replay semantics.
- No status or benchmark claim of <=800ms without at least 30 real connected calls and exact output validation.

## Review Focus

- Duplicate/missed event hints must never redispatch local work.
- Unauthenticated principal cannot read online or queue status.
- Invalid event JSON must not leak code, arguments, or secrets.
- A disconnected wake service must preserve correct polling fallback.
- Release rollback must understand all result storage formats written by the new version.

### Task 1: Versioned control protocol
- [x] Write failing five-test source contract for negotiation, immutable ID-only events, strict wire validation and sequence bounds.
- [x] Confirm RED on missing module.
- [x] Implement clean module cloud-gateway/lib/rdc-v2-protocol.mjs.
- [x] Confirm five focused tests GREEN.
- [x] Run 12,000 invalid-input adversarial cases and 1,000 valid round trips in external QA.
- [x] Run 116-test existing gateway + v2 regression suite.
- [ ] Independent review of module and final commit.

### Task 2: Persistent event-channel integration
- [x] Write RED six-test broker contract for monotonic events, independent listeners, cancellation, capacity and expired-history gaps.
- [x] Implement isolated clean RDCV2EventBroker module with bound state and original operation identity.
- [x] Run external 1000-listener / 700-abort / 3000-event QA, all four scenarios green.
- [x] Re-run 122 Node gateway + v2 regression tests.
- [x] Write RED then GREEN v2 private notification tests for device and operation identity, bounded history, polling fallback and no payload leakage.
- [x] Add the exact opt-in RDC_ENABLE_V2_WAKE private DO route, retaining V1 routes and D1 claims.
- [x] Preserve one gateway poll channel cursor; verify stream/body bounds and no unauthorized operation execution.
- [x] Include the new v2 regression tests in the existing macOS/Linux/Windows gateway CI entry point.
- [x] Run 132/132 Node gateway and protocol tests, default and DO-enabled Site builds, TypeScript and focused ESLint.
- [x] Run five detached hostile V2 wake scenarios in the sibling QA folder.
- [ ] Run a real provisioned development Durable Object smoke to confirm service lifecycle and network bounds.
- [ ] Verify a protected private Site rollback and actual compatible worker before production feature activation.
- [ ] Measure at least 30 fresh live samples for all mandatory speed metrics.
- [ ] Write failing gateway event admission + result recovery tests, with original operation IDs and no-replay.
- [ ] Add new gateway adapter only behind an explicit v2 protocol version, without touching v1 behavior.
- [ ] Run normal gateway suite and external network-disconnect hostile fixture.
- [ ] Compare exact live wake p50/p95/p99 with 30+ matched samples.

### Task 3: Worker and coding capabilities
- [ ] Build persistent worker event stream and explicit typed version handshake.
- [ ] Add bounded read-only concurrency and serialized idempotent mutation path.
- [ ] Verify one-call source discovery/read, bulk edits, browser session handling and permissions.
- [ ] Run 30-pair benchmark RDC 2.0 vs DC per workload.

### Task 4: Cross-platform and hostile QA
- [ ] Run all worker regressions on isolated source.
- [ ] Build private Site default and opt-in v2 configurations, then exact bundle inventory.
- [ ] Run macOS, Ubuntu and Windows CI on exact source commit.
- [ ] Rehearse offline relay, blocked queue, timed-out result, invalid input and rollback mismatch in detached synthetic fixtures.

### Task 4B: Host-owned floating preview and verified task lifecycle
- [x] Inspect existing PiP controls and preserve source-bound no-focus behavior.
- [x] Write failing worker tests for job binding and exact terminal-only completion.
- [x] Add optional job ID to open/frame without adding another cloud status request.
- [x] Run MCP host regression tests for PiP accepted/unavailable, running/finished/uncertain task, wrong job and new-job binding.
- [x] Build and sync embedded renderer and schemas into gateway assets.
- [x] Run external 407-case hostile lifecycle QA outside the source checkout.
- [ ] Verify actual ChatGPT/Codex host can float, move and dismiss preview, without affecting other task views.
- [ ] Generalize to visual/browser task completion with authenticated source-bound events.
- [ ] Verify two independent float views, no focus theft, and persistent source work.

### Task 5: Safe replacement
- [ ] Read back installed worker version and exact deployed Site SHA.
- [ ] Verify inactive rollback that can read both legacy R2 and inline D1 outcomes.
- [ ] Stage authenticated existing private Site canary and source-compatible worker.
- [ ] Collect all five mandatory sets of >=30 live verified samples, fail closed.
- [ ] Replace v1 only after functionality, privacy, p50/p95/p99 and recovery gates all pass.

## Parallel Ownership

Transport/event API: v2 protocol and transport integration only.
Gateway: durable D1/R2 admission and recovery only.
Worker: Python relay, coding, browser only.
QA: sibling external hostile harness only.
Integrator: release identity, full regression and readback only.

Atlas Bus may coordinate synthetic tasks today, but its present version has no authenticated ChatGPT-to-agent transport. No real multi-agent swarm has been dispatched by a checklist.
