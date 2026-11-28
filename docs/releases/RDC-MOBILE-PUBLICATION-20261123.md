# Mobile build publication materials — November 23, 2026

The mobile candidate remains on `feature/rdc-mobile-install-20261123`, stacked
above the existing speed candidate. It is review material, not a production
release. No worker, gateway, VPS or app-store deployment is included.

## Included artifacts

- GitHub: native Android/iOS source, optional Xcode and standalone build
  helpers, exact-device installation instructions, current qualification
  notes, and the signed Android development APK.
- Existing private ChatGPT RDC plugin: guidance version **1.0.34**, with
  mobile setup/capability instructions, Android development APK, native
  source ZIP, installer manifest and checksums. Its original private
  audience, App/MCP binding, presentation and unrelated skills are retained.
- Owner-private delivery: signed iPhone `.app` and `.ipa`, Android APK,
  installer instructions and hashes. The iPhone profile is device-specific
  and expires 2026-12-01 at 02:28:07 UTC; it is excluded from GitHub and
  plugin archives, as are all signing keys and credentials.

See [native installation](../../native-mobile/README.md),
[artifact manifest](../../native-mobile/installers/manifest.json), and
[physical qualification evidence](RDC-MOBILE-INSTALL-20261123.md).
The native companion remains a read-only gateway status client. Android
hardware, swipe/scroll, usable privacy-safe live preview, wireless/recovery,
app switching, Xcode-free WDA startup, iPad, expanded UI and production
qualification remain open.

## Verification and version boundaries

This publication changes documentation and packaging only. It preserves
`2ba8e68` signing/build evidence and `2328f7c` native adapter fixes. Static
review covered changed files, archive membership, JSON manifests, installer
hashes and absence of owner signing/device identifiers in publication text.
The saved plugin's changed files and both binary support archives were read
back from its current release; every original plugin path remains present.
Saving guidance is not a live-host or worker-runtime test.

The combined mobile-resume campaign remains **97/100**, including failed
trials and all regression reruns. No runtime tests or device trials were
added for packaging. The publication commit uses `[skip ci]` to avoid the
inherited uncapped push/PR workflow. CI is skipped, not reported as passing;
future testing must use the governed combined budget. The portable worker
version remains `0.1.0-alpha.8` / Python `0.1.0a8`; the private plugin's
`1.0.34` guidance version is independent.
