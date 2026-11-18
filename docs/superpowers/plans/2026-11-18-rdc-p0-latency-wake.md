# RDC P0 Event-driven Transport Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:test-driven-development, systematic-debugging, verification-before-completion and isolated worktrees.

**Goal:** Reduce RDC queue pickup and result visibility latency without compromising durable no-replay semantics.
**Architecture:** Keep D1 admission/claim/result as authority. Attach an optional device-scoped Cloudflare Durable Object notification channel behind a live owner-provisioned binding. Missing or uncertain signals fall back to the existing polls.
**Tech stack:** Cloudflare Workers/D1/R2, optional Durable Objects, ESM JavaScript/TypeScript, Node 24 test runner, Python 3 RDC relay, GitHub CI.
**Spec:** docs/superpowers/specs/2026-11-18-rdc-p0-latency-wake.md

## Global constraints
- Speed priority P0; measured 2x improvement relative to DC is the eventual target, not a source-only acceptance claim.
- New code only in perf/rdc-speed-wake-20261118 linked worktree, based on b63fa4d.
- Do not touch live paired Site, worker, tokens, mutable journal or native pointer.
- Preserve D1 conditional claim, exact mutation recovery and privacy.
- No extra D1 polling/queries when signal path is available, no extra permission granting.
- Tests target both notification and missing-binding default path.

## Review focus
- Lost signal between claim probe and subscribe: bounded fallback must still claim D1 operation.
- Network exceptions and a missing DO binding: no rejected or repeated work.
- Duplicate request identity and duplicate result uploads: no duplicate wake or execution.
- Operation-specific result notification: no cross-operation wake or result data exposure.
- Permission and billing: DO namespace keyed by paired device only, owner-provisioned, live usage and cost limits qualified before release.

## Task 1: Queue wake (test-first)
- [x] Add RED tests to gateway.test.mjs for wake, rejection, no replay and backend outage.
- [x] Confirm RED 3/3.
- [x] Implement optional wakeChannel injection and D1 fallback; verify GREEN.

## Task 2: Cloudflare DO adapter and binding (test-first)
- [x] Write failing tests for missing module and scoped wake notifications.
- [x] Implement rdc-wake.mjs adapter and exported Durable Object class.
- [x] Confirm source test GREEN and optional factory use.
- [ ] Confirm staging worker build and explicit binding configuration instructions without changing production Site.

## Task 3: Completion notification (test-first)
- [x] Add RED gateway test for event-driven result completion.
- [x] Add RED operation-scoped DO tests.
- [x] Implement completion hint after result D1 update and host wake wait, then recheck original operation state.
- [x] GREEN targeted tests.

## Task 4: Independent qualification
- [x] Run entire gateway suite and worker Python suite, preserving exact logs/skips/warnings.
- [x] Run local Site build, TypeScript, lint and safe default-transport compatibility tests.
- [ ] Run full staging D1-query budget and DO network timing comparison with at least 30 rounds (local DO-class timer benchmark completed; network/D1 stage remains OPEN).
- [ ] Save exact SHA, source stats, owner review packet and remaining held rollout gates.
- [ ] Publish clean branch to existing TOC-CS/RDC GitHub as a draft PR; do not deploy.
- [ ] After protected rollback/private Site activation is authorized, run >=30 matched live RDC/DC requests across terminal, coding, browser and file operations.

## Task 5: Next independent priorities after this scope
- [ ] Capacity admission repair from existing PR #3, then hardened integration.
- [ ] Capability expansions from PR #10 and its tested branch, selectively integrate after conflicts are resolved.
- [ ] Floating task preview, potentially an external OS window, that auto-clears on completed task and respects owner focus.
