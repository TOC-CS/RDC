# RDC speed and capacity integration qualification

Date: 2026-11-18 (America/Chicago)
Status: isolated source candidate, production untouched
Owner: TOC Ministries

## Scope and provenance
- This isolated integration worktree is based on the latest published P0 speed source commit `18d7992384730f0bf2bf45bcbed75cf722d60a25` from [draft PR #11](https://github.com/TOC-CS/RDC/pull/11). That branch depends on coding-context [draft PR #10](https://github.com/TOC-CS/RDC/pull/10).
- The original capacity recovery changes are from commit `7145b06f6479a54bd6775ca3d0c85935ee7afd2b`, retained separately in [draft PR #3](https://github.com/TOC-CS/RDC/pull/3). This branch does not edit those owning worktrees.
- Private ChatGPT Site v16 and installed RDC worker v0.1.0a8 are unchanged; do not infer deployment from this Git source or test log.

## Why this integration matters
Existing connected 30-pair ChatGPT echo benchmark: RDC p50 3,178 ms vs Desktop Commander p50 1,820 ms, both with 30/30 exact output. RDC performance priority: achieve at least 2x better p50/p95 over DC on terminal, coding, browser, search and analysis workflows, with no reliability regression. Gateway queue pickup p50 was 311 ms, claim-to-result p50 678 ms in 12 previous operations. The event-driven wake hint candidate replaces idle timer waits *only after* private Cloudflare Durable Object binding is deployed. The current site has not enabled that binding, so no real end-to-end speed gain has been proven.

The private Site can reject new calls with `gateway_busy` while its worker is connected and pending_operations=0. The separate capacity recovery patch safely attempts one admission retry after removing at most 32 expired, nonmutating, payload-free entries at proven retained journal saturation. It never erases active or unknown work, mutating operations, unexpired outputs or R2 references.

## Integrated behavior
1. Preserve original conditional D1 claim and operation identity.
2. Attempt first durable admission.
3. On rejection only, inspect retained record count. If it has reached configured limit, delete up to 32 eligible expired nonmutating payload-free rows and retry the *exact same* admission once. Reject full live backlogs/retained protected capacity.
4. If, and only if, a fresh durable admission succeeded (initial or safe retry), emit one optional device-only wake. Duplicate request-key recovery never sends a second wake.
5. After authoritative D1 result commit, emit a device+original-operation completion hint. The host reads the original D1 result and never replays a mutation.
6. Cap consecutive spurious queue wake hints and completion hints to three per request. After that, fall back to the original bounded database polling.
7. With no DO binding, the current polling-only behavior remains functional and safe.

## Verification scope and receipts
- Source merge conflicts were resolved in an isolated copy; no owner source modified.
- The individual source branches already passed their independent red-green tests.
- Combined gateway suite: 73/73 tests passed, 0 failed, 0 skipped.
- New focused integration test: a saturated journal is safely reclaimed, exactly one notification follows successful retried admission, duplicate recovery does not re-notify and original mutation identity persists.
- Node syntax and same-file source checks passed.
- Full Python suite completed with exit code 0: **486 tests run, 43 skipped, zero failed, in 135.001 seconds**. ResourceWarnings for unclosed SQLite database connections and expected simulated relay interruption messages remain visible in the saved log.
- No final private Site deployment, DO binding, rollback version, ChatGPT App or machine enrollment has occurred.

## Release blockers
- Existing private Site version and protected compatible rollback must be read back.
- Verify Cloudflare private Durable Object binding support, owner permissions, storage class, pricing and no unauthorized ingress.
- Integrate source/skills with the latest authorized repository cleanup, preserve supported prior features, and complete 3-platform CI on the exact new revision.
- Qualify real 30+ matched RDC/DC ChatGPT operations in each workload, alternating order, exact output, errors and p50/p95/p99. Exclude model think time.
- Resolve any live `gateway_busy` and verify post-deployment exact tool behavior using the connected @RDC app.
- Task-bound external floating preview with auto-clear remains fourth priority, not deployed by this integration.

**Do not activate Site v17 or replace the running worker solely on the basis of these source tests.**
