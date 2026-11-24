# Mobile installation for RDC development

This guide accompanies the November 23, 2026 mobile development candidate.
RDC remains MIT-licensed and local-first. Native companions can connect to an
owner-controlled HTTPS gateway without ChatGPT, Sites or Cloudflare. They
accept a read-only status token, keep it transient and expose no MCP control.

## Choose the package

| Package | Install route | Verified boundary |
| --- | --- | --- |
| Android development APK | `native-mobile/installers/RDC-Mobile-Android-development.apk` in GitHub; also packaged with this plugin reference when available | Signed v2/v3 and aligned, API 26 minimum/36 target; no physical Android install verified |
| iPhone development app/IPA | Owner-private install bundle, or build/sign native iOS source for the selected device | One iPhone install/launch verified; profile-bound, expires 2026-12-01 02:28:07 UTC |
| Native source | `native-mobile/` in the repository; plugin support archive `mobile-installers/RDC-native-mobile-source.zip` when available | Android Java/SDK and iOS SwiftUI source; Python wheel alone excludes these projects |
| Web companion | Your reviewed gateway at `/mobile/` | Read-only PWA; physical browser installation acceptance remains separate |

[Source and full build guide](https://github.com/TOC-CS/RDC/tree/feature/rdc-mobile-install-20261123/native-mobile)
and [Android installer inventory](https://github.com/TOC-CS/RDC/tree/feature/rdc-mobile-install-20261123/native-mobile/installers)
belong to a development branch, not a production/store release. Inspect the
SHA-256 manifest beside a package. Never install on an automatically chosen
device, replace another app, or expose Appium/ADB to the public Internet.

## Android

Use the included signed development APK or build with `android/build.sh`
after personally accepting the required SDK license. The build requires JDK,
SDK Platform 36 and Build Tools 36.0.0, produces an aligned unsigned APK and
does not sign/install. Sign with an owner-held key; keep the key private.
Gradle and Android Studio are not required by this project.

For an authorized installation, select the exact approved debugging serial
locally and run `adb -s "$RDC_ANDROID_SERIAL" install "$RDC_ANDROID_APK"`.
Both variables must point to the intended device and verified package.
Review any existing-app/signature conflict; do not uninstall or wipe its data
to force an upgrade. Hardware installation and launch must be checked
separately; package construction is not Android acceptance.

## iPhone and iPad

Use compatible owner-approved Xcode and XcodeGen for the verified build route.
The owner completes Apple agreements/account authentication. Set the exact
team and device locally as `RDC_APPLE_TEAM` and `RDC_IOS_DEVICE`; run
`ios/build-xcode.sh signed /YOUR/PRIVATE/BUILD` from `native-mobile/`.
Only explicit `RDC_ALLOW_PROVISIONING=1` enables Apple provisioning updates
for that selected device. The default leaves provisioning updates disabled.
The script creates a strictly verified signed `.app`, not an IPA or install.

With the signed bundle path in `RDC_IOS_APP`, install using
`xcrun devicectl device install app --device "$RDC_IOS_DEVICE" "$RDC_IOS_APP"`
under the selected Xcode developer directory. A development IPA is not an
App Store installer and will not install merely by tapping a download.
Keep its embedded owner profile private. The optional standalone helper
signs an unsigned app using an owner-supplied legitimate SDK, certificate,
exact-device profile and existing private key; it does not install.

After installation, the owner may need Settings > General > VPN & Device
Management > the exact Apple Development profile > Trust. Then launch the
exact `org.tocministries.rdc.mobile` bundle and verify its running process
independently. Do not label installation as launch success. A Personal Team
profile expires; re-sign with current valid provisioning when needed.
The existing private candidate expires November 30, 2026 at 8:28:07 PM US
Central. iPad installation and behavior have not been qualified.

## Native controls and password prompts

The companion does not install a control service. Host-side Appium requires
UiAutomator2 for Android or signed/provisioned WDA/XCUITest for iOS. Use an
owner-configured exact-device profile, loopback service and fresh observed
control handles. Check current catalog support before invoking tools.

Distinguish the prompt actually displayed. During this qualification,
an XCTest authentication sheet appeared inside the Mac iPhone Mirroring
window with a regular secure text field: it requested the Mac login password,
entered directly by the owner and submitted with Return. That observation
does not identify every future prompt. Read its title/message before giving
password guidance. A physical iPhone unlock prompt uses that device's own
authentication. Never request either password in chat or move/change the
screen while the owner is authenticating. Resume only after their handoff.

## November 23, 2026 mobile development evidence

The November 23 development candidate has a signed iPhone companion installed
and independently verified running. Physical Appium/XCUITest observation,
tap, nonsecure typing, secure-screen capture refusal and explicit session
cleanup were verified. A signed Android development APK was built and its
signature/alignment verified; no physical Android installation is qualified.
Swipe/scroll failed at WDA window-coordinate selection. Safe live preview,
wireless use, hardware recovery/no-replay, app switching, Xcode-free WDA
startup, iPad/Android acceptance and the expanded companion UI remain OPEN.
These results do not deploy the candidate worker or qualify a production release.

The native companion is a read-only gateway status client, not unrestricted
phone control. Follow this installation guide for the included
Android development APK, native source, iPhone signing/install requirements
and the owner-private iPhone artifact. This plugin update does not install
or activate candidate worker code. Check the actual connected catalog.

The source fixes cover visible SwiftUI Form descendants behind a nonaccessible
CollectionView and iOS WDA selectors omitting the AppiumAUT wrapper. They retain
hidden-window and secure-field protections. Native saved-password filling is
unsupported. The campaign is 97/100; no unrestricted tests or CI reruns.

## Publication boundary

GitHub carries source, instructions and the Android development APK. The
private ChatGPT plugin adds installation guidance and portable support files;
it preserves its existing App/MCP binding. The owner's signed iPhone bundle
is a separate private deliverable, not included in GitHub or plugin archives.
No private key, developer profile, token, account or raw device identifier
belongs in those public/shared materials. Updating source/plugin guidance
does not deploy a worker, gateway, VPS, or app-store release.
