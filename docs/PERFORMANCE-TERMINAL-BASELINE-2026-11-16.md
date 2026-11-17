# RDC vs Desktop Commander: Terminal Performance Baseline

Recorded November 16, 2026. **Preliminary smoke-test measurements, not release qualification.**

## Environment and task

- Same authorized iMac, macOS arm64. Same harmless command: printf RDC_DC_BENCH_READY, then uname -s.
- Expected stdout: RDC_DC_BENCH_READY followed by Darwin, with exit code zero.
- RDC: connected cloud tool, rdc_job_start followed by concurrent rdc_job_status and rdc_job_output, launched in a named project workspace.
- DC: start_process on the same connected iMac, one call.
- Both routes executed autonomously. No manual Terminal launch, command pasting or shared desktop pointer input.
- Times are milliseconds measured at the tool-call orchestration boundary (including transport and remote service delays). This is **not a measurement of shell computation time** or a fair full-feature parity comparison. DC's first call reported local process execution in approximately 55 ms.
- Measurements were sequential; tool/provider latency varied, especially during RDC trial 2. n=3 is too small to estimate reliable p95/p99.

## Initial measurements

| Trial | DC one-call wall time (ms) | RDC start call (ms) | RDC status + output (ms) | RDC combined (ms) | Output |
|---|---:|---:|---:|---:|---|
| 1 | 2,196 | 3,470 | 2,760 | 6,230 | Correct from both |
| 2 | 1,657 | 8,580 | 3,090 | 11,670 | Correct from both |
| 3 | 2,245 | 2,899 | 2,789 | 5,688 | Correct from both |

- Median DC: **2,196 ms**
- Median RDC: **6,230 ms**
- RDC is approximately **2.84 times slower** in this preliminary end-to-end smoke test.
- Correct outputs: **3/3** for each tool. This does not establish general command correctness or performance.
- Bottleneck hypothesis to test: extra asynchronous job dispatch and retrieval round trips plus gateway latency dominate trivial shell operations. Confirm with instrumented worker timestamps before implementing a fix.

## Benchmark expansion and release acceptance

1. Establish a repeatable benchmark with **at least 30 measured iterations per operation**, warmups, randomized or balanced ordering, cold/warm connections and equivalent commands. Record p50/p95/p99, standard deviation and failures.
2. Separate **agent-to-gateway**, gateway-to-worker, job queue/start, real process runtime, first-byte delivery and final-result retrieval. Compare **direct local RDC** and **remote/cloud RDC** independently against DC; do not attribute cloud latency to shell code.
3. Test terminal access without manual steps: working directory, shell scripts, multi-line commands, positional arguments, stdout/stderr, nonzero exit codes, stdin/interactive input (rdc_job_input), streamed output, long-running jobs, cancellation, timeouts, idempotency, session recovery and reconnect.
4. Test file search, read/write, batch operations and concurrent jobs in a disposable restricted folder, with byte-for-byte output checks and no accidental retries or dropped commands.
5. Measure latency and throughput across small (zero/1 KB), medium and large outputs, concurrent workloads, cold boot, offline/local operation, CPU, memory and network usage. Keep authorization and OS consent intact.
6. Evaluate a **single-call foreground terminal fast path** for short authorized tasks, returning stdout/stderr and exit status directly with a durable background fallback for slow tasks; verify existing safety and command semantics. Investigate connection reuse, batching, poll reduction and result streaming before coding.
7. Performance target from owner: **at least 2x faster p50 and p95 end-to-end than Desktop Commander** on comparable supported tasks, where feasible. Never claim it without measured, repeatable evidence. Keep accurate status if host-side latency is not controllable.
8. BandMates AI Studio acceptance: test concurrent AI-powered musician workflows, rapid tool calls and responsive UI without stealing the owner's keyboard, mouse, active desktop, or restarting BandMates. Preserve local-first/offline operation.

## Status

- Terminal command execution and output readback: **smoke tested, working without manual input**.
- Head-to-head speed target: **not met in preliminary samples**.
- Comprehensive benchmarking, improvements, interactive terminal coverage and BandMates live acceptance: **OPEN**.


## November 16 candidate: direct-local one-call benchmark

