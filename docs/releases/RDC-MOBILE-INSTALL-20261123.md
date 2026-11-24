# RDC mobile installation development evidence, 2026-11-23

Base source: fb631e8 (audit recovery branch). Isolated mobile candidate only.
No live gateway, plugin, device pairing, production service or public release
was changed. Existing six live acceptance gates and release hold remain open.

| Check | Result |
| --- | --- |
| New mobile installation tests (initial red run) | 5 executed; expected 3 failures, 2 errors before implementation |
| New mobile installation tests (green run) | 5/5 passed |
| Existing native Appium/ADB synthetic checks | 33/33 passed |
| Existing mobile worker integration | 5/5 passed |
| Existing standalone gateway checks | 19/19 passed |

Combined development execution: 67 total, including the 5 deliberately failing
pre-implementation checks; 62/62 final selected checks passed. This total is
under the single owner-mandated 100-case ceiling. Unselected cases remain
untested. JavaScript syntax and Git whitespace checks passed.

The iMac has Apple Command Line Tools only, no full Xcode, no Appium
installation, no working JDK, and no Android SDK/ADB executable. The connected
device inventory lists the iMac and VPS only, with no physical phone.
Real iPhone/iPad and Android installation, native automation, live host
performance, public TLS, signed IPA/APK and store distribution remain unverified.

## Follow-up: real iPhone USB onboarding

Five additional targeted USB onboarding tests passed. The owner-connected
physical iPhone reported product type iPhone18,2 and iOS 26.6.1. The Mac's
USB multiplexer enumerated one USB device; the device service answered, and
its existing host trust was accepted. The owner-local profile generator
created a permission-600 fragment for the exact USB device outside the
repository, without modifying live worker configuration or phone data.
These are USB diagnostic and configuration results only. Full Xcode is absent,
and the host has approximately 6.2 GiB free. Native control and signed
distribution remain open.

## Follow-up: live iOS metrics through RDC worker

Installed the Homebrew libimobiledevice 1.4.0_3 package and required small
dependencies on the authorized iMac. Existing trust validated independently.
A further five synthetic exact-target, schema, privacy, and missing-library
tests passed. A separately isolated RDC Engine using the private iOS profile
returned all six allowlisted live metrics via rdc_mobile_ios_status: storage
capacity, available data capacity, total data capacity, charge percentage,
charging state, and Developer Mode. USB trust and iOS version were also
confirmed. No personal data or device identifier was returned or committed.
No live production worker or plugin change, phone data change, or native
automation session was made. Native controls remain open pending device
Developer Mode, Xcode, and signed WebDriverAgent. Host free space was 9.9 GiB.
The five additional source tests plus this focused live check remain within
the cumulative 100-check campaign ceiling.

## Follow-up: alternative iOS communication backends

PyMobileDevice3 11.63.1 installed in the default isolated uv environment.
Go-iOS 1.3.2 installed from the official npm package; its bundled macOS
universal executable was placed in the private RDC tools directory
without running the package postinstall script. Both communicated with
the owner-selected physical iOS 26.6.1 device. Ten selected source checks
(5 new backend checks, 5 existing iOS status checks) passed. An isolated
RDC Engine returned all six metrics with the default PyMobileDevice3
backend and independently verified the Go-iOS device identity.
libimobiledevice fallback is retained. No tunnel daemon, native UI action,
signed application installation, production changes or phone data changes.
Developer Mode remained disabled. No live release gates are closed.

## Follow-up: developer mode, mirroring and native developer image

Owner enabled Developer Mode and disabled the Mac's Internet Sharing.
The connected Apple iPhone Mirroring window was verified without capturing
phone content. Five new mirroring software checks and three developer
preflight checks passed. An isolated RDC worker successfully detected
available mirroring navigation commands and opened and closed a no-root
USB RemoteXPC tunnel. The initially advertised service count was 61.

The initial PersonalizedDMG mount failed; readback showed no mounted image.
The phone subsequently confirmed compatible Cryptex service and no existing
developer image. A single owner-authorized Apple-personalized Cryptex
first installation succeeded without replacing or uninstalling an image.
Independent readback confirmed both the installed record and mount. The
subsequent developer preflight returned 82 advertised services, including
application and device-info services. Device trust and Developer Mode were
still enabled. No personal device content was accessed or changed by these
development operations. Physical UI action qualification, signed companion
packaging, wireless direct control, and existing production release gates
remain open. No production deployment or merge occurred.

## Direct CoreDevice application launch qualification

A new scoped app-launch campaign exercised six targeted software tests;
all six passed. One bounded live smoke workflow on the physical iOS
26.6.1 device prepared the owner-selected Apple Settings bundle, verified
the owner-review gate, dispatched one authorized launch without terminating
any process, and independently verified the configured bundle was running.
The separate temporary no-root USB tunnel closed successfully. The
receipt explicitly leaves native UI and foreground verification false.
No app installation, removal, data access, screenshot or arbitrary input
occurred. No production configuration changed. Existing release holds
and Android hardware qualification remain open.

## Android USB onboarding qualification

