# RDC preview recovery and speed implementation plan

**Goal:** Repair source binding, floating lifecycle and unnecessary frame wait; publish verified fixes to the existing GitHub source, installed worker and private ChatGPT App/plugin.
**Architecture:** Keep exact source/device ownership, single-flight reads, original pending IDs and host-confirmed presentation. UI changes are backward compatible with the existing v16 worker and gateway. Do not deploy the unrelated inline-result/V2 migration. The independently numbered preview-only Site release is v17.
**Tech stack:** Existing Python worker, JavaScript MCP Apps SDK 2.0.4, bundled HTML, Sites gateway.
**Scope:** Current owner request supersedes historical preview deferral and publication hold for these verified bug fixes only. It does not authorize claiming unmeasured end-to-end performance.

- [x] Add failing synthetic-host tests: late valid input after an unbound result recovers the exact session; pending open cannot float; frame cadence follows measured read time; slower reads retain backpressure.
- [x] Implement in rdc/embedded/src/app.js: remember an unbound result for explicit input recovery; require confirmed ready source before automatic floating; schedule successful frames with max(250,min(1500,elapsed_ms)) wait. Failed and pending paths retain existing recovery semantics.
- [x] Run governed focused tests and necessary existing isolation/lifecycle/recovery tests, at most 100 executions across the entire campaign. Record every red/green run and live trial.
- [x] Build the bundle, inspect diff, and verify real iframe rendering with isolated fixture sources where possible.
- [x] Commit/push exact source with [skip ci] to avoid inherited unlimited CI. Preserve the draft speed PR.
- [x] Install only verified changed preview assets into running worker, without restarting active sessions. Deploy preview-only gateway update from actual v16 source with rollback available.
- [x] Update existing App-backed plugin source-binding guidance, version and receipts; preserve identity, grants and audience. Verify saved release and live installed hashes.

Review focus: late/out-of-order host input; stale source/device mismatch; hidden/closed task lifecycle; unknown operations never replayed; slow-host polling pressure.

Verification and publication receipts: [preview v9 release record](../../RDC-PREVIEW-V9-REPAIR-20261123.md). GitHub publication is the final step of this commit; its receipt is recorded in the owner delivery report.
