# RDC competitive engineering, coding and multi-agent acceptance
**Status:** Proposed owner P0 requirement, source and benchmark work authorized; performance superiority unverified.
**Updated:** 2026-11-17, America/Chicago
**Project:** Existing RDC owner branch `repair/preview-v8-host`. Preserve one implementation and the private Site/plugin identity.
**Release constraint:** Live Site v16 remains in service. The v17 gateway stays on HOLD until a protected inactive compatible-reader Site version is independently saved and verified.

## Purpose
TOC requires RDC to outperform Desktop Commander (DC) for the real work an AI agent performs: coding, terminal and file tasks, orchestration of multiple agents, skill usefulness, correctness and end-to-end efficiency. This is a measurable acceptance goal, not a statement of existing performance. An unmatched feature or an unsatisfied metric stays OPEN. A fast tool call that produces a wrong artifact fails.

## Competitive surfaces that must be measured separately
1. **Local engine only:** RDC `Engine.call` in an isolated process versus a same-machine comparable baseline for operations whose implementations can be controlled. This isolates dispatch, filesystem checks and subprocess work. It is not an RDC-versus-DC AI-host speed claim.
2. **Real tool/connector wall clock:** RDC cloud plugin and DC connected remote tool on the same authorized iMac, with matched commands and synthetic repository fixtures. Include network, queues, result collection and tool-call overhead. Use equal permissions and sample both in interleaved A/B and B/A order.
3. **AI-host coding workflows:** the same coding objective, model/effort where possible, information constraints, source state and test oracle. Measure end-to-end time, requests and context tokens (if visible), file diffs, correct behavior, recovery and workflow interruptions. Report host constraints and different model access.
4. **Multi-agent workloads:** isolate real independent worker processes or separate authorized agents by distinct temporary worktree; test 1, 2, 4 and 8 workers and 16 only if hardware permits. Serial RPC iteration is not multi-agent evidence. Count scheduling fairness, blocked operations, conflicts, cancellation, resource peaks and scaling.
5. **Skill usability and portability:** compare discoverability, setup time, callable schema coverage, failed-action recovery, code review/test automation, protocol support, operating-system permissions, offline capability and the actual approved host integration. Skills must be executable and verified, not merely named or described.

## Objective workload matrix and correctness oracles
| Area | Test case | Required oracle |
|:--|:--|:--|
| Code discovery | List project, search exact symbol, read 1 and 20 UTF-8 files | File paths, byte offsets, hashes, match counts and absent data are exact |
| Editing | Create file, exact one-location patch, multi-file refactor in scratch repository | Every expected SHA/diff and downstream unit test matches |
| Conflict safety | Concurrent same-file edit, stale SHA edit, path traversal and symlink | Exactly one valid commit, honest conflict, no outside-file mutation |
| Coding workflow | Add function to Python/JS or TS microproject, write tests, lint/build, repair failing test | Fresh tests pass, identical required behavior, no secrets or unrelated diffs |
| Terminal | Echo, cwd, quoted Unicode, stdout and stderr, exit 1/23, script, environment scope | Actual streams, exit code, cwd and byte lengths match |
| Durable work | Long job, stdin, cancel, timeout, reconnect, duplicate request | Same original ID, exact final result or explicit uncertainty, no duplicate execution |
| Concurrency | 1/2/4/8 independent readers or terminal jobs and conflicting writers | No cross-agent data leak; bounded queues, fairness, correct outcomes |
| Real integrations | Git/DAW/browser in explicitly authorized test area | Verified target identity, no host desktop focus change and no BandMates interruption |
| Skills | Host-specific tool catalog, skill discovery, research/debugging/REA invocation | Correct adapter/tool actually used and its result independently checked |

A benchmark is valid only when tasks are equivalent and both tools are permitted to perform them. A missing feature is recorded as a capability gap, not a hidden zero or an unfair speed win. Do not compare three RDC tool hops with one DC hop without also measuring RDC's best supported single-call equivalent and reporting the task's feature differences. Separate capability correctness from network or host transport cost.

