# RDC Mobile 0.1.1 development preview

This is an installable Android development companion and source/build kit
for iPhone and iPad. The preview adds a bounded device-local command
interpreter to the existing read-only gateway status companion. It is
separate from the RDC worker and its native automation driver.

## 1. Android installation

Download RDC-Mobile-Android-0.1.1-development.apk and manifest.json.
Compare the SHA-256 with the manifest. On a trusted computer with Android
SDK Build Tools:

    shasum -a 256 RDC-Mobile-Android-0.1.1-development.apk
    apksigner verify --verbose RDC-Mobile-Android-0.1.1-development.apk

The signed development package targets API 36 and supports API 26 or later.
Install the verified APK from a trusted file manager, following the OS
installation prompt, or use authorized Android debugging:

    adb devices -l
    adb -s YOUR_AUTHORIZED_SERIAL install RDC-Mobile-Android-0.1.1-development.apk

For a same-signer upgrade use adb install -r only after choosing the exact
device. Never uninstall an existing app or wipe its data to force a
signature mismatch. Physical installation of this preview is not yet
qualified. Use the Local terminal screen for help, pwd, ls, mkdir, write,
cat, sha256 and echo.

## 2. iPhone and iPad installation

Download the native source ZIP. Use your own compatible Apple Xcode and
XcodeGen, development certificate and exact-device provisioning. The
iOS project targets iOS/iPadOS 17 or later. Complete normal Apple
authentication, Trust and Developer Mode setup on your own device.

From the extracted source root:

    cd native-mobile
    export RDC_APPLE_TEAM=YOUR_DEVELOPMENT_TEAM
    export RDC_IOS_DEVICE=YOUR_AUTHORIZED_DEVICE_ID
    bash ios/build-xcode.sh signed /YOUR/PRIVATE/BUILD

Provisioning changes are disabled by default. The resulting signed
RDCMobile.app is device/profile-bound. Install using the normal Apple
developer tools and its exact build path:

    xcrun devicectl device install app --device "$RDC_IOS_DEVICE" /YOUR/PRIVATE/BUILD/DerivedData-signed/Build/Products/Debug-iphoneos/RDCMobile.app
    xcrun devicectl device process launch --device "$RDC_IOS_DEVICE" org.tocministries.rdc.mobile

Verify the app opens on the selected device. A source ZIP or unsigned
build is not an installable IPA. No personal signing profile, IPA,
private key or store listing is distributed here.

## 3. Connect RDC and your AI client

Install the worker from the matching GitHub development branch using
Python 3.11 or later. Create a private virtual environment; install with
pip install '.[mobile]'. Follow the repository README to initialize an
authorized worker and connect a compatible MCP client. On the worker,
configure an exact device profile and a compatible loopback Appium
UiAutomator2 or XCUITest driver. Complete normal device trust and
driver signing before sending native input. See docs/MOBILE-INSTALL.md
and docs/MOBILE-COMMAND-ENGINE.md in the repository. For the browser
companion, visit /mobile/ on your own certificate-verified RDC gateway.

Use the current advertised tool schemas. The new command interface is
a development preview; an older worker/plugin may not yet expose it.
The optional complete-source optimization requires a separately
compatible driver and remains disabled by default. Remote SSH and
physical responsiveness qualification remain pending. All app data,
credentials and owner configuration stay private.
