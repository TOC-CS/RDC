# RDC Mobile installation and native device onboarding

Status: development candidate, updated November 23, 2026. A signed native
iPhone companion was installed and independently verified running; a signed
Android development APK is included in the source tree. The iPhone IPA and
provisioned app are private, device-specific owner artifacts. Physical Android
installation remains unqualified. See [native installers and build steps](../native-mobile/README.md)
and [the current evidence](releases/RDC-MOBILE-INSTALL-20261123.md).

The companion reads gateway status and does not operate the phone OS.
Native control is a separate host-side RDC Appium/ADB workflow after owner
consent. The plugin package is guidance and connection configuration; it
does not install the companion, worker or mobile driver.

## Install the independent companion

The standalone gateway packages a browser-installable progressive web app
at `/mobile/`. It does not require ChatGPT Sites, Cloudflare, or an app store.
Use a gateway you control, on your own Mac or an independently controlled VPS.
The gateway remains loopback-bound; for phone access, use an owner-approved,
certificate-verified HTTPS reverse proxy. The example Nginx configuration
includes the mobile routes. A trusted certificate is required even on LAN.
Do not weaken TLS, expose the raw gateway port, or share the full MCP token.

1. Deploy the reviewed candidate only after the existing RDC release gates and
   owner deployment approval are satisfied.
2. Visit `https://YOUR-VERIFIED-RDC-HOST/mobile/` on your phone. This is a
   placeholder, not a published service or a maintainer-operated relay.
3. iPhone/iPad: in Safari, select Share, Add to Home Screen, then Add.
4. Android: in Chrome, select Install app or Add to Home screen.
5. Open RDC from the home screen. The offline shell retains installation
   instructions, not live status or credentials.

### Optional read-only status

On the authorized gateway, from the installed candidate environment:

```sh
python -m rdc.mobile_install enable-status --state-dir /YOUR/PRIVATE/GATEWAY/STATE
```

The command creates `mobile-status-token` with owner-only permissions, refuses
to overwrite it, and never prints its value. Transfer only this read-only
credential privately. Enter it in the companion to check connection status.
It is cleared after submission and never persisted by the app. The API
returns only connectivity and active operation count; the token cannot call
MCP tools or authenticate a device. Remove the private token file to revoke
access; generate a replacement with the same command if needed. The
companion does not accept device keys or full-control gateway tokens.

The only cached resources are the public installation shell and icons. There
is no third-party JavaScript, analytics, cross-origin fetch, or service worker
interception of the status POST. Installation alone grants no device access.

## Connect an actual iPhone or iPad as an RDC target

Use an authorized Mac with full Xcode (Command Line Tools alone are insufficient),
Node and an Appium XCUITest driver version compatible with the installed Xcode
and iOS version. Follow the maintained Appium device setup and provisioning
guides linked in [MOBILE.md](MOBILE.md), including owner consent and signed
WebDriverAgent. Start Appium bound to loopback without insecure features.

Connect via USB initially; approve Trust, Developer Mode and UI Automation
when required. If your supported Xcode/driver/device combination allows wireless
debugging, pair explicitly in Xcode first; retain USB as a fallback. Select the
exact device identifier shown by Xcode Devices and Simulators. Do not guess it
or use automatic first-device selection.

Generate a private profile fragment on the Mac:

```sh
python -m rdc.mobile_install profile --platform ios --alias iphone \
  --udid YOUR_EXACT_DEVICE_UDID --app com.apple.Preferences
```

The command validates a fixed profile with no-reset behavior and does not
change the live worker. Merge the `iphone` entry into the existing
`mobile_profiles` object in its private `config.json`, preserving other
profiles and existing approval settings. Choose the bundle ID of the app
you actually intend to automate. Reload the worker only with the owner's
consent and when no active work would be interrupted.

## Connect an actual Android phone as an RDC target

Install compatible Android SDK platform tools, JDK and Appium UiAutomator2
on the owner-controlled host. Follow the official Android ADB device pairing
documentation and UiAutomator2 requirements in [MOBILE.md](MOBILE.md).
Use USB debugging or the Android wireless debugging pairing flow; approve
the prompt on the selected phone. Confirm the intended serial in `adb devices -l`.
Start Appium on loopback without insecure features.

