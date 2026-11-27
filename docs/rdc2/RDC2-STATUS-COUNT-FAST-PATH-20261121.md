# RDC status summary count fast path

Date: November 21, 2026. Scope: independently owned source branch, no production worker deployment.

## Source problem

The original RDC system status summary used Jobs.list() followed by Store.jobs(), which first selected up to 100 job IDs, then invoked Store.job() for every ID. Each job decode also opened the SQLite state to read the same device ID. The summary then loaded up to 100 pending approval rows and decoded their JSON arguments, only to return counts. A busy worker with 80 retained jobs could therefore perform hundreds of unnecessary SQLite opens for a single status request.

## Change

Store.job_count() returns the bounded count in one SQLite query. Jobs.count() retains the original stale-job reconcile step, which marks expired queued/running jobs interrupted rather than pretending they completed. Store.approvals_count() uses the same authoritative expiration UPDATE predicate as the existing approvals list, then reads the pending count without deserializing private approval arguments.

Engine.status(summary=True) now calls these counts, preserving the original 100-item display cap. Engine.status(summary=False) continues loading and returning the detailed job, approval and credential metadata exactly as before. No network, authentication, job execution, mutating-tool replay or journal format changes were made.

## Evidence and limitations

Four focused test-first source regressions passed 4/4: summary avoids list materialization, capped counts match existing listings, pending approval expiration stays authoritative, and stale job reconciliation and detailed payload remain unchanged.

A separate 60-operation alternating real SQLite comparison using a temporary database with 80 completed jobs and 20 approvals (18 still pending) returned all counts correctly, 30/30 for each implementation:

| Source-only count query | Original list path | New direct count path |
| --- | ---: | ---: |
| p50 | 58.291 ms | 1.093 ms |
| p95 | 68.726 ms | 1.274 ms |
| p99 | 72.163 ms | 1.308 ms |
| Correct calls | 30/30 | 30/30 |

This is a measured 53.331x source-level median improvement for the isolated test workload. It does not assert a 53x reduction in end-to-end ChatGPT system-status latency or in terminal execution. Startup, transport, host and live worker version remain separate. Private evidence is retained in RDC-2.0-QA/rdc2-status-fast-counts-ab60-20261121.json. The source change requires a future authenticated, rollback-safe worker release before it affects production.
