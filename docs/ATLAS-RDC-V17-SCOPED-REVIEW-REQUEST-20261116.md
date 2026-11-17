# Atlas scoped review request: RDC v17 offline acceptance and rollback guard

**To:** Atlas project manager, existing RDC owner session and independent reviewer
**From:** RDC existing build continuation on 2026-11-16
**Requested decision:** Accept locally verified code and test plan for next controlled release-preparation stage, or return specific REWORK. **No authority to activate v17 or mark RDC complete.**

## Context
Continue existing RDC build at:
`/Users/brandondawson/RDC-Development/workspace/rdc-v8-host-validation-20261115`.
GitHub draft PR #1: https://github.com/TOC-CS/RDC/pull/1, branch `repair/preview-v8-host`. Do not open a duplicate implementation or PR. Existing owner-private ChatGPT Site remains live on v16. v15 is the prior pre-inline rollback, and the historical v16 reader is unsafe after v17 inline-only records exist. The BandMates and AI Presentation Agent owners must remain undisturbed.

## Findings resolved by candidate source
1. A compatible rollback factory reads D1-inline and R2 results yet **forces new writes to R2**, with the original owner authorization, retained terminal IDs, TTL, hash consistency and no replay.
2. Regression tests cover exact UTF-8 JSON result lengths **8192 and 8193 bytes**, both ASCII and multibyte, including inline/R2 decision, readback, TTL and owner isolation.
3. A worker forging `structuredContent._rdc_gateway_operation_id` or `_meta['rdc/operation_id']` cannot override the gateway-owned operation ID on first delivery or idempotent recovery. The exact original worker upload remains in storage for integrity checks.
4. The original RDC logo is preserved. Compact branding reduces real compiled HTTP `initialize` from **1,328,374 to 46,594 bytes** and `resources/read` from **2,060,992 to 779,192 bytes**. The local preview is byte-for-byte unchanged outside a single full-resolution PNG-to-thumbnail data URI substitution. Both independent/offline and cloud resources use the checked-in branded 192x192 thumbnail.

## Local evidence and validation
- Source implementation commit before final test-only audit docs: `5c0242b166398eedc0506fcb0a6b383d4e085d0f` (Git tree `ba798fce8513d24b152c0d498759acc905fda129`).
- Gateway: **43 of 43 tests pass**. Full local worker suite: **364 of 364 tests pass**, on the optimized source. Browser-based embedded UI test suite: **34 of 34 pass after correcting an asynchronous resize-assertion race**. The first independent visual run had 33 passes and one premature height assertion; the isolated original test and entire rerun passed after waiting for the confirmed resize/frame layout.
- Production v17 gateway and separate rollback-compatible production builds passed. Gateway lint: zero errors, one existing unrelated Next.js image warning.
- Actual HTTP behavior checked for compiled old and new gateway bundles on loopback with synthetic owner/device settings and isolated local D1/R2. Unauthenticated status/tool calls and wrong device key consistently return HTTP 401. No live production data or credentials used.
- Final rollback-compatibility archive on Mac:
`/Users/brandondawson/RDC-Development/checkpoints/rdc-v17-rollback-fullopt-20261116/rollback-compatible-site-source-and-build.tar.gz`
SHA-256: `7b720e83474e784177c03c9b024e6f32844d0c603f7e8735f655b76e5e35d3ba`.
Compiled rollback gateway chunk SHA-256: `a9aa4368d72c17caf97bc8cf16548e5a0815f899bbccf5cd23b8ae6afe38e9da`. D1 `DB`, R2 `BUCKET`, migration hashes and compiled forced-R2 writer checked. No Site version has been created from this archive.
- Evidence and runnable local HTTP probes:
`/Users/brandondawson/RDC-Development/checkpoints/rdc-v17-gateway-review-20261116/`.
- Detailed evidence and release gates:
`docs/releases/RDC-V17-ROLLBACK-REVIEW-2026-11-16.md`.

## Release blocking decisions for Atlas
1. **Protected inactive Site version missing.** Existing Site version management is not exposed in this Chat session. Save and verify the rollback-compatible artifact on the SAME owner-private Site, preserving D1/R2 and App/plugin identity, **before** any v17 inline writer activates. Verify exact version ID and archived SHA. Refuse release if this cannot be proven.
2. **Latest source not pushed to existing GitHub draft PR.** This chat's GitHub connector is read-only and local Git push returned missing authentication. The branch's remote HEAD remained `3bfd044b2c0aa5ea35709dbb83b20d1a623dc32d`. Retain the local commits and offline Git bundle. Once source push is independently authorized and possible, run GitHub Actions on the precise published commit across macOS, Linux and Windows. Do not claim those results now.
3. Atlas independently review v16 rollback incompatibility, correct compatible Site rollback selection, byte boundaries, forgery handling, TTL/no-replay and owner isolation. Mark scoped source ACCEPT only with evidence; keep activation blocked pending live release gates.
4. Maintain all other RDC open requirements: true host-supported in-app PiP, upstream host-owned rogue Software Cursor, outer ChatGPT App logo/publisher identity, native Windows/Linux capture, BandMates integration qualification and postdeployment cloud speed measurements. This scoped source review cannot mark whole RDC project complete.

## Operational safety
Avoid Site/D1 production migrations, v17 activation, production worker restarts, Git history force-pushes, App/plugin recreation, and live user GUI interference. Existing owner task sessions and their uncertain no-replay identities must remain intact. REA static comparison could not finish because the installed macOS Swift process-ownership helper failed to compile; its error and partial evidence were retained, and we did not modify the system Xcode/REA installation.

**Required follow-up from Atlas:** ACCEPT SOURCE / REWORK with precise failures, and identify the permitted owner of the protected inactive Site version + GitHub auth/CI work. No blanket deployment or completion approval is requested.
