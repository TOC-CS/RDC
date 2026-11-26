---
name: rdc-coding
description: Use RDC for authorized coding, source discovery, guarded file changes, terminal/test execution, and reproducible performance comparison with Desktop Commander.
---

# RDC coding and terminal workflows

Use the owner's existing RDC App and the exact selected worker, link, project root, and task identity. Start by reading the installed RDC skill and checking `rdc_connection_status`, `rdc_system_status`, and the tools actually advertised in this chat. An offline candidate, GitHub source file, or local engine feature does not establish that a gateway tool is live. Keep the owner's active desktop, cursor, and BandMates applications undisturbed.

## One-request source inspection when available

When the current tool catalog actually exposes `rdc_code_context`, use it for a read-only combination of project directory listing, bounded literal search, and up to 20 SHA-256-hashed reads. Always pass one explicit selected project subtree. Treat `file_paths` as relative to that project: requested reads may not traverse to other projects, even when the worker's configured mode allows general full-host access. Use observed absolute paths and current hashes, not guessed source locations. The result is a collection of independent reads, never an atomic filesystem snapshot.

Review each returned per-file `ok`, `error`, `truncated`, `offset`, `next_offset`, and `sha256` before editing. Search results may be truncated or skip binary, large, unreadable, or disallowed files. If `rdc_code_context` is missing, use the existing `rdc_file_list`, `rdc_file_search`, and `rdc_file_read_many` tools instead. Never simulate an unavailable tool or claim the feature was activated from a pending source commit.

## One-call search-to-source matched reads (isolated source candidate)

When the **live tool catalog** advertises the optional `read_matches` schema field on `rdc_code_context`, select a single authorized `path`, supply a literal `query`, and set `read_matches` to a number from **0 to 5**. This reads the first distinct matching files returned by the bounded source search during the same request. Explicit `file_paths` stay first, and duplicate matched paths are omitted. The combined call never requests more than 20 files. Example: `rdc_code_context({"path": "/authorized/project", "query": "def load", "read_matches": 3, "search_mode": "source"})`.

Check `auto_read_count` (number of automatically selected paths), `read_limit_per_file`, each read's `ok`, `sha256`, `truncated`, `offset` and `next_offset`, and the search's `files_scanned`/`files_skipped`. A match may become unavailable or resolve outside the project before the read; the affected read must return a per-file error and must not reveal another project's content. Content excerpts are capped at 16 KiB per read. Nonzero `read_matches` requires `query`.

**Fallback:** the current v16 connected RDC does not advertise `rdc_code_context` or `read_matches` yet. Use available live `rdc_file_search` and `rdc_file_read_many` in that environment. No source tests or generated assets constitute production activation. After authorized gateway and worker deployment, recheck the exact live tool catalog before invoking this option; run a real end-to-end comparison against Desktop Commander.

The integrated RDC performance candidate is in the isolated `integration/rdc-performance-20261117` branch. Its project-boundary repairs and batched source search/edit code remain offline. Local integration verification recorded 475 Python tests (26 skipped) and 56 gateway tests with zero failures, plus a successful gateway build. These results describe source tests, not a deployed ChatGPT tool. Hosted Windows/Linux/macOS CI, independent reviewer authority and live deployment remain OPEN.

## High-speed coding and browser operations (candidate only)

Use these workflows **only when the actual connected RDC tool catalog advertises them**. The local source catalog includes 64 worker tools, but the active Site v16 and worker v0.1.0a8 remain unchanged until separately reviewed and deployed.

- **Source search:** `rdc_code_context` combines a project directory listing, literal search, and up to 20 SHA-256-versioned reads in one bounded call. `file_paths` resolve relative to the explicit selected project. Search defaults to `search_mode="source"`, excluding `.git`, `node_modules`, `.venv`, `__pycache__`, `.next`, `dist`, `build`, and `target`. Specify `search_mode="all"` only when generated and dependency code is genuinely required. Audit skipped paths and truncation.
- **Batch edits:** `rdc_code_edit_many` accepts 1 to 10 independent exact edits inside the selected project, each with `old_text`, `new_text`, and `expected_sha256`. It checks the selected-project boundary, rejects duplicates and changed symlink targets, then reports each result. Batches are **not atomic across files**. If some edits succeed and others conflict, inspect the explicit partial-failure result for every file and its current SHA rather than resending the batch. **No replay** after an uncertain mutation: recover the original `_rdc_request_id` and worker idempotency key.
- **One-call browser work:** when available, `rdc_browser_start_navigate_observe` starts, navigates and observes one independent authorized session; `rdc_browser_navigate_observe`, `rdc_browser_click_observe`, and `rdc_browser_fill_observe` return fresh observations with the action. Use the exact returned session and observation IDs. Validate handles, URL changes and truncation before the next action. No blind retry after lost browser acknowledgements or shared desktop takeover.
- **Terminal fast path:** use live-advertised `rdc_job_run` for short noninteractive commands. Retain the exact exit code and original job identity; recover background work via status/output rather than dispatching a second process.
- **Gateway phase diagnostics:** `rdc_recent_operation_metrics` is a gateway-only, owner-authenticated, bounded read intended to show queue pickup, claim-to-completion and total gateway service timings without exposing stored arguments, results, tokens or full IDs. The separate `rdc_connection_status` read-only fast path excludes stale operation rows without performing cleanup writes.

