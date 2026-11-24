# RDC Mobile installation and native device onboarding

Status: development candidate. The installable companion has synthetic HTTP
verification, not physical iPhone or Android acceptance. It does not operate
the phone OS. Native control is provided by the existing host-side RDC
Appium/ADB adapters after owner consent. No signed IPA or APK is included.

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

A signed native iOS companion requires full Xcode, a signing team and device
provisioning for development or distribution through TestFlight/App Store.
A signed native Android package requires an SDK/JDK, Gradle-compatible build
and protected signing key. These native packages are not generated by the
web manifest and must not be advertised until built and tested. The supported
host automation path does not depend on either native companion package.

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
