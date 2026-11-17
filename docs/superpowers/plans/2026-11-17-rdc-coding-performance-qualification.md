# RDC coding and terminal competitive qualification plan
**Work item:** RDC-P0-CODE-TERMINAL-MULTIAGENT-20261117
**Status:** IN_PROGRESS. Owner: existing RDC development session, one writer in `repair/preview-v8-host`.
**Base source:** Published review source `0e3058292dac6555663548614276ad28dea1a2fe` (Git tree `90717688950d70e578fec961e9240cbf2f33c43e`). Current local merge retains this exact tree. Do not touch concurrent owners' untracked `AGENTS.md`, `TOC_MASTER_BUILD_WORKFLOW_V1.md` or `TOC_SHARED_HOSTED_AI_API_ACCESS_V1.md`.
**Design:** `../specs/2026-11-17-rdc-vs-dc-code-agent-performance.md`.

## Phase 1: source, capability and baseline inspection
1. Inventory actual RDC and DC tools, terminal session semantics, code-file operations, recovery and available skills. Record actual capability names and evidence, not advertised claims. Identify unmatched features.
2. Read `rdc/files.py`, `rdc/jobs.py`, `rdc/relay.py`, `rdc/engine.py`, existing terminal benchmarks and failing/performance receipts. Keep the current serialized primary relay unchanged until a safe scheduler is designed and tested.
3. Inspect live v16 connection and D1 phase evidence read-only. Preserve the protected rollback version requirement before any v17 activation.
4. Keep model and swarm discovery separate from deterministic coding tests; shared hosted API credentials are broker-only and currently require independently verified access. Never display secret bytes or silently use paid models.

## Phase 2: test-first isolated coding benchmark and regression
1. Add `benchmarks/coding_workflow.py` using `tempfile.TemporaryDirectory`, a private test Engine, a deterministic tiny Python or JS project and SHA-256 oracles. No user files or system desktop access.
2. Implement each stage of a realistic coding task: list repo, search symbol, read multiple files, apply a SHA-checked edit, create a test module, run its tests, capture stdout/stderr and exit status. Include negative cases: stale SHA, missing path, duplicate exact-match refusal and a nonzero terminal exit.
3. Measure every local API call with monotonic time, keep raw samples and p50/p95/p99 for warmups plus at least 30 counted iterations. Distinguish setup, local dispatch, command startup, exit/result readback, and final verification. Run without model inference. Check that source edits and test results match oracles.
4. Add a CI-safe unit test that runs the harness on tiny counts, verifies JSON schema, exact result/diff, no escaping the scratch root, no external state and accurate failure accounting. Capture a red failure before implementation and green after.

## Phase 3: bounded concurrency and multi-agent work
1. In disposable worktrees run 1, 2, 4 and 8 independent coding/terminal tasks, each with a unique root and identity. Avoid shared live project writes. Record throughput, p50/p95/p99, CPU/RSS and output accuracy. Distinguish async tasks from distinct independent agent processes; do not label a loop a swarm.
2. Inject stale-hash same-file writes in a synthetic shared file with two worker tasks. Confirm exactly one authorized winner, a conflict result for the loser, and no outside-root or partial file writes.
3. Compare current serialized relay throughput to a bounded multi-lane model in a simulation only. Before changing it, specify fairness, owner isolation, queued/claimed/unknown states, operation ID authority, TTL, cancellation and no-replay invariants. Obtain Atlas review before touching the relay's live scheduling semantics.

## Phase 4: external Desktop Commander comparisons
1. Use existing authorized DC and RDC tools in the same chat, same iMac, same scratch fixture and permissions. Alternate tool order, include cold/warm samples, and do at least 30 samples per matched task. Record exact input/output correctness and phase timing, including the tool provider boundary.
2. Benchmark code search, file read, exact edit, file creation, tests/build, terminal stdout/stderr, nonzero exits, long/interactive jobs and recovery. A feature mismatch becomes OPEN and an explicit capability row, not an invented metric.
3. Separately time RDC direct-local Engine, RDC cloud tool, DC remote tool and the real AI coding workflow. Mark unavailable/unknown timing fields rather than filling estimates.
4. Calculate p50/p95/p99, throughput, errors, cold/warm overhead and CPU/RAM cost with original outliers. Compare at matched concurrency and workload. Highlight remaining deficits and shortlist changes grounded in bottleneck evidence.

## Phase 5: optimization, independent acceptance and safe release
1. Prioritize low-risk changes with measured wins: tool batch efficiency, one-call file discovery/edits, reusable shell sessions, fast-path completion, output chunking, nonblocking scheduling. Reuse DC's proven usability patterns when licensed and compatible, without copying proprietary internals or bypassing security.
2. For every change: fail a targeted regression, implement minimum repair, run focused tests, full Python/Node suites, OS-independent CI, simulated browser and real independent tool tests. Record exact source SHA, benchmark data and observed gains.
3. Send evidence packet to Atlas with explicit ACCEPT/REWORK request, including limitations and release blockers. No self-approval.
4. Activate no gateway update until the **protected inactive compatible-reader Site version** is saved/read back, source/CI matches, live D1 migration is separately approved and worker/Studio noninterference is independently checked. Continue offline improvements while release gate remains blocked.

## Explicit stop and safety conditions
- Stop a particular unsafe or unverified operation if it would alter the owner's actual desktop input, private accounts, credentials, production Site, BandMates or other owners' files. Continue safe independent tests and documentation.
- A test failure is REWORK and requires diagnosis; do not mark all work done from a locally passing partial suite.
- Do not claim 2x DC advantage, universal host compatibility, true multi-agent parallelism or completed coding skill without verified matched evidence.

## Next executable action
Create a coding workflow harness and its contract test in the existing RDC repository, run test-first red/green, 30+ local trials, then review metrics and submit the local packet to Atlas. Preserve GitHub PR #1 and live Site v16.
