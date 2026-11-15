# Configured Mobile Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate configured mobile sessions into RDC's existing grants, owner UI and read-only embedded preview.

**Architecture:** A separately owned mobile adapter implements the Appium protocol and privacy controls. This work consumes its sanitized session/control contracts and reuses the existing engine and preview lifecycle. Configuration contains owner-only profiles; neither the iframe nor agent supplies capabilities or endpoints.

**Tech Stack:** Python 3.11+, unittest, existing HTTP/MCP SDK, plain JavaScript, pinned MCP Apps SDK/esbuild, Playwright synthetic UI fixtures.

**Spec:** `docs/superpowers/specs/2026-11-15-mobile-preview-design.md`.

## Global Constraints

- Work only in `feat/mobile-devices`; no main-checkout changes, version changes, gateway asset edits or commits.
- `mobile_profiles` defaults to `{}` and is omitted from public settings.
- Preview accepts browser UUID and `mobile-<UUID>` identities; credential/job schemas stay unchanged.
- Native mobile saved-password filling is unsupported; secure fields expose no fill control.
- All device calls in verification use fixtures. Hardware and production host rendering remain unqualified.

## Review Focus

- Profile capabilities/endpoints must never appear in status or preview responses: Task 1.
- A mobile mutation must still queue under review and fail while paused: Task 1.
- Mobile and browser sessions must retain their identities across list refresh and frame capture: Tasks 1 and 3.
- Native secure controls must never render the browser credential chooser: Task 2.
- A screenshot privacy refusal must hide the image without declaring the worker disconnected: Tasks 2 and 3.

### Task 1: Private profiles and unified preview routing

**Files:** Modify `rdc/config.py`, `rdc/engine.py`, `rdc/preview.py`; create `tests/test_mobile_integration.py`; adapt `tests/test_embedded.py` fixtures.

**Interfaces:** Consume `validate_mobile_profiles(profiles)`, `Adapters.status().mobile.sessions`, and `Adapters.snapshot(session_id)`. Produce the existing `rdc_preview_open/frame` response with both session kinds and logical viewport dimensions.

- [x] Add failing tests for private-profile omission, UUID schema separation, mixed preview selection/capture, and existing review/pause gates.
- [x] Run `python -m unittest tests.test_mobile_integration -v` and record the pre-implementation failures.
- [x] Add the configuration field/validator and route preview through the combined adapter status and snapshot contract.
- [x] Run the integration and existing embedded contract tests; require no unexpected adapter dispatch or secret profile output.

### Task 2: Owner mobile controls

**Files:** Modify `rdc/web/index.html`, `rdc/web/app.js`, styles only if needed; extend `tests/test_dashboard.py` and focused source-function UI fixtures.

**Interfaces:** Consume sanitized profiles `{profile, platform, automation}`, mobile session metadata and control flags. Dispatch only `rdc_mobile_start/observe/tap/fill/swipe/close` with current session/observation identities.

- [x] Add failing checks for configured-profile selection, mobile action routing, secure-field refusal and privacy-specific capture status.
- [x] Implement profile start, mixed session labels, mobile observed controls and bounded viewport swipe input; disable browser-only controls for mobile.
- [x] Preserve structured error codes and hide refused captures without disconnecting a reachable worker.
- [x] Run source-function fixtures and the dashboard browser suite where the environment permits; report browser skips explicitly.

### Task 3: Embedded mobile preview

**Files:** Modify `rdc/embedded/src/app.js` and `index.html`; extend `tests/test_embedded_ui.py` and focused source-function fixtures. Rebuild only the worktree's embedded HTML when needed for UI verification.

**Interfaces:** Keep the existing host bridge and read-only preview tools. Labels consume session kind/platform/profile/input notice; capture privacy errors retain their stable code.

- [x] Add failing mobile-label/shared-input and privacy-refusal checks while retaining ended-session recovery assertions.
- [x] Generalize browser-specific copy, show the mobile input notice and hide privacy-refused frames without changing session lifetime.
- [x] Rebuild the pinned embedded resource and run focused integration/UI checks, preserving explicit environment limits.
- [x] Review the scoped diff and hand integration evidence to the coordinator. No commit is part of this authorized task.


## Execution evidence

- Used the existing pinned project virtual environment at the baseline checkout as a read-only test executable. Ambient Python had an incompatible older MCP import and was excluded from evidence.
- Task 1 failed first on the missing configuration field and preview contracts, then passed all 8 integration and existing embedded contract tests.
- The first 5 source-function UI tests failed on the missing profile UI, browser-only labels, native secure-field forms and disconnected privacy status. All passed after implementation.
- Additional lifecycle checks reproduced 5 failures for capture-failure status, ended-device polling and disconnected input wording. The 11 source-function UI contracts now pass, including native swipe coordinates, exact action identities and cleanup states. These are JavaScript behavior fixtures, not browser rendering or hardware evidence.
- The final focused gate ran 20 tests successfully: 5 mobile integration, 11 JavaScript source-function contracts, 3 existing embedded contracts and 1 self-contained resource check.
- Rebuilt the embedded resource with the unchanged pinned package lock and a read-only link to the baseline's installed dependencies: 2,021,123 bytes; 8 bundled package licenses; SHA-256 `76d75f7feaa8b95f7a0887725e646f75f37f9b2c53c9cb1bdfeb2ac6359a0f1c`. Source JavaScript syntax checks and `git diff --check` passed.
- Attempted both extended browser-backed classes with a task-local temporary directory. Chromium failed at `process_singleton_posix.cc` because its socket operation is forbidden in this environment. Both classes were skipped; this provides no rendered UI or host-layout pass.
- No production device, native credential provider or host browser has been used. Whole-branch regression and independent review are coordinated separately after all owners freeze their files.