Benchmark harness: benchmarks/terminal_fast_path.py, run with the RDC virtual environment's Python 3.14. Re-run in a clean source checkout:

    python benchmarks/terminal_fast_path.py --trials 30 --output docs/releases/rdc-fastpath-local-benchmark-2026-11-16.json

Data: docs/releases/rdc-fastpath-local-benchmark-2026-11-16.json. Balanced, deterministically shuffled, 30 real detached commands per method, executed against the same local Engine process and ephemeral SQLite job state. Exact stdout was checked for every invocation. No keyboard, mouse, application windows, private data or user desktop were accessed.

| Metric | Existing start + status/output | New rdc_job_run single call |
|---|---:|---:|
| Runs | 30 | 30 |
| Correct outputs | 30 | 30 |
| p50 local end-to-end | 88.483 ms | 99.011 ms |
| p95 local end-to-end | 93.319 ms | 100.357 ms |
| p99 local end-to-end | 98.352 ms | 144.462 ms |
| Completed within first local Engine.call | 0 (not applicable) | 30 |

**Interpretation:** The new route is approximately 12% slower in this direct-local sample at p50; the test does not isolate the contribution of polling. It completes the local command and output inside one Engine.call, but whether that eliminates separate ChatGPT tool round trips depends on the deployed gateway, relay scheduling and provider timing. This measures only the local worker, not cloud network latency, gateway polling, message generation or Desktop Commander. The 2x owner target remains OPEN and requires at least 30 matched cloud DC/RDC measurements after the corresponding worker and gateway versions are installed. A future implementation may reduce durable worker startup and/or gateway-hop overhead, subject to exact-once/recovery safeguards.

**Node/REA environment check:** Homebrew Node.js 24.22.3 with npm 11.19.1 was installed on the iMac and selected for new Bash and Zsh login shells. The original root-owned Node.js 24.21.0 binary was retained, and BandMates was not restarted. REA v6.9.0 starts and recognizes Node 24.22.3. The broader REA doctor audit still reports optional analysis engines and client registrations missing/drifting; no invasive provider setup or active app restarts were attempted.


## Independent code-review findings and safety work

A Codex read-only multi-agent review identified post-launch result failures that could lose the durable job ID, potentially blocking safe recovery. This candidate now includes focused tests and fixes for durable ID retention on failed result collection, zero-wait pending responses without unnecessary output I/O, regular-file-only output reading, consistent job/output status from a single snapshot, and inclusion of the fast-path operation in RDC activity. A separate gateway regression covers delivery of a simulated completed worker result within the initial cloud call.

Outstanding: the gateway primary relay processes operations serially, so using the maximum 3000-ms inline wait can delay unrelated queued operations. Interactive and longer commands should continue using the durable job-start path or set wait_ms=0. This architectural limit and end-to-end cloud performance require actual deployment and concurrent workload tests.


## Reviewed candidate rerun

After the independent multi-agent code-review fixes, the full 356-worker/28-gateway test suites passed. A fresh balanced local benchmark, with 30 real commands per path, yielded:

| Metric | Existing job path | Reviewed fast path |
|---|---:|---:|
| Correct outputs | 30/30 | 30/30 |
| p50 | 96.106 ms | 108.336 ms |
| p95 | 110.463 ms | 137.845 ms |
| p99 | 111.592 ms | 166.166 ms |
| First local Engine call completed with output | Not applicable | 30/30 |

Raw timing evidence: docs/releases/rdc-fastpath-local-benchmark-reviewed-2026-11-16.json. The two runs occurred at different times and under different system loads; do not attribute the differences between runs to one code change. In this second run the fast path remained slower locally, and its value is conditional reduction of cloud/model round trips, not lower raw subprocess execution time. Live cloud measurements, concurrent relay behavior and comparison against Desktop Commander remain OPEN.

The reviewed implementation preserves the original durable job ID if result collection fails after command dispatch, avoids immediate output I/O for zero-wait or timed-out active jobs, reads only regular output files without following symlinks, bounds reads by captured file size, synchronizes job/output status and includes the new tool in activity reporting. The gateway tests also simulate returning an actual completed job-shaped response within the initial cloud call.
