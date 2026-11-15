# Credential Enrollment Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this focused change. Parent-approved scope is owner enrollment/removal in the existing worker UI.

**Goal:** Let the owner register and remove a named saved credential without editing private JSON.

**Architecture:** Keep the existing broker and mapping schema. Add two owner-only HTTP endpoints and a compact form beside credential permissions. Enrollment records a locator and does not read a vault; existing consent remains necessary for every new fill or persistent grant.

**Tech Stack:** Python, SQLite, Starlette, existing vanilla JavaScript owner UI, unittest and Playwright.

**Spec:** `docs/CREDENTIALS.md` and the parent task's explicit enrollment/removal scope.

## Global Constraints

- No password inputs, native vault enumeration, bulk export, new MCP tools, or changed agent privileges.
- Enrollment generates the opaque credential UUID on the worker.
- An exact HTTPS origin and supported native locator must pass the existing mapping validation.
- Preserve existing mappings on invalid input or a failed write. Replace through a private temporary file and atomic rename.
- Removal invalidates that alias's grants and unadmitted requests; it leaves sessions and already-admitted input alone.
- Do not restart the persistent worker on port 8765. Test with synthetic providers and separate fixture workers.

## Review Focus

- Agent token attempts to enroll/remove must fail before any file mutation.
- Malformed input or malformed existing configuration must preserve the prior file.
- Rename failure must leave the old file intact and clean up the private temporary file.
- Removing an alias during native lookup must prevent a later unadmitted fill.
- The owner form must not retain locator fields after save or disconnect, and must never trigger a vault read at enrollment.

## Task 1: Private mapping enrollment and removal

**Files:** `rdc/credentials.py`, `rdc/server.py`, `tests/test_credentials.py`.

**Interfaces:** `CredentialBroker.enroll(label, origin, provider, locator)` returns a public alias only. `CredentialBroker.remove(credential_id)` returns removal status. Owner routes are POST `/api/credentials/enroll` and POST `/api/credentials/remove`.

- [x] Add failing tests for private atomic writes, preservation on validation/write failures, agent rejection, and removal during a provider wait.
- [x] Share the existing configuration validator between reads and enrollment.
- [x] Implement private atomic replacement and owner-only routes without native provider access.
- [x] Run broker and adapter credential tests.

## Task 2: Compact owner setup form

**Files:** `rdc/web/index.html`, `rdc/web/app.js`, `rdc/web/styles.css`, `tests/test_credentials.py`.

- [x] Add a collapsed setup section with name, HTTPS origin and provider-specific locator fields.
- [x] Render existing aliases with a remove control; reset locator fields after save and disconnect.
- [x] Add a real owner-UI test using a separate synthetic worker/provider: enroll, request fill, owner consent, redacted status, remove.
- [x] Transfer only scoped source files to the iMac, run focused tests on fixture ports, and report the observed results.

## Verification and review record

- The four initial backend tests failed before enrollment/removal existed, then passed.
- The owner browser test first failed on the missing form. Its next run identified an origin-to-server auto-fill race; removing that optional suggestion produced the expected enrollment. Separating the provider label from its select options made its accessible name exact.
- Independent review found pagehide-retained locator fields and partial file-success/database-failure removal. Each was reproduced. Pagehide now uses local disconnect cleanup. Removal retries clean consent records even when the mapping is already absent, with fixed partial-failure messages and an owner retry control. No mapping or grant is restored.
- Local broker/adapter verification: 19 tests passed. The removed-alias provider fixture now joins its released thread before deleting its temporary database.
- iMac verification: `.venv/bin/python -m unittest tests.test_credentials -v` passed all 23 tests in 13.627 seconds, with no skips or errors. The full combined suite is assigned to the parent integrator.
- The owner form was visually checked at a 390-pixel viewport using `test-results/credential-enrollment.png`, containing only synthetic account data.
- All work used fixture workers and synthetic providers. The persistent worker on port 8765 was not restarted, and no native vault was read.

## Rulings

- Use the parent-assigned shared checkout and scoped files so the integrator can combine parallel changes; no independent commit or deployment was made.
- Treat a database cleanup failure after file removal as a recoverable partial result. Repeat removal is idempotent and never restores an alias or grant.
- Assert disabled state on the actual editable input. The installed Playwright implementation does not classify a fieldset itself as a disabled interactive control.
