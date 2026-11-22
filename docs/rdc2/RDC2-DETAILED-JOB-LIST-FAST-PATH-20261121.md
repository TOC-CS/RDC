# RDC 2.0 detailed durable-job list fast path

Date: November 21, 2026. Development source only. Existing owner-private ChatGPT Site, live worker and original operation journal remain unchanged.

## Original read behavior

The old Store.jobs(limit) queried up to 100 original job IDs, then invoked Store.job() for each ID. Each job fetch opened another SQLite connection to read the saved job row, decoded its original spec, then opened another SQLite connection to read the original device_id. For 80 retained jobs this generated more than 160 separate database connections and inflated detailed job inspection, including the data used in the worker's full status output.

## Source change

Store.jobs(limit) now selects the bounded original job rows and original device identity through ONE database connection and builds the identical detailed records without additional database opens. Both Store.job(original_id) and Store.jobs() use the same pure _job_record decoder to preserve the original argv, cwd, timeout, client_key, original job ID, boolean truncated status, byte counts, exit code and state. No DB schema, original recovery identity, output bytes, approval record, process execution or no-replay behavior changed. The single-job Store.job() method continues to raise job_not_found on missing/expired IDs.

## Test-first verification

Four independent regression tests pass: the list opens one database connection regardless of result size, its entire output equals all original Store.job() records in stable order, single-job recovery and missing identity semantics are preserved, and queued/running/completed job status is read without mutating work.

An interleaved 60-operation real SQLite campaign used a disposable state with 80 original completed job records. Each trial returned the exact same 80 detailed records and original fields:

| Source-only detailed-list read | Original N+1 path | Single snapshot |
| --- | ---: | ---: |
| p50 | 56.032 ms | 0.696 ms |
| p95 | 62.667 ms | 0.774 ms |
| p99 | 79.425 ms | 0.858 ms |
| Correct original output | 30/30 | 30/30 |

Observed p50 speedup: 80.506x. The independent private receipt is under RDC-2.0-QA/rdc2-detailed-job-list-ab60-20261121.json. This improvement is source-only; it is not the end-to-end time of a ChatGPT tool call or proof the connected worker is updated.

The related status-summary count fast path uses bounded COUNT(*) reads, preserving the summary display cap and original approval expiration logic. Both changes retain the owner's 100-test-per-campaign maximum.

## Release limitations

Connected ChatGPT worker v0.1.0a8 and private Site v16 still need a separately verified protected replacement. The six required live speed gates, 30+ matched Desktop Commander comparisons, owner authentication, TLS/loopback limits and rollback remain open. Do not activate the held v17 inline-result migration to deploy these Python-only improvements.
