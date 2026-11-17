# TOC RDC: code-context and search subtree safety review
Date: 2026-11-17 CST
Owner: TOC Ministries, RDC scoped development continuation
Review state: READY FOR INDEPENDENT ATLAS SCOPED SOURCE REVIEW. Production unchanged.

## Baseline and exclusive scope
- Base: c67a26d13b8ee2dd51a643009b7abaa2750cad17, existing `repair/preview-v8-host`.
- Isolated Git worktree/branch: `workspace/rdc-code-context-review-20261117`, `fix/code-context-read-scope-20261117`.
- Exclusive changed code: `rdc/engine.py`, `rdc/files.py`, `tests/test_coding_context.py`; this report is new.
- Leave original untracked owner workflow/API directives and existing BandMates/Presentation/Atlas projects untouched.

## Test-first defects and minimal repairs
1. **Batch source reads:** In live-equivalent `full-host` mode, an alias can be valid inside the selected project at admission and redirect outside it before `rdc_code_context` reads it. First RED test actually returned synthetic content from an unrelated project. The read path now revalidates the project boundary immediately before each read, then opens the resolved canonical target rather than the original alias. A request that moved outside the selected project returns a bounded per-file `path_denied`. Evidence: `code-context-symlink-swap-RED-20261117.log` and `code-context-symlink-swap-GREEN-20261117.log`.
2. **Literal search:** `Files.search` could receive an enumerated project subdirectory that was swapped to a symlink before the file opened. The original source returned an unrelated project's synthetic matching line. It now resolves each candidate, checks membership in the original search subtree and reads that canonical path; out-of-subtree candidates are counted as skipped. Evidence: `code-context-search-swap-RED-20261117.log` and `code-context-scope-2fix-GREEN-20261117.log`.
3. **Cross-platform test compatibility:** New symlink tests explicitly skip when file/directory symlink creation is prohibited by the OS. Actual Windows and Linux hosted runs on this exact branch remain UNVERIFIED.

## Verification results and boundaries
- Focused coding/security tests: 8/8 PASS, zero failures on the iMac, with the actual production worker untouched.
- Full Python worker regression: 372 tests, 0 failures, 26 skips, final code and test revision; evidence: `code-context-scope-FINAL-worker-full-20261117.log`. Existing test warnings mention transient relay-fixture disconnections and SQLite ResourceWarnings; suite verdict remains green.
- Isolated Node gateway regressions: 45/45 PASS, zero failures; gateway code unchanged. Evidence: `code-context-scope-gateway-full-20261117.log`.
- Isolated production gateway build: PASS. ESLint: zero errors, one preexisting Next.js image warning. Evidence: `code-context-scope-FINAL-gateway-build-20261117.log` and `code-context-scope-FINAL-gateway-lint-20261117.log`.
- Alternating two-run 30-trial local source comparison, 60 successful observations per version: original code-context p50/p95 = 8.619/9.144 ms; hardened version = 9.120/10.020 ms. New checks added approximately 0.501 ms or 5.8% local p50 overhead on the synthetic 60-file task; correctness was 60/60 each. The gateway/AI host operation count remains one instead of three. No claim of live cloud speed improvement. Evidence: `code-context-scope-60-trial-comparison-20261117.json`. Performance target remains OPEN.
- Real existing RDC v16 worker smoke: direct authorized `rdc_job_run` captured both stdout and stderr, exact intentional exit 23, and one identical retry returned the original job ID. No user files were modified.
- Historical published CI: GitHub run 44025075522 succeeded for published SHA 0e3058292dac6555663548614276ad28dea1a2fe only. It does NOT validate this scoped new branch.
- GitHub connector repo permission observed: pull=true, push=false. No publication or GitHub Actions run for this branch. No original repo branches or pending owner files overwritten.
- Superpowers methodology applied: test-first failures, scoped debug, minimum fix, refocused tests, whole-suite checks and separate review. External callable Superpowers, hosted AI broker, and actual AI swarm dispatch remain UNVERIFIED/UNAVAILABLE. REA binary inspection unnecessary for fully available Python source.
- Unknown residual OS directory-replacement races outside the two injected interleavings should be independently reviewed; no claims of complete adversarial filesystem security or multi-OS qualification.

## Release gate and review request
TOC/Atlas independent reviewer: inspect two source edits and tests on the exact reviewed commit; repeat focused tests on macOS, Windows and Linux as permitted and decide ACCEPT SCOPED / REWORK. Keep owner-private RDC Site on v16 and v17 activation on HOLD. A protected inactive compatible rollback version has not been verified. The original v16 reader must never serve as post-inline rollback. Do not touch existing production D1/R2, worker, App/plugin identity, browser UI or BandMates.
