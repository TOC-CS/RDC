# RDC coding, terminal and gateway performance enhancement

Objective: outperform Desktop Commander in comparable, user-observed workflows, especially cold initiation, terminal commands, coding source discovery, edits, and reliability. Speed improvements must be measured, not assumed.

Observed November 17: a real RDC ChatGPT terminal call took ~6.1 seconds while the persisted worker command lasted ~47 milliseconds. The dominant unexplained time is outside command execution. An existing full matched echo benchmark showed RDC p50 3,178 ms vs DC 1,820 ms, so RDC does not yet win individual terminal calls. Private Site v16 and worker 0.1.0a8 are active; this is source-only work on commit 0631401.

Scope of this independent candidate:
1. Make read-only RDC connection status use zero global maintenance writes and an expiry-aware count. Admission and device polling continue doing bounded cleanup and obeying capacity. This removes several cloud database operations on each health check without changing status truthfulness.
2. Improve rdc_code_context for coding agents: resolve relative requested file paths against the explicitly selected project, reject escapes before output, and make literal source search exclude generated/dependency directories by default, with an explicit "all" mode to search them when requested. Keep rdc_file_search generic behavior unchanged.
3. Add an isolated fixture benchmark that compares full source scan and fast source scan for correctness, scan counts, and local latency. Preserve full Git/terminal access through the current durable job tools, rather than bypassing owner execution policy.
4. Demonstrate real RDC ChatGPT tool execution of focused/full suites; retain exact Git commit/bundle, test logs, and performance receipts. No claim of faster than DC until deployment and matched 30+ non-warmup live observations.

Safety and correctness:
- No separate communication/chat work, Atlas Bus changes, browser takeover, credentials, native cursor, live worker restart, private Site update, or production D1 migration.
- No command execution from a read-only code search, especially when allow_exec is disabled.
- No search aliases or symlink swaps may cross the selected source project; relative and absolute paths share one root boundary. Search results may be truncated and scoped searches intentionally omit generated directories.
- A status check cannot mutate rows; expired queued rows are excluded from the pending count without cleaning them. Normal admission/poll cleanup remains authoritative.
- Preserve idempotency, no replay, pause, approval and no-orphan durability.

Release goals:
- Compare RDC to DC on single-command p50/p95/p99, time to first output, terminal error/recovery correctness, source lookup+edits+test cycle, browser startup and concurrent isolated jobs. Target lower p50/p95 than DC across these explicitly matched scenarios, but report failures if any remain.
- Launch and cold reconnect are separate workloads from warm commands. Log startup boundaries before optimizing.
