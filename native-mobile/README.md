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

## iOS

Prerequisites: full Xcode, the iPhoneOS SDK, and XcodeGen. Run
xcodegen generate --spec ios/project.yml from this directory, then open
the generated project in Xcode. For a physical iPhone, the owner chooses
their Apple development team and provisioning profile; for simulation,
build using the iOS Simulator SDK. No signing identity or provisioning
profile is embedded. A native signed IPA is not available until those
steps are verified. Do not disable ATS or override certificate validation.

The independent gateway /mobile/ PWA remains the lower-friction installation
option on either platform. Physical device acceptance, full native UI control,
signed distribution and production release gates remain separate.
