# RDC 2.0 bulk-result parity: private R2-backed source candidate

Date: 2026-11-19 America/Chicago
Project: TOC Ministries, TOC-CS/RDC.
Base source commit: 20269f19e9b9a68bb4c60fdb8f81ea90d8393da8 (RDC 2.0 event-driven foundation).
Branch: rewrite/rdc-2-bulk-results-20261118.
Status: ISOLATED SOURCE CANDIDATE, NOT DEPLOYED. Source remains off by default.

## Product need
The first private RDC 2.0 transport used an inline Durable Object result limit of 256 KiB for speed and durability. The existing RDC v1 worker supports up to 12 MiB output. A fast transport that silently shrinks that limit would fail feature-parity acceptance.

## Clean design
- Preserve the previous fast 256 KiB inline path, original owner identity, original operation digest, atomic claimed/unknown completion, long-lived local original-action journal, and private WebSocket notification.
- Results larger than 256 KiB and up to 12 MiB use an original-claim authenticated HTTPS POST to the exact same owner-private Site route /v2/device/result. The Site verifies the existing paired device credential before reading any large request. It forwards only to the privately bound V2 Durable Object using the existing private service secret. All network requests enforce TLS and disallow redirects.
- The V2 actor validates exact result digest, claim token, original request digest and bounded MCP result envelope before writing the value into the existing Site R2 BUCKET under the dedicated rdc2-results/<original-operation-id>/<sha256>.json prefix. Only AFTER R2 durability does the actor atomically commit the original V2 SQLite operation row as completed with a result key, digest and size. Same original key and result returns a duplicate receipt, never an execution retry.
- Private recover requests perform exact owner authorization before retrieving the original R2 object and verifying the stored SHA-256. A missing, mismatched or inaccessible object fails closed, never requeues the operation.
- Expired external result references are bounded and deleted from R2 only after the stored TTL has passed. Nonexpired/private results remain, original mutation tombstones remain. If R2 deletion fails, expiration stops without clearing the reference.
- The V2 journal schema adds nullable result_key with an idempotent SQLite table-info migration for the earlier UNRELEASED V2 candidate. The migration preserves all original completed inline result rows.
- Over 12 MiB still produces an explicit bounded result_too_large error under original claim. Future enhancements must separately examine very large output streaming, compression, CPU/memory costs and Cloudflare R2 account budgets.
- Exact Site environment flag RDC2_RUNTIME_ENABLED=1 and previously opt-in private V2 Durable Object binding remain required; default Site and installed v1 relay/worker remain unchanged.

## Adversarial and regression evidence
- Red-green focused Node tests for large R2 result, forged claim/digest before storage, missing private binding, missing object recovery, timed expiry and old schema migration.
- Red-green private Site edge tests for original device-key auth and disabled default.
- Red-green 5 Python tests for private owner Site HTTPS upload, original id/hash, refused/temporarily unavailable response handling with no original action replay, missing config and >12 MiB output.
- Additional 16-concurrent-duplicate completion regression exercised identical R2 result acknowledgments without duplicate original execution.
- Combined Node and Python test counts are recorded in the test logs after final changes. The previous full Python run after adding bulk client tests passed 502 tests, 43 skipped, zero failures, in about 139.5 seconds.
- Real local Miniflare/workerd with separate persistent SQLite Durable Object and R2 storage: a 600,093-byte result was durably written, duplicated as the same original completion, recovered after a real local Workerd restart, and never re-executed (10 synthetic calls, approx. 310 ms total including runtime setup).
- The external hostile runner under RDC-Development/checkpoints/rdc2-hostile-regression-20261118 completed 14 checks with unauthorized requests, forged SHA, malformed frames, 128 concurrent operations, durability and bounded queue. It is NOT included in this source branch or deployable package.
- Baseline actual connected RDC live median 3178ms remains unchanged, because this V2 implementation has not been released. LOCAL processing latency samples cannot establish full ChatGPT speed.

## Release blockers and independent review
The exact owner-private Site release authority, protected rollback, host MCP 2026 protocol parity, actual account-specific Cloudflare R2 cost/provisioning, real worker and browser/coding feature parity, true 30+ live samples for all five hard speed metrics and cross-platform CI on the new exact SHA are still OPEN. No production deploy or migration is authorized by passing these isolated tests.

Independent review request: verify the original claim/storage/ACK ordering, failure behavior between R2 PUT and DO SQLite commit, missing blob handling, bounded expiry, old V2 schema migration, no public ingress, no secret/data logging, no replay and user requirements. Return REWORK if any required guarantee is unproven.