```sh
python -m rdc.mobile_install profile --platform android --alias android \
  --udid YOUR_EXACT_ADB_SERIAL --app com.android.settings --activity .Settings
```

Use the exact installed package and activity; the sample varies by device.
Merge the generated alias into the worker's existing private configuration.
For the direct Android ADB adapter, set the owner-selected `adb_serial` only
after confirming the authorized device. Never expose ADB or Appium directly
to the Internet.

## Verify phone control

From an authorized AI client connected to the worker, list mobile profiles,
start the exact alias, observe, then perform an owner-approved reversible
action using a fresh observation. Verify the actual resulting screen and
close the session. Observe again after input; never replay an uncertain
action or bypass secure-field screenshot refusal. Android and iOS sandboxing
still applies. The companion cannot read arbitrary private app data or grant
unrestricted background device control.

## Native distribution and release requirements

The native source and exact build/install paths are documented in
[native-mobile/README.md](../native-mobile/README.md). The verified iPhone
route uses owner-approved Xcode, an Apple development identity and exact-device
provisioning. A separately supplied legitimate SDK and standalone compiler
remain an optional packaging route. Android uses JDK/SDK tools directly,
without Gradle or Android Studio, and an owner-held signing key.

The included Android APK is a development build; its signing key stays
private. The iPhone IPA embeds a short-lived owner-specific development
profile and is not published in GitHub or the plugin. Build/sign for each
intended device/team; do not reuse the owner's private profile. The web
manifest generates neither native package. Host automation remains separate.
No app-store distribution or production release is qualified.

Before any release: verify real Safari home-screen installation, real Chrome
installation, HTTPS origin, offline shell, token revocation, native pairing,
actual gestures, secure-field refusal and lifecycle cleanup on selected
physical devices. Preserve the existing six speed/release gates and rollback
controls. Total test executions across the mobile development campaign may
never exceed the owner-mandated 100 ceiling.

### Existing trusted USB connection on a Mac

A local macOS diagnostic can enumerate a unique USB-connected Apple mobile
device and check whether its existing lockdown pairing is accepted, without
Xcode or third-party packages:

```sh
python -m rdc.mobile_install ios-usb-check
python -m rdc.mobile_install ios-usb-profile --alias iphone --output /YOUR/PRIVATE/iphone-profile.json
```

If multiple USB devices are attached, use the owner-selected `--udid`.
The diagnostic excludes identifiers and pairing records from its output;
the generated fragment contains the actual selected UDID and is owner-only.
It refuses to overwrite an existing file or select an untrusted device.
Accepted pairing is not a verified developer-service connection, native
automation session, or permission to operate private applications. Full
Xcode and signed WebDriverAgent remain necessary for the native route.

On supported Apple systems, the built-in iPhone Mirroring app is an alternate
owner-mediated UI route while native developer tooling is unavailable.
It uses Apple's own wireless requirements and consent, independent of this
USB diagnostic. Never use mirroring to bypass a native screenshot privacy
refusal. It does not qualify the RDC native driver.

### Read-only iOS status without Xcode

Install the optional host communication utility on the Mac:

```sh
brew install libimobiledevice
```

After an owner-selected iOS profile is loaded, the candidate RDC worker exposes
`rdc_mobile_ios_status` with `{"profile":"iphone"}`. It checks existing USB
trust and reads only fixed battery, storage and Developer Mode fields using
the host-installed utility. It will not accept raw device identifiers, shell
commands, arbitrary domains or file paths from the AI client. No personal
files or app data are returned, and no permissions or phone settings are
changed. Missing fields are omitted and explicitly marked partial or
unavailable. This route does not require Xcode, but also cannot tap, type,
install arbitrary apps or replace native XCUITest control.

On the physical device verified November 23, 2026, iOS 26.6.1, this route
returned all six metrics from an isolated RDC worker without changes to the
production worker. Developer Mode was disabled. For XCUITest, the owner must
complete Apple's Developer Mode and UI Automation requirements and valid
WebDriverAgent signing; see the official Appium device preparation guide
linked in MOBILE.md. Apple's separate iPhone Mirroring feature requires
the nearby iPhone to be locked and the owner to approve its setup.