## Sampling, metrics and performance gates
- At least **30 non-warmup observations per workload per tool** in repeated, balanced order. Predeclare seeds, exact invocation arguments, tool versions, fixture digest, host OS and hardware, permission state and concurrency.
- Record success/failure, no-replay correctness, measured p50/p95/p99 completion latency, standard deviation, first output, queue wait, claim-to-result, worker runtime, serialization and upload, timeout/cancel, work per second and error rate. Record CPU seconds, peak RSS, disk read/write, network bytes or unknown when not exposed. Keep original measured outliers.
- Release performance objective: at least **2x lower p50 and p95 latency** than DC on every comparable supported coding/terminal task and greater correct-work throughput, plus equal or better p99, resource efficiency, feature coverage and exactness. If a claimed advantage has inadequate data, label UNVERIFIED. The user-requested universal superiority is a product target, never a factual declaration before validation.
- **Accuracy gate:** 100% correct results on deterministic fixtures; no silent edits, stale-hash writes, unapproved input, wrong directory, missing output bytes or duplicate work. Unexpected failures must be triaged, repaired and revalidated, not averaged away.
- **Multi-agent gate:** per-agent task identity, distinct authorized roots or worktrees, bounded resource/queue usage, conflict-safe writes, fair scheduling, recovery after one agent fails, and no replay of an uncertain mutation. Throughput should scale without starving other agents or disturbing the user's live work. Concurrency levels unsupported by the actual platform remain open.
- **Skill gate:** source and API bindings are authoritative. A documented plugin or skill without a callable adapter does not qualify.

## Initial evidence and bottleneck hypotheses
The existing direct-local terminal benchmark already distinguishes one-call terminal completion from an older two-call flow. The live v16 cloud measurements from November 16 reported queue pickup p50/p95 311/596 ms and claim-to-result 678/1078 ms (n=12); there is no verified RDC 2x end-to-end advantage over DC. A serialized primary relay and cloud/host overhead are candidates for bounded optimization. Do not infer causation without matched measurements or enable unbounded polling, risky command replay or new cloud resources.

Before implementing a scheduler, study existing RDC `rdc/relay.py`, `rdc/jobs.py`, `rdc/files.py`, catalog and worker authorization. Prefer established MCP, durable job, thread pool, git worktree and process-group behavior rather than reinventing protocols. Start with test-only measurements and choose an optimization from demonstrated bottlenecks.

## Security and operational safety
- Use only disposable fixtures in an allowed root for live tool comparisons. No private documents, owner browser sessions, actual secrets, TOC production files or BandMates sources as benchmark targets.
- Keep a single owner of each mutable output path and record competing writers; do not parallelize shared output files unsafely.
- Do not use desktop pointer, keyboard, microphone, MIDI, editor activation or global process restarts in automated performance tests. OS consent and local approval remain authoritative.
- Local language model inference is disallowed for TOC development under the latest shared hosted developer API directive. Deterministic compilers, tests, local shell and REA source inspection remain allowed. Hosted free provider checks require verified authorization, nonsecret broker access and cost limits.
- Preserve live v16 and v17 release HOLD. Speed and coding benchmarks may proceed offline while Site rollback, CI and Atlas review gates remain independently open.

## Review and evidence output
Save the runnable harness, compact manifest and raw sanitized samples in the RDC-owned checkpoints. The report must state where RDC wins, ties, loses or is not supported. Record exact commit/tree, versions and test commands. Request independent Atlas ACCEPT, REWORK or BLOCKED on the scoped evidence. Do not mark the whole product complete from a favorable microbenchmark.

**Owner decision:** This spec implements the user's 2026-11-16 expanded RDC requirement and 2026-11-17 coding/terminal addition. It does not authorize a production release or claim universal superiority.
