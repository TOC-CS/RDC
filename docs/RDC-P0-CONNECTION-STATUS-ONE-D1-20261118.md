# RDC P0 connection status: owner-bound single D1 read

Date: 2026-11-18
Branch: `perf/rdc-status-single-query-20261118`
Source base: `9d6701c` (combined isolated P0 release candidate)
Deployment: **NOT DEPLOYED**. The existing owner-private ChatGPT Site and worker remain unchanged.

## Scope

An established owner's `rdc_connection_status` formerly issued a D1 owner SELECT and then a D1 batch containing the liveness SELECT and pending COUNT. The new path uses one read-only D1 statement that requires the exact stored owner principal and returns liveness plus pending count. That reduces the warm status pathway from **two D1 network trips to one**, with the same output contract.

First-time private owner enrollment, prohibited bootstrap, and an unauthorized secondary account still take the original verified owner() path. A mismatched principal receives HTTP 403 without any device state disclosure. Missing device rows return offline. Expired queued and stale claimed rows are excluded; no status call mutates the durable journal or replays work.

## Verification

- Red/green regression: the new one-query owner-bound test failed before the change (three prepared SQL statements) and passed after (one).
- Gateway regression suite: **111/111 passed, 0 failed** after adding first-owner enrollment, offline-state and unauthorized-owner privacy coverage.
- `node --check` passed for modified gateway and tests.
- `tsc --noEmit --pretty false`, targeted ESLint, and `git diff --check` passed.
- Default Site build passed. Explicit opt-in `RDC_ENABLE_WAKE_BINDING=1` Site build passed with one `RDC_WAKE_CHANNEL` Durable Object binding and the `rdc-wake-sqlite-v1` migration.
- Existing RDC virtual environment full Python suite: **487 tests, 43 skipped, zero failures** (`/tmp/rdc-status-single-query-python-venv-20261118.log`).
- Full Site ESLint finished with 0 errors and 1 pre-existing `no-img-element` warning in `app/page.tsx`.

## Mandatory release gates

This is a **source-only speed optimization**, not a live p50/p95 result or permission to deploy. The owner requires 30+ verified live samples for each of five speed metrics, including terminal <=800 ms; queue pickup <=50 ms; claim-to-result <=150 ms; local notification <=1 ms; and one-call coding context <=800 ms. The protected compatible rollback, correct private Site release route, provisioned wake binding, and exact worker/site revision readbacks remain mandatory. No additional host privileges, broad file permissions, or deployed Site changes were requested.
