# RDC vs Desktop Commander | REA gap review and source upgrade | 2026-11-18

## Purpose
Build RDC into a better general-purpose agent workbench for terminal, coding, browser, file inspection, analysis and workflow safety, based on the real connected tools rather than promotional claims.

## Evidence boundaries
The REA static review on 2026-11-17 examined seven selected shipped Desktop Commander 0.3.1 JavaScript sources and 16,614 AST nodes; 805 of 812 inventoried files were outside semantic analysis and dynamic hosted-server code was unavailable. Record: ~/RDC-Development/checkpoints/rdc-dc-pipeline-rea-20261117/PIPELINE-TRACE-AND-BENCHMARK-MASTER.md and rea-sdk26-summary.json. The installed remote agent exposed Desktop Commander v0.3.1 on iMac.local. The connected RDC app exposed worker v0.1.0a8 on the same iMac and private Site v16.

## 30-pair historical live terminal baseline (November 17)
Both tools returned exactly 30 of 30 correct shell echoes. RDC p50 3,178 ms, p95 5,148.3 ms. Desktop Commander p50 1,820 ms, p95 3,642.5 ms. RDC is 1.75x slower at median on this narrow operation. The completed worker process portion is much shorter than the AI host tool roundtrip; more detailed gateway instrumentation is needed to attribute the difference. These are measured gateway calls, not a code execution speed comparison. No faster-than-DC claim is supported.

## Core transport comparison
Desktop Commander 0.3.1 remote route: hosted service to Supabase Realtime doorbell, conditional row claim, local Node MCP child stdio, persisted remote result. RDC v16 route: hosted Cloudflare D1 durable queue, relay long-polling with up to 10-second wait and 500 ms claim probes, local Python MCP worker, D1/R2 result storage and completion polling. Doorbell latency is a plausible contributor, but not proven to dominate end-to-end time. Keep durable claim identity and fail-closed uncertain mutation handling.

## Live capability checks performed November 18
- RDC job_run executed Python and shell, returned exact exit 0, retained a durable job ID, and matched a SHA-256 computed through the connected Desktop Commander start_process tool.
- RDC file_list listed the isolated performance repository and file_read_many returned UTF-8 source text and SHA-256 digests.
- RDC independently launched Chromium, navigated to https://example.com/, returned page title and interactive control handles, captured a screenshot, and closed the isolated browser session. No owner cursor or native desktop was used.
- Connected Desktop Commander advertises file, search, edit, process, session and configuration operations. This chat's Desktop Commander tool catalog did not advertise dedicated browser session APIs or one-call project-scoped code context. This is a connector comparison, not proof of absence in every Desktop Commander edition.

## Competitive gaps and upgrades
1. **Interactive terminal latency:** RDC loses the measured baseline. Priority P0: use bounded, nonsecret admission/queue/claim/result phase telemetry; investigate event-driven relay wakeup while preserving D1 durable claims and mutation identities. Any gateway change requires regression, rollback, and live remeasurement. Work remains OPEN.
2. **Coding research roundtrips:** RDC integrated candidate already has project-scoped rdc_code_context; this isolated branch adds read_matches=0..5 to read the first distinct matching source files within the same request. Existing explicit paths remain first; no >20 combined reads; per-file SHA and errors remain. This can remove a separate discovery-to-read tool hop. Local code and test only, NOT currently advertised by live v16.
3. **Code change safety:** RDC candidate supports guarded SHA-exact rdc_code_edit_many. Must test partial batches and uncertainty recovery. DC's connected tool catalog lacks an equivalent project-scoped batch tool. No live proof until deployment.
4. **Browser control:** RDC's dedicated isolated Playwright session worked live. A separate source candidate combines start/navigate/observe and action/observe to save a cloud roundtrip. Test stale handles, privacy checks and no blind mutation retry before release.
5. **File analysis:** RDC auto-read search, binary skip, truncated reports and SHA-based read validation provide concrete developer capability. Future direction: bounded multi-file summaries, source graph context and opt-in diff views, but avoid stale indexes and secret leakage.
6. **Durability and recovery:** Preserve existing exact job status/output and original operation status paths, owner access consent, session isolation and fail-closed privacy. Speed may not compromise duplicate-execution prevention.
7. **Comparative qualification:** Match at least 30 actual ChatGPT roundtrips per workload, alternating request order under comparable load, recording output correctness, p50/p95/p99, failure rate and response size. Synthetic engine timing cannot prove tool speed superiority.

## This isolated source work
Worktree: ~/RDC-Development/workspace/rdc-rea-search-context-20261118, branch perf/rdc-rea-search-context-20261118, based on b2349b6. New red-first test suite confirmed the prior schema rejected read_matches. After implementation, six new behavior/security tests passed. Coding skill red-first guidance test passed after the skill update. Gateway catalog synchronized with 64 tools and 56/56 gateway tests passed. The full Python suite completed with exit code 0: 485 tests run, 43 skipped, 0 test failures, in 127.560 seconds. Two ResourceWarnings about unclosed SQLite connections appeared in the full suite output and remain open diagnostic items.

Balanced 30-round **local Engine only** benchmarks using 51 synthetic files verified identical source text/hash results. With the full suite running, one-call p50 was 7.698 ms and two-call p50 7.636 ms. With no full suite running, one-call p50 was 7.615 ms and two-call p50 7.605 ms. This reduces API calls from two to one with effectively unchanged local execution time. No live acceleration claim is supported. Raw files: test-results/rdc-rea-search-to-source-20261118.json and test-results/rdc-rea-search-to-source-20261118-unloaded.json.

Fresh six-round balanced **live** echo spot check on the unchanged v16 worker: 6/6 successes for both, RDC p50 3,277 ms versus Desktop Commander p50 1,683.5 ms (1.95x slower). This smaller different-shell test does not supersede the better 30-round historical baseline. Raw file: test-results/rdc-rea-live6-20261118.json.

## Release limits
Do not replace the live v16 Site, install the candidate worker, or publish a plugin version until complete platform and rollback evidence is reviewed. This branch preserves other owner worktrees; it contains source derived from the integrated candidate and must be reconciled with the later RDC skill/communications cleanup before merging. Current owner instructions to remove communication experiments take precedence over older integrated source. Production, remote source and installed skill may differ from this isolated code.
