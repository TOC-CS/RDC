# RDC 2.0 Source-Qualified Real MCP Status and Job Listing A/B

Date: November 21, 2026. Owner-authorized single-Mac QA, no OpenAI Platform API spending. This is not the current ChatGPT-connected v1 release.

## Source qualification

Two distinct, newly initialized local worker states used original QA-only private token files, separate loopback MCP listeners and the same restricted QA workspace. The baseline process loaded the original installed RDC alpha source, and the candidate process loaded the current RDC speed-owner source. Their actual process working directories were inspected via the operating system, and their imported worker source file SHA-256 digests differ as expected.

Each state contained the same 80 synthetic completed jobs and 20 synthetic approvals, 18 not yet expired. All original durable job details were identical except for the intentionally distinct paired device identities. Both workers required authentication and returned HTTP 401 to unauthenticated MCP probes. Neither worker could access the owner production private application data through its configured workspace roots.

The first status comparison was disqualified: despite a different PYTHONPATH, both processes had inherited the same candidate working directory, so Python -m rdc imported the candidate source in both. That unqualified receipt was retained privately under a filename ending in source-invalid.json. The baseline worker was restarted from the original source directory and the verified 60-operation campaign was run fresh. The entire 30-versus-30 test then used distinct verified source roots and identical data. Never cite the disqualified first trial as a speed or regression result.

## Actual official MCP status calls

The 60-operation campaign kept authenticated MCP clients persistent and alternated baseline/candidate in batches of five. Each returned the correct original status with job_count 80 and pending_approvals 18.

| Real local MCP system status | Original worker | Optimized worker |
| --- | ---: | ---: |
| p50 | 63.404 ms | 4.169 ms |
| p95 | 85.580 ms | 4.986 ms |
| p99 | 92.164 ms | 6.616 ms |
| Correct responses | 30/30 | 30/30 |

The optimized source reduced local end-to-end MCP status latency 15.208x at the median for this retained-state workload.

## Actual official MCP detailed job list calls

An independent 60-operation campaign alternated the exact same two workers for the detailed rdc_job_list tool, limit 80. Every result was compared against the original complete 80-job list after removing only the device identity that must differ between independent states. The original status, arguments, saved command identity, job IDs, exit codes and retained fields all matched.

| Real local MCP detailed job list | Original worker | Optimized worker |
| --- | ---: | ---: |
| p50 | 64.734 ms | 5.060 ms |
| p95 | 73.626 ms | 6.977 ms |
| p99 | 88.973 ms | 8.067 ms |
| Correct original lists | 30/30 | 30/30 |

The optimized source reduced local end-to-end MCP detailed job-list latency 12.793x at the median for 80 retained completed jobs. The worker tool catalogs differ because other source features were added between revisions, but both tested tool names and payload identities were verified.

## Source of improvement and limits

The old worker unnecessarily loaded 100 detailed records and their arguments for status summary counts. The new Engine.status(summary=True) uses Store.job_count and Store.approvals_count with original expiration and stale-job reconciliation semantics. The detailed Store.jobs method now returns the original bounded job records via one SQLite connection instead of an N+1 sequence of independent connections, while Store.job(original_id) retains its historical recovery semantics.

Both runs used real official MCP messages over localhost through separate Python stdio bridges. They exclude cloud model inference, ChatGPT host scheduling, ChatGPT Plugin transport, VPS TLS and remote network latency. Initial MCP connection/list overhead was outside the request percentile samples and was similar for both variants. This workload includes 80 synthetic completed records, so its speedup should not be generalized to an empty journal or every user task.

Each 60-operation trial independently obeyed the 100-total-tests-per-campaign requirement. No original mutation was replayed, no production relay or Site was changed, and no OpenAI API paid credits were consumed.

## Private evidence and acceptance

Private receipts under RDC-2.0-QA:
- rdc2-actual-worker-status-ab60-20261121.json, source-qualified.
- rdc2-actual-worker-jobs-ab60-20261121.json, source-qualified.
- rdc2-actual-worker-status-ab60-20261121-source-invalid.json, intentionally disqualified.
- rdc2-status-fast-counts-ab60-20261121.json, source-only count benchmark.
- rdc2-detailed-job-list-ab60-20261121.json, source-only detailed-list benchmark.

The original ChatGPT-connected v1 worker 0.1.0a8 and its private Site v16 remain untouched. The six mandatory live performance release gates remain OPEN until a protected V2 ChatGPT connection and at least 30 correct matched Desktop Commander comparisons independently verify latency, owner pairing, TLS/loopback, actual device delivery and rollback. The held v17 inline-result migration remains on HOLD.
