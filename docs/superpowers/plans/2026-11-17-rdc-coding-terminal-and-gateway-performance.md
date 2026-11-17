# RDC Coding + Terminal + Gateway Performance Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:systematic-debugging, superpowers:test-driven-development and superpowers:verification-before-completion. Keep work isolated.

**Goal:** Improve coding workflow speed/accuracy and remove unnecessary cloud status database operations without weakening durable terminal behavior.
**Architecture:** Use an expiry-aware read-only gateway health path; retain existing normal admission and D1 cleanup. Enhance code_context source searches and relative file resolution within its selected project, with an opt-in all-files search mode.
**Tech stack:** RDC Python worker, Cloudflare D1 gateway (ESM), unittest, Node test runner.
**Spec:** docs/superpowers/specs/2026-11-17-rdc-coding-terminal-and-gateway-performance.md

## Task 1: Cloud status fast path
- [ ] Write failing gateway test to prove rdc_connection_status performs no cleanup UPDATE/DELETE and reports expiry-aware pending counts, including one expired queued and one live claimed row.
- [ ] Run RED.
- [ ] Separate status handling from clean() in gateway MCP route, retaining owner validation. Update status SQL to exclude expired queued rows without mutation.
- [ ] Run GREEN and all existing Node gateway tests. No Site migration.

## Task 2: Safe relative project paths for coding
- [ ] Add failing tests: relative path "app.py" resolves against selected project; "../outside" denied even in a granted sibling project, and alias swap does not cross boundary.
- [ ] Run RED.
- [ ] Implement project-root resolution at initial admission and immediate read; preserve paths ordering/version SHA and failure independence.
- [ ] Run GREEN and all code_context tests.

## Task 3: Fast source-only search
- [ ] Add tests: default source mode skips .git, node_modules, .venv, __pycache__, .next, dist, build, target; explicit all mode includes generated matches; rdc_file_search unchanged.
- [ ] Run RED, implement restricted directory pruning with os.walk followlinks disabled and existing resolution rechecks.
- [ ] Run GREEN and source benchmark with 500+ synthetic generated files, 10+ source files, repeated samples and full match correctness.

## Task 4: Terminal and coding qualification
- [ ] Run matched harmless terminal commands through actual ChatGPT RDC, document host vs device job elapsed and known uncertainty.
- [ ] Run full local Python worker suite, all Node gateway tests, static compile and diff check through actual RDC tool calls.
- [ ] Save exact commit, source Git bundle, scenario measurements, and source test hashes to RDC project. Do not change live private Site v16 or worker.
- [ ] Record future 30+ paired RDC vs DC live acceptance requirements for single call, code workflow, cold init and reliability.

## Review focus
- No silent execution under read-only code-context tool.
- Scope must remain selected project for every requested file, including relative paths and symlink swaps.
- Source search excludes generated dirs only in the new source-mode, and returns truthful scanned/skipped/truncated metadata.
- Status must not report stale expired queue entries as pending when cleanup is deferred.
- No side effects or duplicate command execution after uncertain network/tool failures.
