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
