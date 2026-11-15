# RDC Guardian Reporting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox syntax for tracking.

**Goal:** Automatically collect a bounded private incident history and expose RDC's actual recovery state without disrupting operations.

**Architecture:** A standard-library recorder sanitizes to a finite event schema, submits through a bounded in-memory queue, and writes a private SQLite store. Worker and relay hooks record fixed outcomes; a read-only tool and CLI report safe summaries. Existing reconnect and no-replay logic stays authoritative.

**Tech Stack:** Python 3.11+, unittest, SQLite, threading and queue; existing RDC MCP catalog and CLI.

**Spec:** `docs/superpowers/specs/2026-11-15-guardian-continuation-design.md`

## Global Constraints

- No private names/emails in public source. Brand is RDC (Remote Desktop Commander) by TOC Ministries.
- No new third-party dependency or paid API.
- No secret, argument, raw exception message, path, browser content or arbitrary text in stored diagnostic events or exported reports.
- Retain at most 2048 event rows; report at most 50 entries; use a queue with at most 256 records.
- Producer submissions do not wait for disk or network. Storage failure cannot change an authorized operation's result.
- Preserve owner pause, review mode, credential grants, process ownership and the existing no-replay contract.
- Do not install, deploy, publish, update live configuration or restart the iMac during implementation.

## Review Focus

- A storage path is replaced by a symlink or nonregular file: diagnostics must refuse unsafe writes and report unavailability without blocking the main task.
- A slow or locked database and event burst: queue and retention remain bounded, dropped events are visible, and work continues.
- An unknown exception embeds a synthetic password or path: only a fixed safe category reaches disk and the tool.
- Shutdown occurs while the queue is full or writer failed: close remains bounded and incomplete capture is explicit.
- Relay result delivery is uncertain: incident recording never redispatches the underlying action or labels a retained upload as a completed user task.

## Task 1: Implement and integrate private diagnostics

**Files:** Create `rdc/diagnostics.py`, `tests/test_diagnostics.py`, and `docs/DIAGNOSTICS.md`. Modify `rdc/engine.py`, `rdc/relay.py`, and `rdc/cli.py` only where needed for recording, lifecycle and a read-only diagnostic surface. Add focused integration tests in existing related tests only when needed. Do not change package versions, generated embedded bundles or gateway assets; root handles release integration.

**Interfaces:** Implement a recorder with nonblocking `record(component, event, tool=None)` over finite allowlists, bounded `snapshot(limit=50)`, and bounded `close()`. The implementer may choose concrete class and constructor names, documented in its report. Add `rdc_diagnostics_status` with optional integer limit 1..50, read-only annotations, and `rdc diagnostics --state-dir ...` output. No action or arbitrary text parameter is exposed.

- [x] Write meaningful failing tests for private finite data, bounded queue/retention, writer failure, safe path handling and shutdown.
- [x] Implement the recorder and make the focused tests pass.
- [x] Add worker and relay hooks while retaining existing results, exceptions, approvals and reconnect/no-replay behavior.
- [x] Add tests proving failed operations are recorded, successful reconnection is distinguished from an attempt, and reporter failure does not change the underlying operation.
- [x] Add the read-only tool and CLI with bounded safe output and no new permission path.
- [x] Document actual automated recovery, missing capture, and the need for verified code repairs. Run focused tests and the available project suite; report environment-related limitations precisely.
- [x] Commit only task files and write the task report.

## Task 2: Review and qualify the release

**Owner:** Root after Task 1. Independently review the diff and privacy/no-replay cases. Integrate required repairs. Set the next core version, synchronize the gateway catalog from exact source, and qualify the frozen candidate on the iMac using its existing virtual environment. Preserve the installed worker until the approved installer passes quiescence and identity checks. Reconcile any already-running prior publication before updating public source, gateway and saved plugin guidance. Verify live version/catalog and read-only diagnostics after installation.

- [x] Independent spec and code-quality review.
- [x] Frozen full iMac suite and source hash receipt.
- [x] Gateway tests, type check and production build.
- [x] Exact-source activation with preserved config/grants and retained rollback evidence.
- [x] Public/source and plugin readback, or precise external blocker with all reviewable work ready.

## Completion evidence, 2026-11-15

Task 1 was implemented in `5f90840383e826238a13b3e873583a8628ca5355`, with the task report retained in the development record. Independent review passed, including 21 diagnostic tests and 55 relay tests with no skips. The reviewed changes preserve finite private data, bounded capture, operation results and no-replay behavior.

Task 2 qualified frozen runtime `4a18ec0a87d30d4f37dea9b03a611098e14bc527`: the complete iMac gate passed 254 tests with no failures, errors or skips, and all 54 frozen inputs were unchanged. The [sanitized receipt](../../verification-results-0.1.0a4.json) records the exact hashes and outcomes. The matching gateway passed nine tests, TypeScript checking and its production build, then deployed successfully. Exact-source activation preserved configuration, grants, identity, pause state and protected file metadata while retaining rollback code. Native ChatGPT status confirmed alpha4 after activation and deployment; the local diagnostic CLI read the real store successfully. Existing private plugin 1.0.4 and its preserved App binding and audience were read back.

The public source at [`e4f6f18c8d1002462fccd93f85a1be1e1983cb52`](https://github.com/TOC-CS/RDC/commit/e4f6f18c8d1002462fccd93f85a1be1e1983cb52) matched approved local source `12335ccedf6e6464ae8924b051b2742296afd2d3`: all 225 manifest paths, blob IDs, modes and sizes matched, with no missing or extra files. Its [hosted matrix](https://github.com/TOC-CS/RDC/actions/runs/43699939501) completed successfully. Ubuntu and macOS each executed and passed 254 tests with no skips. Windows reported 254 discovered tests: 237 executed passes and 17 documented POSIX-only skips.

Later native checks confirmed the same online, idle alpha4 worker and a ready, available diagnostic report with `incomplete: false`. The host catalog now exposes 53 model-visible tools, matching 54 server tools with the preview-frame tool reserved for the app. Native mobile listing succeeded but returned no configured profiles or sessions and `available: false`. Skill guidance now requires the host's advertised account routing where present and preserves that account across recovery.

The completed release steps retain explicit qualification limits. Windows secure diagnostic capture is unavailable. The hosted macOS timeout-fixture warning remains unattributed; targeted review supplied no evidence justifying a runtime change. Requested ChatGPT branding, production embedded rendering and physical-phone qualification remain unresolved. The observed "App unavailable" preview failure has no confirmed cause. See the [verification record](../../VERIFICATION.md) for exact run times, skipped contracts and those remaining boundaries. This completed finite-reporting plan does not establish implementation or deployment of a broader automatic-repair guardian.
