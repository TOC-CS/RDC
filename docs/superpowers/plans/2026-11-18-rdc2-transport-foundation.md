# RDC 2.0 Durable Transport Foundation Implementation Plan

Goal: implement a standalone clean V2 durable journal and private actor.
Spec: docs/superpowers/specs/2026-11-18-rdc2-replacement-architecture.md
Stack: Cloudflare Durable Object SQLite, JS ES modules, Node sqlite tests.
Process: Superpowers worktree, test-driven-development, debugging, regression, verification.

Task 1: V2 Journal
- [x] Write failing tests for exact owner, admission, duplicate/conflict, single claim, complete, recover, restart, overload and expiry.
- [x] Run RED then create clean rdc2-journal.mjs implementing synchronous atomic state machine.
- [x] Run focused tests and baseline gateway suite.

Task 2: V2 internal actor
- [x] Write RED actor tests for internal auth and event hint privacy.
- [x] Implement a no-public-route V2 DO class and test claim/completion/recovery plus disconnects.
- [x] Confirm default Site unaffected, opt-in DO build and static checks.

Task 3: Harsh isolated regression
- [x] Outside repository, build disposable malicious-input and failure-storm runners.
- [x] Confirm no hostile code in distributable and no sensitive data in logs.
- [x] Measure CPU, latency, p50/p95/p99, output exactness, crashes, no-replay.

Task 4: Handoff
- [ ] Full original gateway and Python regression, typecheck, lint, build, GitHub CI.
- [ ] Publish clean draft PR only. Keep production cutover blocked until compatible rollback, private Site release authority, real speed 30-sample acceptance.
