# RDC Single-call Terminal Fast Path Design

## Intent
Reduce end-to-end latency for short terminal commands while preserving RDC local-first independence, configured permissions and durable recovery. Desktop Commander is the benchmark. The owner has approved implementation for BandMates AI Studio and requires no manual Terminal launch.

## Evidence
rdc_job_start records SQLite job state and launches a detached worker, then returns a job ID. The caller uses separate status/output calls. Three preliminary cloud smoke tests gave median RDC 6,230 ms, Desktop Commander 2,196 ms, including provider and transport latency. This is directional, not p95 qualification.

## Approaches
- Direct foreground subprocess: faster locally, but harder to preserve cancellation, stdin and nonreplay after transport interruptions. Deferred.
- Gateway batching: later possibility, but cannot always eliminate multiple host/model round trips.
- Chosen: short bounded wait on the existing durable job, returning output in the original call if done, or the same job ID for longer commands.

## API
New mutating tool rdc_job_run accepts argv, cwd, optional timeout and idempotency_key as rdc_job_start plus wait_ms integer 0..3000 (default 1500) and output_limit integer 1..262144 (default 16384; additionally capped at max_read_bytes).
Return fields: job, reused, complete and output. Output uses the existing rdc_job_output shape. Complete means a terminal status only; failure exits remain job status=failed and exact exit_code. For pending jobs return complete=false and a durable job ID, allowing later status/output/stdin/cancel/recovery.

## Safety invariants
- Reuse existing job startup, SQLite fingerprint, idempotency key, cancellation and detached process; do not directly re-execute.
- Same allow_exec, pause, owner review, max job count, timeout and root constraints.
- Cloud mutation keeps stable _rdc_request_id. Never automatically replay an uncertain call.
- No native desktop focus, keyboard or mouse modification. Keep BandMates active.
- Output bounded and truthful; separate stdout and stderr remain combined in the current worker as before.
- No paid-model or VPS dependency; local engine remains fully functional.

## Acceptance
1. One call returns completed job and text for a short successful command.
2. A zero-wait call returns pending immediately, with same job recoverable later.
3. Reused idempotency key returns same job without re-execution; changed command conflicts.
4. Nonzero exit returns failed job with stderr and exit_code.
5. Paused/review/disabled execution and invalid cwd constraints remain effective.
6. Gateway advertises the tool with required stable request ID, CI and production build pass.
7. 30+ matched host measurements with p50/p95/p99 needed before 2x speed claim.

## Non-goals
Do not remove approval/OS permissions or reset running worker/gateway during testing. Do not claim host-level floating viewer acceptance from mock tests.