The recorded local synthetic benchmark found source-only search 44.85x faster than searching all 660 generated/dependency/source files in that fixture, and one six-edit batch 1.26x faster than six separate local edits. Both measure Python Engine time, not ChatGPT connector latency. Continue matched cold-start and end-to-end comparisons with Desktop Commander after approved live deployment. The historical RDC 3,178 ms versus DC 1,820 ms terminal p50 remains the unresolved baseline.

## Accurate code modification

Create or select the owner-approved worktree and explicit edit scope. For writes, read current content and SHA-256, then use `rdc_file_edit` with the expected hash and exact occurrence count, or `rdc_file_write` with the required version check. If a hash conflicts, reread and reconcile. Preserve other owners' untracked files, existing branches, app identities, production credentials, and active jobs. Do not use shell scripts to bypass a refusal from a dedicated tool or a native-input owner consent decision.

## Direct terminal, tests, and recovery

For short authorized commands use the live advertised `rdc_job_run` with an argument vector, explicit working directory, stable `idempotency_key` and cloud `_rdc_request_id` where required. Verify `complete`, exact exit code, stdout/stderr, and output truncation. For long-running or interactive commands use `rdc_job_start`, then recover the original job with `rdc_job_status`, `rdc_job_output` and `rdc_job_input`. Never redispatch an uncertain mutation with a new request ID. On queued cloud results use `rdc_operation_status` for the original operation before deciding whether further action is required.

For coding builds, use a disposable project or exclusive Git worktree, run the focused tests and the full relevant suite, verify diff and source hashes, and report remaining failures precisely. Production rollout, worker restarts, credentials, human input, and Site database migrations require separate authorization.

## Performance and parallel tasks

Compare direct-local worker, cloud gateway, and AI-host round-trip timings separately; do not treat a local microbenchmark as proof that the ChatGPT tool call is faster. Use matched harmless workloads, at least 30 non-warmup observations per tool and condition, balanced order, p50/p95/p99, correctness and failure counts. Test concurrency with isolated workspaces, exclusive file ownership and bounded pools. Concurrent deterministic processes are not an independently reasoning AI swarm.

As of the verified November 17, 2026 baseline, live RDC v16 and Desktop Commander each returned 30/30 correct echo commands, but RDC p50 was 3178 ms versus 1820 ms for DC; the goal to outperform DC remains OPEN. The unpublished batched source-context feature reduces possible host tool hops, but has no verified postdeploy speed advantage. The security-hardened variant took local p50 9.120 ms versus 8.619 ms before hardening in 60 trials each. Avoid unsafe caching, replay, permission changes, unbounded polling, or user desktop takeover as performance shortcuts.

## Current release boundaries

Reuse the existing `TOC-CS/RDC` draft PR #1 and current owner-private RDC Site. The Site remains v16; do not activate v17 before independent code review and an inactive verified rollback-compatible Site version exist. Historical v16 is unsafe for rollback after inline-only v17 result records exist. A read-only GitHub connector cannot publish source, and a browser sign-in state alone does not authorize access through a different browser control surface. When authenticated browser editing is unavailable, retain the exact local bundle, commit, and manifest and report the publication gate.

Evidence packet: `~/RDC-Development/checkpoints/rdc-code-context-scope-20261117/` on the owner's iMac. Never claim a local packet automatically reached Atlas or that a build or Site version is deployed without verified readback.

## Mobile speed-first development

For RDC mobile changes, use available Superpowers planning, isolated-worktree,
test-driven development, systematic debugging, execution and verification
skills. Keep one inline development path when parallel work would duplicate
device state or spend extra tokens. Use scope-appropriate qualification with exact counts, meaningful timeouts
and safe cleanup. The owner retired the fixed 100-check ceiling on
November 25, 2026. Never replay uncertain input. Measure actual execution
and verified feedback, not only request acceptance. Public release notes,
source packages and walkthroughs must use generic examples, without owner
applications, personal paths, private device evidence or signing material.
