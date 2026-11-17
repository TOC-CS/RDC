# RDC gateway status validation and no-side-effect rejection
TOC Ministries | November 17, 2026 | source-only candidate

Observed issue: owner-scoped rdc_connection_status previously accepted extra model-supplied fields silently. rdc_operation_status also ignored extra fields and ran the durable cleanup sweep before rejecting invalid diagnostics values, allowing malformed requests to consume D1 maintenance queries and mutate expired rows despite no valid recovery request.

Repair: strict zero-field validation for connection status; strict allowed-field and type checks for operation status before clean(env). Valid owner authentication remains required first. Valid recovery calls still execute original cleanup and preserve queue expiry/unknown outcomes and original operation identity. No new identity fields can be model-provided to override owner binding.

TDD: two focused tests initially failed. One checks injected fields/types are rejected without secret leakage or journal writes after initial owner enrollment; the other checks invalid recovery cannot alter an expired queued row, while valid recovery expires it and returns its original operation ID. After minimum patch, focused tests passed 2/2 and full gateway 61/61.

This is a staged source hardening candidate, not a deployed version. Broader Python tests, CI and live version-readback remain independent gates. See docs/superpowers/specs/2026-11-17-rdc-platform-wide-development-scope.md for full workstreams including performance, reliability, security, functionality and compatibility.

## Final local regression qualification
- Node gateway full suite: 61 tests passed, 0 failed, 0 skipped.
- Python full suite: 478 tests, zero failures and 43 skipped, completed on authorized iMac.
- Production vinext build: complete.
- ESLint: zero errors, one existing next/no-img-element LCP warning.
- git diff --check: pass.
- Functional effect is strict input validation and no database cleanup for invalid status/recovery calls. Query/latency reduction for real valid workloads remains unmeasured until source-identifiable private Site deployment.
- Other RDC workstreams continue under the complete platform scope file, including speed, efficiency, security, resilience, browser and file/terminal behavior, software integration and release verification.
