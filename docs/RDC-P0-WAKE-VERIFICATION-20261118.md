# RDC P0 Speed First, source qualification and deployment hold
**November 18, 2026, TOC Ministries**
**Branch:** perf/rdc-speed-wake-20261118, based on isolated b63fa4d (coding-context PR #10).
**Scope:** Gateway-only optional private Durable Object wake hints. No deployment, worker restart, D1/R2 cleanup, credentials, or native desktop actions.

## Baseline and goal
Earlier 30 matched ChatGPT shell roundtrips: RDC v16 p50 3178ms and Desktop Commander 0.3.1 p50 1820ms, both 30/30 correct. RDC gateway 12 terminal operations: queue wait median 311ms, claim-to-result median 678ms, total service median 982.5ms. Target: >=2x *faster* RDC p50 and p95 on each relevant real-world workflow with exact correctness and no increased failures. These historic samples are not evidence of post-release improvement.

## Implemented
1. Optional bound wake channel injected into the existing gateway. Successful new D1 admissions signal only the paired device; any available relay poll rechecks the original D1 conditional claim.
2. After D1 commits a result, the paired device/operation-specific completion hint wakes the original cloud request. It always rechecks D1 for the authoritative stored response.
3. New private exported `RDCWakeSignal` Cloudflare Durable Object class with short bounded waiters, request timeout/abort cleanup, and no public route or raw tool data.
4. Existing gateway polling, mutation no-replay, permission checks and read-only status remain unchanged when the binding is absent. Signal errors do not consume or drop a queued action.
5. Updated RDC primary skill for speed-first priorities, DO binding release gates, recurring gateway_busy and external task-bound floating preview auto-clear as an open requirement.
6. The existing CI gateway test entrypoint imports the new DO tests, so macOS, Ubuntu and Windows execute both suites without a GitHub workflow edit.

## Test-first receipts and verification
- Queue wake: 3 red cases before implementation; green after repair.
- Env binding factory: red then green.
- Completion notification: red then green.
- New DO module: module missing red; five green, then operation-specific red followed by seven green.
- **Node gateway suite (latest revision):** 70 passed, zero failures/skips, 442.296 ms. Two new red-first cases exposed unbounded D1 claim/result queries under repeated spurious wake hints. Both initially failed and turned green after capping trusted wake-triggered probes at three per original gateway operation, then reverting to the existing timed D1 sweep. No new event may authorize execution or repeat a mutation.
- **Python worker suite:** 485 tests run, 43 skipped, zero failures in 138.053 seconds (ran before the last skill wording change; updated skill-specific 4/4 passed separately).
- **Isolated Site production build:** succeeded via the source-matching npm lockfile dependency clone.
- **TypeScript `tsc --noEmit`:** initial error on optional wakeChannel inference, corrected to explicit WakeChannel JSDoc type, then passed.
- **Lint:** zero errors, one existing image-performance warning in app/page.tsx.
- **Git diff --check / JS syntax:** passed.
- **In-process 30/30 wake simulation:** notification p50 0.247ms/p95 0.485ms, timer fallback p50 501.591ms/p95 501.890ms. This only measures local DO-class behavior and a timer. It excludes actual Cloudflare DO/D1 costs, network, ChatGPT, worker and Desktop Commander.
- **Security/privacy:** only device UUID and original operation UUID used as hints; duplicate/rejected request suppression; D1 remains authoritative.

## Open acceptance and release gates
1. Owner-private Site has no verified `RDC_WAKE_CHANNEL` binding or SQLite DO namespace. Existing v16 stays unmodified. Source class export alone does not activate the optimization.
2. A private staging release must prove the host permits the binding and that event delivery reduces *real* D1 pickup and completion latencies while keeping failed-hint fallback within bounds.
3. Independent protected rollback-compatible Site version and exact production source/version readback required before activation.
4. Existing recurring `gateway_busy` retained-operation capacity blocker is separately addressed by draft PR #3, not this change; readiness requires joining and qualifying the fixes.
5. Actual 30+ balanced live ChatGPT RDC/DC rounds in terminal, coding, browser, file search/read, correct exit/output, p50/p95/p99 and resource/cost usage remain OPEN.
6. Floating preview that operates outside chat and auto-clears on completed task is priority four, not implemented by this speed branch.
7. No hosted coding-agent APIs or Keychain secrets were used. Saved provider key metadata was checked only; external model quota/cost and independent hosted review remain unverified.

## Evidence files
- `test-results/rdc-p0-wake-local30-20261118.json` (nonsecret per-sample benchmark)
- `test-results/rdc-p0-wake-all-gateway-20261118.log`
- `test-results/rdc-p0-wake-full-python-20261118.log`
- `test-results/rdc-p0-wake-site-build-20261118.log`
- `test-results/rdc-p0-wake-tsc-20261118.log`
- `test-results/rdc-p0-wake-lint-20261118.log`
- `docs/RDC-P0-WAKE-STAGING-20261118.md`

**Status:** READY FOR SOURCE REVIEW. Live superiority and production completion are OPEN. Never merge/activate based solely on local wake timer measurements.
