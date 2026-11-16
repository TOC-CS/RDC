# Terminal completion performance candidate — November 16, 2026

Local candidate only. No deployed worker or BandMates session was changed. The 2x faster-than-Desktop-Commander cloud target remains unverified.

## Measured change

The detached supervisor now wakes when output capture finishes instead of always sleeping 40 ms. If the output pipe closes before the child exits, the supervisor keeps its 40 ms control interval to avoid spinning. The inline collector polls every 10 ms for its first 200 ms, then returns to 40 ms. Durable process ownership, permissions, idempotency, output capture, cancellation and recovery routes are unchanged.

Four alternating-order rounds used disposable source copies and profiles, 10 measured commands per method/variant/round, and 3 warmups per method per round. Both variants used the same instrumented harness; only `rdc/jobs.py` and `rdc/worker.py` differed. Baseline was restored from local commit `3461af5`, whose tree is identical to public commit `8a4a86e788be9b91eb8143d4d475c10e56524842` (`40a7e3da3061d5087a22e8e2007a8bf6a8fc4eed`). The public commit is used below so the command also works in a fresh GitHub clone. The worker/gateway test suites finished before timing began. All 160 measured commands and 48 warmups produced exact expected output; all 80 fast-path measured commands completed in their initial local call.

| Local operation | Baseline p50 | Candidate p50 | Baseline p95 | Candidate p95 |
|---|---:|---:|---:|---:|
| Start + status/output | 88.614ms | 63.581ms | 91.268ms | 75.638ms |
| Single-call job_run | 96.707ms | 59.806ms | 99.214ms | 65.111ms |

Fast-path p50 fell 38.16% and p95 fell 34.37%. Phase medians identify the improvement: worker lifetime 48.166→22.758ms; result collection 21.383→8.369ms; detached startup 26.291→26.895ms. Worker lifetime includes process launch, capture and supervision; it is not an isolated shell-runtime measurement. Phase timestamps use wall clocks; total latency uses a monotonic clock. With 40 observations per method, tail estimates remain preliminary.

[Raw samples and complete baseline/candidate source hashes](rdc-terminal-performance-matched-2026-11-16.json). Reproduce using:

```sh
python benchmarks/terminal_performance_compare.py --baseline-ref 8a4a86e788be9b91eb8143d4d475c10e56524842 --rounds 4 --trials 10 --warmups 3 --output /tmp/rdc-terminal-performance.json
```

## Verification

- Full worker suite: 360 tests passed in 122.706 seconds. Gateway: 28 tests passed. Logs remain under `/private/tmp/rdc-performance-full-worker.log` and `/private/tmp/rdc-performance-gateway.log`.
- New regression suite: 4 passed. The initial-collection budget failed before the fix at 40 ms versus its 20 ms limit. A deliberately naive event-wait mutation failed the EOF-before-exit test with 703 heartbeat writes during a 0.30-second command; the guarded implementation passed and preserved the final child side effect.
- Existing full-suite contracts cover nonzero exits, bounded output, stdin, timeout/cancel, idempotency, permissions, and survival across Engine disconnect. The parent-owned terminal test cleanup may be edited separately after suite import; rerun that file if changed.
- An isolated direct-local concurrency probe returned status in 2.548 ms and completed a second short job in 58.326 ms while the first inline call remained waiting. Cancelling the long job returned `cancelled` with its existing stdout preserved. These are individual functional observations, not concurrency latency percentiles.

## Remaining cloud bottleneck

The actual relay main loop, exercised with a disposable journal and fake gateway/worker, delayed an already queued status dispatch by 1502.532 ms behind a 1500 ms inline wait. Both operations were delivered once. The primary relay still awaits each operation before claiming the next; only activity observations have a separate lane. `wait_ms=0` or the existing job-start path avoids an inline wait for known long operations. Gateway polling and relay idle backoff can add further delay. This change does not alter those scheduling semantics. Live cloud benchmarks and BandMates acceptance remain open.

## Source identity

[Validation results, log hashes and source hashes](rdc-terminal-performance-validation-2026-11-16.json). Candidate SHA-256:

