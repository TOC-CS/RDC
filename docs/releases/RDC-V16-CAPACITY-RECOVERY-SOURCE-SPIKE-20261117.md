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

## Second scoped improvement: read-only emergency capacity status
Added an authenticated rdc_gateway_capacity_status tool in the isolated v16 source candidate. It does not enter the device queue, works even if normal dispatch hits gateway_busy, and has no mutating capability or access to operation bodies. A single owner-scoped database aggregate reports retained record count and limit, queued/claimed backlog and limit, unknown count, read-only versus mutating counts, stored request/result byte totals and limits, and conservative next-result reservation pressure. The output contains no owner IDs, operation IDs, requests, result bodies, keys, secrets or raw tokens. Source code never disables admission limits or replays uncertain work. The gateway's owner authorization still guards the call.

The two tests were written and run RED first, with both denied at HTTP 400 before the tool existed. After adding its descriptor, owner-only handler and aggregate, both passed; the full gateway suite passed 36/36. The diagnostics are SOURCE-ONLY until the existing private Site is updated by its authorized owner through a supported release path. This addition changes the advertised gateway tool list but does not alter the R2-only result schema.

## Full local verification after adding read-only diagnostics
The full historical worker Python regression suite completed 364 tests with zero failures and 26 skips in 166.487 seconds, source-only test environment. Gateway Node tests 36/36 pass. Vinext production build completed, compiled output contains the new tool marker, and lint reported zero errors and one existing image warning. Git diff validation passed.

A sanitized, source-and-compiled private Site staging archive was prepared at ~/RDC-Development/checkpoints/rdc-v16-capacity-spike-20261117/RDC-V16-CAPACITY-DIAGNOSTIC-SOURCE-AND-BUILD-20261117.tar.gz, SHA-256 0cdd9f1a1d81ad148806d8b9a52a6b8889816d363c7056e732c577b83ee391ad. It contains no .env, .npmrc, .git, node_modules, .wrangler or private-key/database filenames. An archive is NOT a deployed inactive Site version, so live release gates remain open.

Hosted macOS qualification of the prior exact source commit was inconclusive: five GitHub Actions attempts were canceled before runner assignment with no test steps, while Ubuntu and Windows both passed. Do not label those macOS cancellations as code failures or hosted macOS qualification success.
