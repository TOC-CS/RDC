# RDC mobile development installers

The included Android APK is development-signed, API 26 minimum / API 36 target.
Its signature and alignment were verified during the build; no physical
Android installation or app-store release is qualified. The private key is
not included. Inspect [manifest.json](manifest.json) for exact bytes/SHA-256,
platform evidence and open gates. See [build/install instructions](../README.md).

The iPhone app/IPA is delivered privately to its provisioned owner device.
Its profile expires 2026-12-01 at 02:28:07 UTC. Build and sign the iOS source
for your own device; no universal IPA, TestFlight or App Store release is
provided. Native status clients and host-side native automation are separate.
