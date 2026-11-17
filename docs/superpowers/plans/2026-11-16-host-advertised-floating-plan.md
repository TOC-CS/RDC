# Host-advertised floating implementation

> Use superpowers:test-driven-development and verification-before-completion.

**Goal:** Only request automatic in-host PiP when the host advertises the mode.

**Architecture:** Narrow predicate correction in rdc/embedded/src/app.js. Existing MCP protocol, modal, source binding and preview notification contracts are unchanged.

**Spec:** docs/superpowers/specs/2026-11-16-host-advertised-floating-design.md

## Constraints
- Preserve the user's strict prohibition on separate OS windows and automatic fullscreen substitutions.
- No mutating desktop input, no helper kills, no worker or BandMates restart.
- Reuse existing embedded build/sync workflow and gateway project identity, audience, D1/R2 and plugin 1.0.15. Back up old installed resource before activation.
- Do not claim PiP works in current Codex until real in-host acceptance, even if all fixture tests pass.

### Task 1: Host capability guard
**Files:** Modify tests/test_embedded_ui.py and rdc/embedded/src/app.js; generated rdc/embedded/preview.html and cloud-gateway/lib/rdc-assets.json.
**Interfaces:** Reads app.getHostContext().availableDisplayModes; preserves requestAutomaticFloat(), requestMode('pip') and existing source identity.
- [ ] First write failing regression with legacy bridge present and host modes inline/fullscreen, assert no legacy request, no fullscreen and visible note after open and reopen.
- [ ] Rework fixture tests to require host-advertised PiP for positive path; preserve tests for confirmed and unconfirmed replies.
- [ ] Confirm red tests fail for wrong requests on old implementation.
- [ ] Narrow canFloatInHost() to advertised host modes.
- [ ] Run focused and full worker tests; rebuild embedded and gateway assets; verify byte-identical and gateway tests, lint and build.
- [ ] Commit, publish to existing GitHub draft PR, verify exact remote tree; deploy only to existing owner-private Site after saved version inspection, with prior v14 rollback.
