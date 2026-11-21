# RDC 2.0 Superpowers and REA speed trace, November 20, 2026

Original owner branch. Superpowers using-superpowers, systematic-debugging, brainstorming, test-driven-development, writing-plans, verification-before-completion applied. The historical REA 6.9.0 static evidence analyzed the seven selected shipped Desktop Commander 0.3.1 sources. That source shows a persistent Node MCP client and guarded Realtime notification, whereas deployed RDC v1 still uses its own polling-based Cloudflare D1 gateway. Hosted DC service internals were not examined.

## Actual trace hierarchy

Current live ChatGPT RDC worker 0.1.0a8 and Site v16 had three correct matched echo calls at p50 2932ms versus Desktop Commander p50 1511ms. RDC local durable job length 89-106ms. The connected user-facing speed gap remains outside local command execution. Three pairs do not satisfy the required 30-pair acceptance.

New V2 source revision 5ca6349 adds bounded private monotonic same-process phase metrics to the standalone gateway. Durable IDs and schema did not change. RED source test suite: 13 cases, 3 expected missing-feature errors. GREEN: 13/13 passed, followed by separate 100/100 core and 16/16 release-policy regressions.

The exact-source Python standalone V2 gateway ran only on isolated VPS loopback port 18790 and was reached through an authenticated SSH tunnel from the authorized iMac test worker. Source archive checksum and state were kept private. 30 correct original terminal commands, 31 total MCP calls including one owner-only metric read.

| V2 stage | Median |
| --- | ---: |
| Complete actual MCP terminal call | 151.279 ms |
| Gateway monotonic admission-to-claim | 17.479 ms |
| Gateway monotonic claim-to-durable-result | 104.540 ms |
| Local original durable job | 40.311 ms |
| Gateway ASGI send call | 0.216 ms |

The second independent 30-command source-only trace measured total MCP p50 159.079ms, gateway queue p50 20.451ms, claim-to-result p50 111.491ms, worker relay handle p50 80.722ms, and result submit/ACK p50 29.723ms. These are different clock domains and should only be joined by original operation ID; never report server send time as actual notification delivery. Raw private evidence: RDC-2.0-QA/rdc2-rea-monotonic-mcp-terminal30-20261120.json and rdc2-rea-relaystage-mcp-terminal30-20261120.json.

## Measured candidate: fast inline terminal completion

The existing RDC Python worker polls SQLite every 10ms during the first 200ms after starting an original durable terminal command. A 3ms interval reduces scheduling delay without moving command execution into the MCP process, changing the original journal, replaying work or affecting longer-lived 40ms wait polling. TDD initially failed both precise-cadence tests; after the small code change, 2/2 passed.

A separate 60-operation, alternating 30-versus-30 real durable shell command benchmark in a disposable workspace showed 60/60 exact original outputs and completion statuses:

| Real source-only local terminal response | 10ms baseline | 3ms candidate |
| --- | ---: | ---: |
| Median | 31.552 ms | 31.505 ms |
| p95 | 45.236 ms | 36.256 ms |
| p99 | 45.667 ms | 38.274 ms |

The observed median is effectively unchanged, but p95 improved about 19.9% in the isolated campaign. A test launcher initially imported the older installed RDC and failed before running any benchmark operations; the corrected isolated source path was verified before executing the 60 actual commands. No installed production worker was modified. Source-only measured improvement does not establish ChatGPT connected speed.

The original-output worker I/O regression passed 12/12, full capped V2 source suite 100/100, release policy 16/16, and monotonic trace 13/13. All test campaigns individually respected the <=100 operations ceiling.

## Release and next engineering gate

The standalone gateway remains an isolated, single-owner beta; public TLS/workspace entitlement, private authenticated V2 ChatGPT connector, exact deployed source and protected rollback are not verified. Old Site v16/worker 0.1.0a8 must stay intact. Final acceptance needs 30+ correct live samples for each absolute metric and 30+ alternating matched RDC/DC correct operations, with a 2x RDC median speed advantage. Secure MCP Tunnel can be considered only when account/workspace association, permissions, private credential handling and plugin setup are available. Do not claim source-only millisecond results met public ChatGPT host targets.


## Eight-concurrent-job workload, independently verified

A separate 64-operation disposable project campaign alternated eight batches of eight short terminal echo jobs, with four batches per variant and no more than eight simultaneous original durable jobs. Each job retained its own idempotency key and exact output. Both old 10ms polling and new 3ms polling completed 32/32 correctly with no missing results or capacity errors. This stress benchmark was scoped entirely to a disposable QA state, not the production worker.

| Real local eight-way concurrency | 10ms baseline | 3ms candidate |
| --- | ---: | ---: |
| Median end-to-end durable job response | 62.471 ms | 56.689 ms |
| p95 | 91.050 ms | 73.105 ms |
| p99 | 120.018 ms | 75.709 ms |
| Correct results | 32/32 | 32/32 |

The candidate reduced observed median by 5.782ms (9.3%) and p95 by 17.945ms (19.7%) under this bounded load. Full private evidence: RDC-2.0-QA/rdc-jobs-inline-poll-concurrent64-20261120.json and the source harness in the QA folder. These gains are local and do not imply ChatGPT-hosted speed acceptance. The owner-mandated 100-total-operations limit was respected.
