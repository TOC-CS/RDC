# Search-to-Source One-Call Coding Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development, systematic-debugging and verification-before-completion. Use isolated worktree for source modifications.

**Goal:** Search and automatically read matched project source files within one RDC cloud tool call.

**Architecture:** Extend existing read-only rdc_code_context schema and handler without changing global Files.search or approval policy. Search result paths are revalidated inside the selected project before each hashed read.

**Tech Stack:** Python 3.9+, jsonschema, unittest; generated Cloudflare gateway assets; existing skill Markdown.

**Spec:** docs/superpowers/specs/2026-11-18-rdc-search-to-source.md

## Global Constraints
- Only isolated perf/rdc-rea-search-context-20261118 worktree. No live worker or private gateway changes.
- Maximum 5 automatic matching files, maximum 20 total reads, <=16 KiB per read.
- Default contract unchanged. No automatic replay, do not follow scope escapes.
- Preserve all other owners' uncommitted files and release holds.

## Review Focus
1. Multi-line matches must select unique files once. Test exact paths.
2. Explicit file_paths and matched paths must not duplicate output. Test ordered merge.
3. No query with read_matches greater than zero fails validation. Test rejected.
4. Symlink substituted between search and read remains confined. Test denied.
5. Large matching files return truncated offsets and hashes; no full content disclosure. Test bounded size.

## Task 1: New red tests
- [ ] Add cases to tests/test_coding_context.py for auto matched read, dedup, no query, swapped alias and truncation.
- [ ] Run python3 -m unittest discover -s tests -p test_coding_context.py -v. Confirm expected failure specifically from missing schema feature.

## Task 2: Minimal implementation
- [ ] Add read_matches schema and validation in rdc/engine.py.
- [ ] Extend handler to merge searched filenames into explicit paths with bounds, reuse checked_read and digest output.
- [ ] Verify new cases and complete local coding tests.

## Task 3: Skill, synchronization and verification
- [ ] Update skills/rdc-coding/SKILL.md with precise conditional live-tool usage and fallback.
- [ ] Run source catalog asset generation/sync and cloud gateway tests.
- [ ] Run complete Python suite, git diff --check, and focused negative security tests.
- [ ] Save result log, source commit/hash, REA comparison, release blockers. No production deployment.
