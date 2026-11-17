# v17 rollback compatibility: implementation plan

> For agentic workers: use Superpowers test-driven-development, verification-before-completion, and preserve the existing sole-owner branch.

**Goal:** Provide a real rollback-compatible gateway reader with safe old/new storage behavior and prove byte/identity regressions before any activation.

**Architecture:** Export createRollbackCompatibleGateway from the existing gateway module, forcing maxInlineResultBytes=0. No separate runtime service or privileged maintenance route. Use the existing D1/R2 fixture to exercise v17 writer and rollback reader against the same persisted operations. Package a distinct inactive rollback candidate only after regression/build validation.

**Files and steps**
1. **Tests first** in cloud-gateway/tests/gateway.test.mjs: add exact UTF-8 8192/8193 ASCII + multibyte roundtrip and R2 fallback cases. Run failing tests if a behavior gap is discovered; if already green, preserve them as explicit guard coverage.
2. Add hostile worker metadata test and assert true gateway ID on original success, retry recovery and owner-only diagnostics. Preserve original serialized payload.
3. Add cross-version rollback case: show key-only v16 reading inline would return result_expired; use a compatible-reader instance on the same migrated D1/R2 to verify readback before TTL, cleanup at expiry, no replay, wrong-owner denial, and post-rollback R2-only new result. Confirm test fails when factory absent.
4. Implement minimal createRollbackCompatibleGateway factory after the failed test, explicitly override maxInlineResultBytes to zero. No new tool or API route.
5. Run focused tests, full gateway suite, worker tests when practical, gateway production build and git diff --check.
6. Prepare an **inactive rollback-compatible build** from exact verified source in a separate staging directory by switching only the gateway factory import. Verify compiled handler and owner-private project ID, existing D1/R2 bindings and both migrations; never deploy or migrate live.
7. Commit/update existing branch and draft PR without rewriting concurrent work, run hosted CI, and record full commit, Git tree and rollback candidate SHA. Publish only source, no v17 activation.
8. Update existing RDC continuation, owner matrix, and verification ledger; request Atlas scoped approval for design/CI only. Whole RDC release remains open.
