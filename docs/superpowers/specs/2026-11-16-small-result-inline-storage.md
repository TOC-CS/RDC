# RDC small-result storage optimization (candidate v17)

## Evidence and goal
Live owner-only D1 timings, latest 12 completed terminal calls on v16: queue pickup p50 350 ms, claim-to-completed p50 839.5 ms, total gateway p50 1190.5 ms. Claim-to-completion includes local worker execution (~60 ms from separate timings), HTTP upload, R2 PUT and D1 completion. Current gateway PUTs every result to R2 even if a command responds with only a few hundred bytes; recovery GETs R2. Objective: safely eliminate R2 PUT/GET for *bounded small results* with no additional requests, changed permissions, uncertain mutation replay, or user-visible output semantics. Real end-to-end speed benefit must be measured after deployment, not assumed.

## Approaches
1. Preferred: new nullable `result_inline_json` TEXT column in D1 for at most 8192 UTF-8 bytes of validated MCP result JSON. Existing large results still write R2. D1 completion remains atomic with result storage, avoiding orphaned R2 objects for inline results. Migrate additively using Drizzle so previous code can ignore the new column.
2. Rejected: storing result JSON in `result_key` with prefix. That field is a R2 locator and may appear in diagnostic logs; leaking private output through a formerly metadata-only field is unsafe.
3. Rejected: larger R2 cache or speculative polling, which does not remove extra object-storage operations and can increase cost.

## Retention and security
- Both inline and R2 results obey the existing respective TTLs. Cleanup must clear `result_inline_json` and size alongside R2 deletion and retain identity tombstones for idempotency.
- Terminal operation rows must not be retired while a retained inline result is still present; no replay on lost ACK.
- Never add result payloads to owner-only timing diagnostics, headers, logs, metrics, or public responses except the existing authorized normal operation-result path.
- Scope is only the private gateway and a safe additive schema migration; local worker/relay/browser preview/permissions/credentials and BandMates are unchanged.
- Cap 8 KiB inline; R2 remains mandatory for large JSON/images and after upload failure recovery. Preserve existing 12 MiB result limit and 512 MiB reservation bounds.

## Verification
Red/green unit tests for compact result R2-put avoidance, exact authorized recovery, TTL retirement, duplicate and conflicting uploads, large-image R2 fallback, unexpired retained rows, and existing owner principal guards. Test additive migration through real SQLite D1 fixture. Full worker/gateway suites, build, lint, Git diff, hosted macOS/Linux/Windows CI, then existing-private-Site-only staged deploy and live smoke/phase comparison. Never claim faster than Desktop Commander without actual comparable evidence.
