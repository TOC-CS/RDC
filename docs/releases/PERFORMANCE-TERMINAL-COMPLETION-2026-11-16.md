# Terminal completion performance candidate — November 16, 2026

Local candidate only. No deployed worker or BandMates session was changed. The 2x faster-than-Desktop-Commander cloud target remains unverified.

## Measured change

The detached supervisor now wakes when output capture finishes instead of always sleeping 40 ms. If the output pipe closes before the child exits, the supervisor keeps its 40 ms control interval to avoid spinning. The inline collector polls every 10 ms for its first 200 ms, then returns to 40 ms. Durable process ownership, permissions, idempotency, output capture, cancellation and recovery routes are unchanged.

Four alternating-order rounds used disposable source copies and profiles, 10 measured commands per method/variant/round, and 3 warmups per method per round. Both variants used the same instrumented harness; only `rdc/jobs.py` and `rdc/worker.py` differed. Baseline was restored from commit `3461af5`. The worker/gateway test suites finished before timing began. All 160 measured commands and 48 warmups produced exact expected output; all 80 fast-path measured commands completed in their initial local call.

| Local operation | Baseline p50 | Candidate p50 | Baseline p95 | Candidate p95 |
|---|---:|---:|---:|---:|
| Start + status/output | 88.614ms | 63.581ms | 91.268ms | 75.638ms |
| Single-call job_run | 96.707ms | 59.806ms | 99.214ms | 65.111ms |

Fast-path p50 fell 38.16% and p95 fell 34.37%. Phase medians identify the improvement: worker lifetime 48.166→22.758ms; result collection 21.383→8.369ms; detached startup 26.291→26.895ms. Worker lifetime includes process launch, capture and supervision; it is not an isolated shell-runtime measurement. Phase timestamps use wall clocks; total latency uses a monotonic clock. With 40 observations per method, tail estimates remain preliminary.

[Raw samples and complete baseline/candidate source hashes](rdc-terminal-performance-matched-2026-11-16.json). Reproduce using:

```sh
python benchmarks/terminal_performance_compare.py --baseline-ref 3461af5 --rounds 4 --trials 10 --warmups 3 --output /tmp/rdc-terminal-performance.json
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
