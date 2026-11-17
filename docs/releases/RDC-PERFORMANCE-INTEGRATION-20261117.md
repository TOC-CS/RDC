# RDC Performance Integration: Scoped Release Candidate

**TOC Ministries | November 17, 2026**

**Status:** Integrated source validated locally. Independent Atlas and GitHub cross-platform review required. **Live Site v16 preserved. v17 activation held.**

## Provenance and scope

Created an isolated `integration/rdc-performance-20261117` worktree from the existing `af322be1b75a4e48e0fece3b194c632b8dac6fc9` development candidate. Integrated the verified performance source `013ef6ff82737815b661f8dbb779a6ba0aa3d4a3`, which contains `1566aed5c77c192b90ed43ae72379e7334a4a6ab` and `06314011805b42b71bfe4b84be435927a2f98799`. Both lines descend from the same audited `d49d33e` source baseline.

The only merge conflict was the cloud gateway core. It was resolved by preserving the existing ChatGPT tool contract plus the new owner-only gateway metrics, read-only connection-status fast path, and normal mutation cleanup. The three other overlapping files auto-merged. The source communication feature was preserved without adding work to its separate project.

The original owner worktree `repair/preview-v8-host`, the communication feature branch, and the performance owner's original branch remain independent and unchanged.

## Integrated features

- Browser: `rdc_browser_start_navigate_observe`, `rdc_browser_navigate_observe`, `rdc_browser_click_observe`, and `rdc_browser_fill_observe` reduce permitted browser tool round-trips. Existing session IDs, fresh observation handles, and no-replay rules are preserved.
- Coding: `rdc_code_context` accepts relative source paths under one explicit project. It skips generated/dependency directories in the default source search mode, with explicit `search_mode="all"`. Individual file hashes and truncation indicators remain visible.
- Edits: `rdc_code_edit_many` accepts at most 10 SHA-256-guarded project-confined surgical edits. It refuses duplicate canonical paths, prevents symlink redirects out of scope, reports per-file outcomes and partial failures, and makes no promise of batch atomicity.
- Terminal/cloud: short `rdc_job_run` calls retain durable job IDs, true exit codes, operation recovery and idempotency. The gateway's status fast path reduces read-only D1 cleanup overhead and uses expiry-aware pending counts.
- Diagnostics: owner-only `rdc_recent_operation_metrics` supplies bounded phase durations, excluding request bodies, result payloads, tokens and full operation IDs.
- Skill documentation: the main `skills/rdc/SKILL.md` now explains one-call browser operations and links to `skills/rdc-coding/SKILL.md`. The coding skill documents search modes, guarded edit batches, cloud metrics, and the live deployment caveat.

The generated `cloud-gateway/lib/rdc-assets.json` catalog contains **64 unique worker tools**, matching the current Python Engine. Gateway-only tooling is additional to that count.

## Verification

Fresh same-source integration runs before the coding-skill documentation addition:

- Full Python worker suite: **475 tests run, zero failures, 26 expected skips**, `full-python-integration-20261117.log`.
- Cloud gateway Node suite: **56/56 passed**, `gateway-integration-first-20261117.log`.
- Gateway lint: **zero errors, one existing image-component warning**, `gateway-integration-lint-20261117.log`.
- Offline production gateway build: **passed**, `gateway-integration-build-20261117.log`.
- Added coding-skill contract tests were observed failing first, then **2/2 passing**, `performance-skill-RED-20261117.log` and `performance-skill-GREEN-final-20261117.log`.

Final same-source Python regression after adding the portable coding skill and its two TDD tests: **477 tests, zero failures, 26 expected skips**, about 128.9 seconds. Evidence: `full-python-final-20261117.log`. The preceding 475-test run remains historical evidence of the earlier merge state. The merge was inspected for unresolved conflict markers, direct owner-only tool access, preserved D1 cleanup on mutating operations, and explicit batch mutation safety. Independent code review and hosted Windows/macOS/Linux CI remain separate release gates.

## Performance baselines and limits

Source benchmark evidence from the performance owner includes 30-run synthetic comparisons: default source-only search versus a full 660-file scan was **44.85x faster** in median local execution, and one six-edit batch versus six separate local edits was **1.26x faster** median. These are local Engine results, not end-to-end ChatGPT cloud tool latency. The source search benchmark intentionally compares a smaller permitted scope and returns the same target match.

The previous matched ChatGPT terminal benchmark was RDC **3,178 ms p50** against Desktop Commander **1,820 ms p50**, each 30/30 correct. RDC remains behind in that baseline. Current integration proves feature correctness in the local source; it makes no claim of universal speed superiority.

## Release and security restrictions

- Existing owner-private Site stays **v16**, and the connected live worker stays **0.1.0a8**.
- Do not activate v17 until a protected rollback-compatible inactive Site version has independent readback evidence, with reviewer approval. No live D1 migration was conducted.
- Public release remains held until fully operational and reviewed. A versioned ChatGPT skill-only update may be published without changing the Site, tool catalog, or current App identity.
- Review the exact source commit and GitHub CI independently. The candidate's generated tool catalog is not proof those tools are currently callable in ChatGPT.
- Next live benchmarks require an approved deployment and matched, balanced cold-start, browser, coding, file, terminal, concurrency, and recovery workloads measured with both RDC and Desktop Commander.

Supporting performance-owner source bundle and evidence: `~/RDC-Development/checkpoints/rdc-terminal-coding-performance-20261117/`. Integration verification packet: `~/RDC-Development/checkpoints/rdc-performance-integration-20261117/`.
