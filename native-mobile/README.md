# RDC native mobile companions (development source)

Native iOS SwiftUI and Android Java source for the independent RDC status
companion. These implement the same least-privilege gateway API as the
installable web companion, not mobile OS automation or a full-control client.

Both apps accept an owner-entered HTTPS origin and read-only status token,
use the platform's standard certificate trust, reject redirects, bound
response sizes, and avoid persisting tokens. No third-party tracking or
account login is required. Clear the session to discard entered state.
The app does not accept a device key or execute MCP commands. No ChatGPT,
Sites, Cloudflare, or hosted maintainer relay is required.

## Android

Prerequisites: JDK, Android SDK Platform 36, Build Tools 36.0.0. An owner
must review and accept the relevant SDK licenses before package installation.
The build script does not accept licenses, download dependencies, generate
signing secrets or install on a device.

Set JAVA_HOME and ANDROID_HOME for the approved SDK and run
./android/build.sh. The resulting aligned APK is unsigned.
Sign it with Android's apksigner using an owner-held development or release
key, verify its signature, and install only on the explicitly authorized
device. No keys or credentials belong in this repository.

## iOS: standalone command-line packaging

The owner has authorized Xcode for packaging and native test-driver setup,
while retaining independent RDC runtime operation. The standalone packaging
helper remains an optional route using an explicit standalone Swift compiler
and a separately supplied, legitimately obtained iPhoneOS device SDK.
It rejects paths inside Xcode.app and does not download SDKs or accept
licenses. The Xcode project specification is also supported for packaging.

Inspect current readiness without an SDK or credentials:

    python3 ios/standalone.py doctor

With a compatible owner-supplied SDK:

    python3 ios/standalone.py doctor --sdk /OWNER/SDK/iPhoneOS.sdk
    python3 ios/standalone.py build --sdk /OWNER/SDK/iPhoneOS.sdk --out ios/build/RDCMobile-unsigned.app

The build step produces an unsigned app bundle only. To sign a physical-device
development package, obtain a valid Apple-issued development certificate and
an explicit RDC provisioning profile covering the exact selected phone. The
certificate and its private key must already be present in the owner's local
keychain. Do not revoke other certificates, export private keys, use ad hoc
signatures, disable ATS, or override certificate validation.

    python3 ios/standalone.py sign --app ios/build/RDCMobile-unsigned.app --profile /OWNER/PRIVATE/RDC.mobileprovision --device OWNER_DEVICE_ID --identity OWNER_CERTIFICATE_SHA1 --out ios/build/RDCMobile.ipa

Use local private variables for the owner device and signing identity values,
not shared logs. This verifies the profile's expiry, iOS platform, explicit
bundle entitlement, registered device and authorized certificate, then signs
a temporary copy, checks minimal entitlements and strict local signature
verification, and creates a fresh IPA. Apple's device installation service
remains the authority for signing and provisioning. The helper never installs
an application. A compatible SDK/toolchain and Apple signing prerequisites
are still required. The November 23 Xcode route produced a signed development
app and IPA and installed the app on the owner-selected iPhone; the initial
launch still required investigation of the device's developer-profile trust.
See docs/releases/RDC-MOBILE-INSTALL-20261123.md for the precise evidence.
The direct USB developer-service path is separate and does not require Xcode.

For the optional owner-approved Xcode route, install the compatible official
Apple release, review and accept the first-launch license, finish the required
platform setup, and sign into Xcode with the owner's development account.
Run ios/build-xcode.sh unsigned to compile without signing. The signed mode
requires the exact owner-selected development team and iPhone in local
environment variables RDC_APPLE_TEAM and RDC_IOS_DEVICE. It does not install
the application or accept agreements. Provisioning updates are disabled by default.
After owner authorization, set RDC_ALLOW_PROVISIONING=1 to let Xcode manage
the development profile and register only the explicitly selected device.
The helper requires the existing signed-in Apple account and never exports
private keys or revokes certificates.

If Xcode shows a certificate but security find-identity reports zero valid
code-signing identities, compare matching identities with valid identities
before creating another certificate. A missing Apple intermediate can cause
this discrepancy. Obtain only the matching intermediate from
https://www.apple.com/certificateauthority/, verify its chain, and install
it with normal Keychain trust; do not override trust or revoke the identity.

Physical iOS installation may still require the owner to trust the developer
profile in Settings > General > VPN & Device Management. An installed bundle
is not evidence of a successful launch. Preserve the launch result and verify
the running process independently. Personal Team development profiles expire;
inspect the actual embedded profile expiration before reuse.

The independent gateway /mobile/ PWA remains the lower-friction installation
option on either platform. Physical device acceptance, full native UI control,
signed distribution and production release gates remain separate.
