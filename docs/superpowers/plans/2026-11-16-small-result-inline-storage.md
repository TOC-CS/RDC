# Implementation plan: bounded inline small results

**Prerequisite:** deployed v16 healthy, owner-private Site version15 rollback intact; published source HEAD 3001050 and clean.

**Files:**
- cloud-gateway/db/schema.ts: nullable resultInlineJson TEXT.
- cloud-gateway/drizzle/: generate one additive Drizzle migration and metadata; retain existing 0000 migration untouched.
- cloud-gateway/lib/rdc-gateway-core.mjs: 8192-byte threshold, inline-or-R2 durable completion, authorized readback, TTL cleanup, identity retention.
- cloud-gateway/tests/gateway.test.mjs: new real D1 fixture regressions. Write failing tests *first*.
- cloud-gateway/README.md: revise exact D1/R2 and rollback/retention contract.
- docs/superpowers/specs/2026-11-16-small-result-inline-storage.md: reviewed design/risk.

**Steps:**
1. Add tests for small complete result -> zero R2 PUT, exactly one D1 result, unchanged original recovery, no duplicate dispatch, TTL clears payload, principal isolation. Add tests for forced large fallback and unexpired retention. Run tests RED against current code.
2. Add schema and generate additive migration through the preinstalled drizzle-kit, inspect SQL for only one ADD COLUMN, verify old data survives.
3. Implement smallest gateway changes. Run tests GREEN; run current 32 contract tests and 364 worker tests, build, lint, strict source diff.
4. Save local checkpoint. Publish to existing branch/PR only after verification. Verify Git tree exact. Run hosted CI for exact revision. No plugin change if external MCP tool schema unaffected.
5. Before any live deployment, save current v16 source/version/archive/identity and ensure DB migration is additive. Deploy ONLY via existing Site project and verify owner-only connection, terminal idempotency, large readback and cleanup. Compare claimed-to-completed timings to v16 12-call baseline and separate client overhead.
6. Leave host PiP/cursor/App outer branding and physical BandMates acceptance OPEN until supported host behavior is observed. Do not publish BandMates.

**Stop conditions:** Any migration that drops columns/tables, alters owner identity, exceeds inline cap, allows extra replay, changes permission or App binding, loses previous R2 results, or changes unrelated user app state.