| File | SHA-256 |
|---|---|
| `rdc/jobs.py` | `4b958c39520f056912254147864c2685a83d028efea31137b5a0c6819f8ab2f9` |
| `rdc/worker.py` | `02e3cd457bee48db52c66110b4f2b45995dbb61f4eb7ff2bdb13c0b5b66c3294` |
| `tests/test_terminal_performance.py` | `947d9599dd80247ef58d28025d4af40e0a2ddd9d45b250ed35a9ecdd3609ccf2` |
| `benchmarks/terminal_fast_path.py` | `9ddeef160003f15c88ad1bc0ab92499b53d260965efe0f25a7a4a642a44db5c4` |
| `benchmarks/terminal_performance_compare.py` | `5c36d2e2beb3442cd6730ff4c50abf23206e3d9afa51c0716de1ad12b9833b28` |

## Live cloud comparison and offline acceptance

The running legacy RDC cloud route and Desktop Commander were compared in 30 alternating-order pairs on the same Mac. The live worker and gateway remained unchanged throughout the comparison; these results do not measure the candidate single-call cloud route. Timing includes tool orchestration and excludes model thinking. RDC includes durable start plus concurrent status/output retrieval; Desktop Commander is its initial start_process call, with later numeric-exit verification reported separately.

| Route | p50 | p95 | p99 |
| --- | ---: | ---: | ---: |
| Desktop Commander initial call | 4.972 s | 7.212 s | 17.582 s |
| RDC legacy cloud start plus result retrieval | 9.420 s | 11.426 s | 12.170 s |

All 60 stdout results and normal completions matched. RDC returned numeric exit 0 for all 30; Desktop Commander numeric exit 0 was verified for 19, while 11 already-completed session IDs were unavailable during the follow-up read. Those verification limitations are retained, not relabeled as command failures. Every timed pair is retained, including one 21.722-second Desktop Commander transport outlier. Thirty samples provide only preliminary tail estimates. Median reported machine intervals were 47.5 ms for Desktop Commander and 48.336 ms for RDC, using different supervision boundaries; they are not isolated shell-runtime comparisons.

RDC's current cloud route is slower at p50 and p95. The measured local improvement does not establish the requested cloud speed advantage. See [sanitized records and methodology](rdc-dc-live-legacy-2026-11-16.json). Raw account-bound tool responses remain local.

The candidate also passed a real official-MCP-SDK stdio acceptance check in a disposable profile with browser and desktop adapters disabled: 12 distinct commands in two batches of six concurrent calls, exact output and exit 0 throughout, followed by a file-producing script and an idempotent repeat that reused the same job. All 13 jobs were accounted for. This workflow required no cloud service or visible Terminal. See [offline acceptance evidence](rdc-offline-workflow-2026-11-16.json). It is a bounded terminal workload, not complete BandMates application qualification.

## Release verification boundary

Source commit 137a42d67741504697c0e99c2902646948951b7a passed the full local macOS worker suite (360 tests), gateway suite (28 tests), gateway TypeScript check and production build. Both push and pull-request Windows and Linux checks passed on that commit. Hosted macOS remained queued at this snapshot; no hosted macOS result or native Windows/Linux capture qualification is claimed. [Push workflow](https://github.com/TOC-CS/RDC/actions/runs/43951955524) and [PR workflow](https://github.com/TOC-CS/RDC/actions/runs/43951965607) retain the exact job results.

The subsequent benchmark-default correction uses the public baseline commit with the identical tree; a two-round smoke run produced 24 correct outputs. Runtime source files are unchanged by these evidence and reproduction updates.

A matching runtime update and existing private gateway version 12 are prepared with rollback artifacts. Activation is pending explicit release of the daemon-owned Hebrew-course browser session. No runtime restart, connection reset, configuration replacement or BandMates restart is part of the completed work recorded here. End-to-end single-call cloud timing must be measured after activation. The primary relay remains serialized; long inline waits can delay other operations, so long work should use durable start or zero wait.

The actual existing ChatGPT App settings expose name and description edits, but no logo or publisher editor. The description credits TOC Ministries; outer tool-card/listing branding and floating placement remain open host acceptance items. Source logos and mock display-mode tests do not establish those outcomes.
