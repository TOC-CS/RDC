# Historical RDC v16 capacity recovery candidate
TOC Ministries | November 17, 2026
Status: SOURCE-ONLY FALLBACK RESEARCH. NOT DEPLOYED. NOT CERTIFIED AS EXACT LIVE SITE BINARY.

## Purpose
Live connected RDC v16 still reports online with zero pending operations but rejects new RDC terminal calls as gateway_busy. Current published v17-based source repair PR #3 has 3-platform CI success but its live deployment requires protected compatible rollback approval.

This alternative starts from the separately preserved historical v16 source commit 3001050ba702e8a7309f0ab190585d627c1a7bb4, which matches the project's pinned v16 fixture. It retains the historical R2-only result store, legacy D1 schema and tool behavior. It does not activate or introduce v17 inline results and requires no new schema migration in this source diff.

## Minimal behavior
On an actual failed admission, verify the retained journal row count is at maxOperations. Only then delete at most 32 result-free expired nonmutating records in completed/expired state. Retain every mutating request identity, pending or unknown outcome, R2 result reference and unexpired result. Retry conditional admission once using the same principal, device, request key, SHA and resource limits. Active backlog and byte-capacity limits remain enforced.

## Test-first evidence
The isolated Node gateway fixture reproduced a maxOperations refusal with zero live queued work. The added test failed before code change; after code change, both targeted tests passed. The entire gateway suite completed 34 passed, zero failed. Historical Python suite completed 364 tests, zero failures and 26 expected skips. Isolated vinext production build completed; lint reported 0 errors and one existing image warning. No credential retrieval, worker restart, Site migration, or live App traffic were performed by the spike.

## Caveats and release selection
This is a second, narrower source option. It has not been confirmed byte-for-byte against the actual owner-private live Site deployment; a matching historical source fixture alone is insufficient. It must not be rolled out on a Site that has processed any v17 inline-only results, because v16 cannot read those records. Independently read the live Site version and data state, preserve a compatible inactive rollback version, verify the same private App/Site ID and DB/BUCKET bindings, and obtain required release authorization before any activation. If the actual capacity problem is result-byte or request-byte saturation rather than aged journal rows, this limited patch rightly preserves the limit and will not fix the refusal. Confirm cause with owner-only diagnostic when available. No performance superiority versus DC is established.
