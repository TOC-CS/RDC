# RDC 2.0 bounded terminal status polling, November 22, 2026

**Scope:** development-only source in `publish/rdc2-speed-20261121`, against an authorized isolated iMac. The existing owner ChatGPT connection, private Site, v1 worker, VPS processes and public release are unchanged.

## Performance change

`Jobs.run` now polls `Store.job_state` for the lightweight status column instead of repeatedly decoding a full durable job record and reopening the device-identity table. It reads the detailed original job once on completion or timeout. An adaptive polling schedule checks about every 3ms for the first 45ms of a short job, 15ms up to 200ms, and 40ms thereafter. For older minimal test fixtures, an explicit full-record fallback preserves the original behavior. The original durable job identity, exit code, output snapshot, no-replay behavior, cancellation, timeout and recovery contract remain in place.

The one-second simulated wait was measured at 88 status snapshots before the adaptive schedule and **47** afterward, a **46.6%** reduction in observed checks. This is a per-job database-load gain, not a network speed result.

A matched source-only 15-vs-15 alternating benchmark, before adaptive backoff, returned 15/15 correct original terminal outputs per source with p50 **36.895ms** original and **36.924ms** lightweight status. After adaptive polling, another **20/20** correct local original-output commands had p50 **37.007ms**, p95 **42.988ms**. These figures do not demonstrate a meaningful short-command latency improvement. The gain is reduced status-query work while retaining short-job latency. Only isolated local results were measured; ChatGPT end-to-end latency remains unverified.

## Test budget and regression results

- Three test-first source cases were executed before the change (expected failures), then three passed after the first code change.
- 30 original terminal commands in interleaved baseline/candidate samples all returned exact output, job ID and exit status.
- 12 worker-I/O tests passed, and the 4-case terminal budget suite initially exposed a pre-existing one-second excessive-read failure (88 vs <=50). After adaptive backoff all 4 passed.
- The 11-case core suite initially failed to import due to missing `jsonschema` in system Python. Running the exact suite through the project virtual environment passed all 11.
- Three focused new cases passed again; another 20 original-output terminal commands passed; one one-second fixture measurement counted 47 checks.
- **95 checks/trials accounted for in this bounded development campaign**, including expected red tests, unsuccessful suite import, repeated verification and benchmark operations, under the mandatory 100 ceiling. Historical broader regression coverage is not implied.

The previous worker `Store` no-schema-init optimization was explicitly **rejected and reverted** after slower p50 (38.048ms original versus 52.650ms candidate, interleaved 10/10 each); see the separate private QA rejection receipt. It is excluded from this change.

Private receipts: `RDC-2.0-QA/rdc2-jobstatus-fast-interleaved15-20261122.json`, `rdc2-jobstatus-after-adaptive20-20261122.json`, and `rdc2-jobstatus-focused-regression-20261122.log`.

## Release gates

This is source-only. The connected ChatGPT App/plugin was separately updated to owner-private skill version **1.0.31**, without switching its existing binding or installing the new V2 worker. The required live ChatGPT-connected correctness, end-to-end latency, actual device notification, secure pairing, protected rollback and 30+ matched Desktop Commander performance gates remain open. Do not merge/publish or migrate the protected connection from this result alone. No paid OpenAI API calls or purchases were made.