### Preferred lightweight iOS backend (development candidate)

Install the official PyMobileDevice3 distribution in the default isolated uv
tool directory. The verified release was 11.63.1:

```sh
uv tool install --managed-python --python 3.13 pymobiledevice3==11.63.1
```

The RDC status tool defaults to the PyMobileDevice3 backend, querying six
fixed metrics in one existing, exact-device USB lockdown session with
automatic pairing disabled. If the primary backend is unavailable or
incomplete, the existing libimobiledevice route is retained as a fallback.

For independent device identity verification, Go-iOS 1.3.2 was installed
from the upstream npm distribution. Install its appropriate upstream
platform binary privately at ~/.local/share/rdc/tools/go-ios/ios on macOS.
Go-iOS is explicitly selectable and returns only whether the selected
device identity matched the USB diagnostic. It does not return full
lockdown data. No Go-iOS tunnel daemon or REST server is started.

The owner-configured profile alias is the only accepted device target.
The optional backend enum is auto, pymobiledevice3, libimobiledevice, or
go-ios. The last option verifies identity only and is not a battery or
storage backend. All outputs omit device identifiers and personal data.

Developer services, screen interaction, signed app installation and
wireless hardware acceptance remain separate gates. Existing phone
passcode and trust settings are preserved. Developer Mode must be
enabled by the owner through Apple's supported setup.

### Developer services and Apple Mirroring (development candidate)

After Developer Mode is enabled on the phone, the optional
`rdc_mobile_ios_developer_preflight` tool checks the exact owner-configured
USB profile and opens and closes a temporary, no-root RemoteXPC tunnel.
It reports only developer readiness, image mount state, and allowlisted
service availability, not connection addresses, raw device data, or
device identifiers. A successful tunnel does not by itself qualify UI
automation.

The physical iOS 26.6.1 device required the Apple-personalized Cryptex DDI
route rather than the initial PersonalizedDMG mount. The owner-authorized
first installation completed successfully using Apple's signing service.
An independent subsequent preflight confirmed the mount and application
and device-info service availability. No replacement or uninstall was
performed. Developer-image installation is an explicit setup operation;
the read-only preflight never installs or repairs an image.

For Apple iPhone Mirroring, a local owner can opt in by setting
`ios_mirroring_enabled: true` and an existing non-disabled desktop grant.
`rdc_mobile_mirror_observe` reads the exact Apple app's window metadata
and available Home Screen, App Switcher, and Spotlight menu commands.
`rdc_mobile_mirror_navigate` consumes a fresh observation and always
requires a local owner decision, even in trusted mode. It does not return
phone screen content, type text, accept arbitrary coordinates, or replay
an uncertain command. The owner must independently verify the Apple-selected
phone. Native Appium sessions and mirroring navigation cannot run concurrently
through this adapter. The connected window was verified; physical menu action
outcomes remain unqualified.

iPhone Mirroring also requires its own Apple account/Continuity setup and
an available wireless connection. On this host, Internet Sharing was
disabled by the owner to resolve the connection conflict. The separate
USB developer transport remained operational.

### Direct native iOS application launch without Xcode or Appium

A local owner can enable the narrowly scoped CoreDevice route with
`ios_coredevice_launch_enabled: true` in the RDC worker settings.
The existing private mobile profile must specify an exact USB device and
installed application bundle. The option defaults to false.

Call `rdc_mobile_ios_app_prepare` with the configured profile alias.
The worker verifies USB trust, Developer Mode, mounted developer image,
the exact installed application and advertised CoreDevice launch support.
On success it returns a single-use observation valid for 120 seconds.

Call `rdc_mobile_ios_app_launch` with that alias and observation. The
worker requires owner review even in trusted mode. It rechecks device
identity and installed app, launches the configured app without killing
an existing process, and independently queries its bundle-specific
process identity through Instruments. No raw process identifier or
driver response is returned. A process-running result does not prove
foreground display, an unlocked screen, touch input or native UI
automation. A failed or uncertain dispatch is never automatically
replayed. This route cannot uninstall, reinstall, signal processes,
access app content, take screenshots or provide arbitrary launch
arguments. It does not open a network listener or require Xcode.