Installed official Android SDK platform-tools 37.0.1 on the iMac;
the ADB 1.0.41 executable reported version 37.0.1-15733141. No ADB
process was running following host installation verification. Added
owner-local USB discovery, exact transport authorization status, and
private profile generation with installed activity resolution. A
separate five-case Android onboarding source campaign passed all five
tests: network/emulator exclusion, unauthorized device refusal, private
exact transport status, private profile creation and configured-profile
worker routing. No physical Android device was connected and no live
Android control, signed APK or release qualification is claimed.

## Native companion source projects

Added dependency-light Android Java and iOS SwiftUI native companion
source, platform manifest/project definitions, branded app icons and
portable connection-contract tests. Both target the existing independent
read-only gateway status API. They do not implement unrestricted phone
control, use full-control credentials or change any installed phone app.
Android disables app backup and cleartext transport; iOS retains default
ATS and certificate verification. Both reject redirects and bound
responses; tokens are transient and not written to persistent settings.

Installed official Android command-line tools (SDK manager 22.0); the
host's existing OpenJDK 25.0.5.0.3 runs successfully. Android SDK Platform
36 and Build Tools 36.0.0 were requested without accepting licenses.
The SDK manager stopped at its required owner license acceptance prompt.
No license acceptance, APK signing or device installation occurred.

A new fixed native companion connection-contract campaign ran 35 checks
across the Java JVM and Swift macOS host: 15 Java and 20 Swift checks,
all passed. Both portable contracts compiled; SwiftUI syntax parsing,
Android manifest XML parsing and Android build-script syntax passed.
The full native UI targets have not been compiled against their device
SDKs or installed. iPhoneOS SDK remains absent and code-signing identity
count is zero. The iPhone native application-launch capability from the
previous campaign remains verified; full touchscreen qualification and
signed companion distribution remain open.

The existing release gates and production hold remain in effect.
No personal apps or production gateway settings were changed.


## Owner-directed no-Xcode development continuation

The owner explicitly prohibited Xcode and Safari, and ChatGPT Work was
not used. Full Xcode remains absent. The standalone Swift compiler in
the existing Apple Command Line Tools was detected without invoking
the Xcode application or xcodebuild. The legitimate iPhoneOS SDK remains
unsupplied, and no Apple development signing identity was previously
available. Native Android SDK Platform 36 and Build Tools 36.0.0 remain
uninstalled pending owner acceptance of the SDK license. No agreement
was accepted on the owner's behalf.

Five focused native interaction preflight source tests passed. In the
isolated RDC Engine, the physical iOS 26.6.1 iPhone returned verified USB
trust, Developer Mode, mounted signed image, 82 remote services,
a unique built-in primary display at 1320 x 2868 pixels and four HID
surfaces. Touch, button, accessibility and screen-capture services were
advertised. The device did not return a verifiable lock-state response.
No screenshots, screen contents, HID input, app mutations or personal
data were accessed. Input and capture permission are explicitly false.

Six standalone packaging source tests passed prior to relocating the
test module into the repository's capped runner catalog. The new helper
admits only an explicit iPhoneOS device SDK outside the Xcode app path,
direct Swift compiler commands, and exact development provisioning for
the RDC app, device and keychain identity. It rejects expired, mismatched
or wildcard profiles and preserves existing output. Standalone compiler
preflight succeeded while the missing iPhoneOS SDK was honestly reported.
No real iOS compilation, package signing, application installation,
Android device qualification or production deployment occurred.


## Owner-approved Xcode and automation toolchain setup

The owner superseded the Xcode prohibition for compilation and signing.
Apple's official stable Xcode 27.2 archive was downloaded using authenticated
Google Chrome, expanded in the logged-in user Terminal, and independently
verified against the Apple signature requirement and exact bundle ID.
Xcode 27.2 build 27B52 is installed in Applications. First-launch status
remains incomplete and the SDK query explicitly reports that Apple's license
has not been accepted. No agreement was accepted by the assistant. The
global selected developer directory was not changed.

Appium 4.0.1 and pinned XCUITest 13.6.1 / UiAutomator2 10.1.0 drivers are
installed in a private development directory. One isolated loopback health
check succeeded and the temporary server was stopped; no device session
was created. Added an optional Xcode build script, syntax-checked only,
with unsigned and owner-selected signed modes. Android SDK Platform 36
and Build Tools remain pending Google's license acceptance. No IPA or APK
build or release deployment is claimed.

## Native device compilation after owner license approval

Both platform license/setup checks passed after owner confirmation.
The Android SDK 36 and build-tools 36.0.0 produced an aligned APK with
bundle org.tocministries.rdc.mobile, minimum API 26 and target API 36.
A dedicated local development-only key was created and retained privately
outside the repository; the development APK passed apksigner verification
(v2 and v3), one signer, and zipalign verification. No production signing
key or Android device installation was used.

Xcode 27.2 build 27B52 completed the native iPhoneOS Debug build with
CODE_SIGNING_ALLOWED=NO and CODE_SIGNING_REQUIRED=NO. The arm64 Mach-O
was independently inspected: platform iOS, minimum OS 17.0, SDK 27.2.
The exact owner-selected physical iPhone was also confirmed paired in
Xcode CoreDevice. No local Apple signing identity or provisioning profile
was present, so no iPhone installation or signed IPA is claimed.

Private candidate copies and a build receipt are retained on the iMac.
These binaries are companion status clients; they do not independently
provide unrestricted phone control. WebDriverAgent signing, native
touchscreen qualification, physical Android testing and all production
release gates remain open. No production deployment occurred.
