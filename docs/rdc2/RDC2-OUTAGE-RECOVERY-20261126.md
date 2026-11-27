# RDC 2.0 post-outage recovery verification

November 26, 2026. Development candidate only; existing production Site and worker preserved.

## Defects reproduced and corrected

The earlier standalone gateway returned expired/unknown states dynamically but retained all queued and claimed rows in its live capacity count. A full stale queue could permanently refuse new requests after an outage. Observed queued expiration is now durable, and uncertain claims are marked with an additive unknown_since_ms column and excluded from the live queue count. The original physical claimed state, claim ID, request key and request digest remain intact. A valid late result for that exact claim may complete; no uncertain request is requeued. Once observed, expiry/uncertainty cannot be reversed by a backward clock adjustment.

Retained inline and bulk results are checked against their stored original SHA-256 digest. Missing, invalid UTF-8 or altered data fails closed as result_unavailable. The original operation remains retained and cannot be replayed.

The migration adds only a nullable column and a partial live-queue index. Existing SQLite databases can be opened without removing their original records. A disposable journal was created by the exact prior gateway module from d2c1717, then opened by this candidate and the previous reader again. The earlier reader accepted the exact authenticated late result, preserved the expired request, and never reclaimed it. The old reader still has its pre-existing stale-capacity behavior for unresolved physical claimed rows; this is a scoped backward readback/completion test, not a complete live deployment rollback approval.

## Verified evidence

- Five deliberate red regression cases reproduced the earlier capacity, expiry durability and inline-result integrity defects.
- Six new outage-recovery cases passed, including additive schema upgrade, exact late result, duplicate identity and backward clock behavior.
- Expanded gateway/relay/loopback/catalog regression: 63/63 passed with no skips.
- Release-policy tests: 17/17 passed.
- Actual isolated post-outage gateway readback: 150 existing completed records retained, two exact original results recovered through the authenticated MCP client, no new gateway operation, and restart-invalidated monotonic timings remained null.
- Actual restored isolated worker: 30/30 correct terminal commands, p50 226.602ms and p95 303.037ms; 30/30 correct one-request two-file coding results, p50 20.848ms and p95 24.883ms. The preview regression suite was running concurrently, so these are observed recovery timings, not a controlled speed comparison.

The actual recovered worker/gateway readback used the existing isolated QA state and November 24 development source, not the newly migrated candidate. The new schema and exact prior-reader test used disposable state. No production database migration, production process replacement, remote HTTPS/tunnel authorization, or paid OpenAI API use was performed. The six hosted ChatGPT speed gates remain open.