The route was verified on the physical iOS 26.6.1 device using only
the owner-configured Apple Settings application and a temporary isolated
RDC Engine. The owner must enable the feature in their own production
settings after release qualification. The existing Appium and Apple
Mirroring routes remain separate.

### Android USB onboarding without Android Studio

The host-side ADB path needs only official Android SDK platform-tools
for connection and device diagnostics. On macOS, platform-tools 37.0.1
was installed from the Homebrew Android platform-tools cask. Full
Android Studio, JDK and Appium are unnecessary for this onboarding path;
the separate UiAutomator2 route still requires its compatible toolchain.

On an owner-controlled host, connect the selected Android phone by USB,
enable Developer Options and USB debugging on that device, and approve
the host's debugging prompt on the phone. Then run:

```sh
python -m rdc.mobile_install android-usb-check
python -m rdc.mobile_install android-usb-profile --alias android \
  --app com.android.settings --activity .Settings \
  --output /YOUR/PRIVATE/DIRECTORY/android-profile.json
```

The owner may provide `--serial` to choose the exact USB device when
more than one is attached. The tools refuse ambiguous devices, emulators,
network transports and unauthorized debugging sessions. The ADB
transport must be positively identified as USB by the installed ADB
binary. A private fragment is created only after the exact selected
installed activity resolves; it does not modify a live configuration.
On POSIX the fragment is created with mode 0600 and cannot overwrite an
existing file. Keep the private serial and fragment off public logs.

A configured Android profile can use `rdc_mobile_android_usb_status`
for bounded status without revealing identifiers or launching apps.
The local ADB client uses the loopback ADB server only; it may start
that standard local server if needed. No remote ADB connections,
automatic pairing, TCP debugging, app installation or input is performed
by these onboarding commands. No physical Android device was connected
during source qualification; hardware acceptance remains open.


### Optional standalone iOS packaging and native interaction readiness

The owner approved Xcode for development packaging and native-driver testing.
The optional `native-mobile/ios/standalone.py` route remains available; see
[native-mobile/README.md](../native-mobile/README.md). It requires an explicitly
supplied legitimate iPhoneOS SDK compatible with the standalone Swift compiler,
an owner-held Apple development identity and an exact-device profile for a
signed IPA. It never downloads an SDK, uses Xcode, creates a certificate,
changes device trust or installs an application. Direct USB status/launch
routes remain independent from the Xcode-based Appium qualification.

The read-only rdc_mobile_ios_interaction_preflight tool inspects the exact
owner-selected USB device, positively identifies one built-in primary
display, reports bounded native dimensions/orientation and checks the
advertised touch, button, accessibility and screen-capture services. It
may query registered HID surfaces without sending any input. Service
presence or surface enumeration never implies successful touchscreen
automation. Lock-state uncertainty remains explicit. Neither this tool
nor its helper returns screen content or permits touch, keyboard input
or screenshot capture; complete privacy and foreground verification must
be established before qualifying those operations.


### Updated owner-approved packaging policy

The owner subsequently authorized Xcode as an optional development,
packaging and test-driver tool. The RDC direct USB runtime remains
independent. Safari and ChatGPT Work are excluded for this session.
Use native-mobile/ios/build-xcode.sh for isolated unsigned/signed build
products; the existing standalone helper remains available. Review Apple
and Google SDK agreements personally before enabling the respective builds.
The pinned Appium 4.0.1 server and XCUITest 13.6.1 and UiAutomator2 10.1.0
drivers were installed in a private development directory. A temporary
loopback server responded successfully. Signed WDA was then installed and
the owner completed the XCTest authentication prompt directly. The physical
iPhone session verified observation, tap, nonsecure typing, secure-screen
capture refusal and explicit cleanup. WDA rejected coordinate swipe; usable
live preview, wireless/recovery/app-switching, Xcode-free WDA startup and
Android/iPad hardware qualification remain open. All temporary servers and
sessions were stopped. See the dated evidence for the combined 97/100 ledger.
