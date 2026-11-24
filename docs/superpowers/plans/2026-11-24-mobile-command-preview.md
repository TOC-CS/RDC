# Mobile command-engine preview implementation plan

> Use Superpowers executing-plans, test-driven-development,
> systematic-debugging and verification-before-completion for the remaining
> work. Use independent review before any production integration.

**Goal:** Improve client-neutral mobile command selection, correct input,
and time to usable controls without sacrificing verification.

**Architecture:** Reuse the existing MCP device adapters and durable host
jobs. Separate the mobile sandbox interpreter from host execution. Bind
visual inputs to a fresh verified observation.

**Spec:** [Mobile command engine](../../MOBILE-COMMAND-ENGINE.md).

## Constraints and review focus

The total test budget is 100 checks per campaign. Do not rerun failed
mutations, replace an unknown session, weaken privacy checks, use personal
test data in publications, or qualify performance without matched correct
physical measurements. Review wrong-device scope, stale frame/receipt,
lost responses, simultaneous releases, and signing/installation identity.

## Steps

- [x] Isolate public source from private history using an allowlist.
- [x] Verify 30 selected command, lifecycle, visual and terminal regressions.
- [x] Build the versioned iOS and Android companion sources.
- [x] Diagnose the Android signing-input failure and verify the corrected
  package against the existing generic development signer.
- [ ] Verify and publish generic installers, setup guide and hashes.
- [ ] Independently qualify a signed mobile-device installation and verify
  real command results, correct gestures and responsiveness.
- [ ] Verify connected catalog and current plugin/worker compatibility.
- [ ] Compare at least 30 correct matched samples against the mobile
  latency targets. Keep all unmeasured or failed gates open.

Production activation requires the existing release gates; publication of
a development preview is not device or production qualification.
