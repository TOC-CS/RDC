# RDC expiry maintenance query batching
TOC Ministries | November 17, 2026 | source-only isolated development

## Observed need
Ten paired ChatGPT echo calls completed correctly with RDC median 3470 ms and Desktop Commander 1884.5 ms. REA shows RDC uses D1 polling and durable queueing while DC can signal via Realtime. Exact host timing attribution is unverified; this candidate targets one narrower overhead source, recurring D1 maintenance round trips.

## Existing behavior
The cloud gateway clean(env) function unconditionally performs two sequential UPDATE statements during each ordinary request and worker poll to expire queued requests and mark overdue claimed operations unknown. These updates preserve no-replay identities and apply precise TTL conditions. Each statement is a potential separate D1 network round trip.

## Options considered
A. Skip cleanup for most calls: rejected because stale queue capacity and uncertain operation recovery can drift.
B. Cache/coordinate cleanup throttling across server instances: rejected because isolate-local state cannot establish global freshness or preserve durable correctness.
C. Combine the two disjoint conditional updates into one CASE-based UPDATE: selected. Keep exact same TTL predicates, request_json/request_size nulling on queued expiry, and claimed-to-unknown state. Keep all existing result/R2 cleanup and terminal delivery paths intact.

## Test and release boundaries
First add a failing test asserting a single gateway-operation UPDATE under mixed queued/claimed expiry, plus exact state, request-body retention, and no-redelivery safety. Then minimally implement the combined SQL and verify Node gateway full suite, Python full suite, build/lint and cross-platform CI. Measure D1 UPDATE statement count; avoid claiming tool-boundary latency improvement without a new live deployed matched test. No active owner worktree, private Site, D1/R2 data, worker or BandMates changes. Publish as isolated source review only.

## Email-driven CI feedback
The November 17 GitHub notification audit distinguishes actual Windows CRLF/byte-hash test failures from repeated macOS no-run cancellations. See docs/releases/RDC-GITHUB-ACTIONS-FAILURES-REA-20261117.md and the private 22-run inventory checkpoint. This isolated performance change maintains exact queued/claimed unknown-state semantics while reducing one D1 UPDATE per cleanup. It does not modify owner feature branches to replay already-fixed Windows regressions.
