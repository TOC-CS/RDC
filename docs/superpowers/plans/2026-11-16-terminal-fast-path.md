# RDC Single-call Terminal Fast Path Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans task by task.

**Goal:** Return short terminal command results in one RDC tool call with retained durable recovery.
**Architecture:** Extend Jobs.start with bounded Jobs.run wait, add Engine catalog and dispatch, regenerate gateway assets.
**Tech Stack:** Python, SQLite, unittest, Node gateway.
**Spec:** docs/superpowers/specs/2026-11-16-terminal-fast-path-design.md

## Global Constraints
- Preserve durable idempotent jobs, owner permissions and root checks.
- Keep live RDC and BandMates running during isolated source work.
- No speed/quality claim without test output and measured benchmarks.
- No duplicate App, plugin or cloud credentials.

## Review Focus
- Long process never cancelled by first wait timeout.
- Retry with same key never launches another process.
- Paused/review/disabled actions never bypass owner control.
- Windows process startup slower than macOS must not break semantics.
- Bounded output does not exceed relay limits or lose offset correctness.

### Task 1: Durable fast-path tool and tests
Files: tests/test_terminal_fastpath.py, rdc/jobs.py, rdc/engine.py
Interface: Jobs.run(argv,cwd,timeout=None,idempotency_key=None,wait_ms=1500,output_limit=16384) returns job,reused,complete,output.
- [x] Create failing tests for immediate success, pending fallback, deduplication, failure, invalid arguments, owner controls.
- [x] Run targeted tests and verify expected red failure (missing tool).
- [x] Add Engine catalog, validation and dispatch; implement bounded Jobs.run using Jobs.start, status and output.
- [x] Run targeted tests and full worker discovery. Commit.

### Task 2: Gateway contract and baseline
Files: cloud-gateway/lib/rdc-assets.json, cloud-gateway/tests/gateway.test.mjs, docs/PERFORMANCE-TERMINAL-BASELINE-2026-11-16.md
- [x] Add gateway mutation identity and tool-presence contract tests.
- [x] Run red on stale generated catalog, then regenerate and run green.
- [x] Run gateway and TypeScript tests, embedded asset sync and production build.
- [x] Measure direct local fast path vs durable path, record evidence; cloud benchmark after deployment. Commit.

### Task 3: Review, publish, verify
Files: docs/PREVIEW-REPAIR-QUEUE.md and qualified release docs.
- [x] Perform fresh code-review and verify exact tested tree.
- [ ] Publish to existing RDC GitHub branch with authenticated route; verify remote tree and CI.
- [ ] Update existing App-backed plugin skill only if required and preserve owner pairing/audience.
- [ ] Check cursor and foreground non-interference. Record remaining host limitations.
