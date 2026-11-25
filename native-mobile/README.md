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

## Development installers and scope

| Platform | Included artifact | Qualification |
| --- | --- | --- |
| Android 8 / API 26 or later | [Signed development APK](installers/RDC-Mobile-Android-development.apk), target API 36 | Build, v2/v3 signature and alignment verified; physical installation pending |
| iPhone, iOS 17 or later source target | Source and signed build instructions below; owner-specific `.app` and `.ipa` delivered privately | One iOS 26.6.1 iPhone install/launch verified; not universal device compatibility |
| iPad | iOS source only | Device installation and native behavior unqualified |
| iOS/Android web companion | Gateway `/mobile/` installation shell | Separate PWA installation/HTTPS acceptance gates |

See [installer metadata and hashes](installers/manifest.json) and the
[installation walkthrough](../skills/rdc/references/mobile-install.md).
The native apps are read-only gateway status clients. Installing one does
not install an RDC worker, Appium, WDA, or a ChatGPT plugin. Installing a
plugin does not install these apps. Native source is in this repository;
the Python wheel alone does not contain these mobile build projects.

The private iPhone development profile expires December 1, 2026 at
02:28:07 UTC (November 30 at 8:28:07 PM US Central). Rebuild/re-sign with
valid owner provisioning after expiration. Do not redistribute its profile
or assume the IPA will install on another phone. No TestFlight, App Store,
Play Store, production signing or public release is claimed.

## Android

Prerequisites: JDK, Android SDK Platform 36, Build Tools 36.0.0. An owner
must review and accept the relevant SDK licenses before package installation.
The build script does not accept licenses, download dependencies, generate
signing secrets or install on a device.

Set JAVA_HOME and ANDROID_HOME for the approved SDK and run
./android/build.sh. The resulting aligned APK is unsigned.
Sign it with Android's apksigner using an owner-held development or release
key, verify its signature, and install only on the explicitly authorized
device. No keys or credentials belong in this repository. This project uses
JDK/Android SDK commands directly and does not require Gradle or Android Studio.

For the included development APK, inspect the adjacent SHA-256 manifest,
then use the owner-selected USB debugging serial:

```sh
adb -s "$RDC_ANDROID_SERIAL" install installers/RDC-Mobile-Android-development.apk
```

Set `RDC_ANDROID_SERIAL` locally to the intended authorized device. This is
an installation command for owner-authorized use, not a completed hardware
test. It deliberately omits replacement/reset/uninstall flags. If RDC is
already installed or its signing key differs, inspect the existing app and
obtain an explicit upgrade decision; never uninstall to bypass that conflict.

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
app and IPA, installed it on the owner-selected iPhone and, after owner
developer-profile trust, independently verified successful launch and its
running process. See [the dated evidence](../docs/releases/RDC-MOBILE-INSTALL-20261123.md).
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

The Xcode signed mode produces
`OUT/DerivedData-signed/Build/Products/Debug-iphoneos/RDCMobile.app`;
it does not create an IPA or install it. With the exact selected device in
`RDC_IOS_DEVICE` and signed app path in `RDC_IOS_APP`, an authorized owner can
install and launch through Xcode's command-line device service:

```sh
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun devicectl device install app --device "$RDC_IOS_DEVICE" "$RDC_IOS_APP"
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun devicectl device process launch --device "$RDC_IOS_DEVICE" org.tocministries.rdc.mobile
```

Check the installation result, owner trust, launch result and an independent
exact-bundle process readback separately. Do not automatically repeat an
uncertain install/launch. For an IPA, the standalone signing helper above
requires an unsigned input `.app`; do not pass the signed Xcode output to it.

Physical iOS installation may still require the owner to trust the developer
profile in Settings > General > VPN & Device Management. An installed bundle
is not evidence of a successful launch. Preserve the launch result and verify
the running process independently. Personal Team development profiles expire;
inspect the actual embedded profile expiration before reuse.

The independent gateway /mobile/ PWA remains the lower-friction installation
option on either platform. Physical device acceptance, full native UI control,
signed distribution and production release gates remain separate.

## Local terminal preview

The development preview adds a private on-device workspace and fixed commands
(help, pwd, ls, mkdir, write, cat, sha256, echo). The gateway status credential
remains read-only. The companion does not become a system-wide automation
service or unrestricted OS shell. Its output identifies device-local
execution. See [the command engine guide](../docs/MOBILE-COMMAND-ENGINE.md).
The earlier installer inventory and hardware evidence describe previous
builds. Use the new versioned manifest when selecting a preview package.
