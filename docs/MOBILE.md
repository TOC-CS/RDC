# Phones and tablets

For the independent installable iPhone/Android companion, read-only status credential, and owner-side profile generator, see [Mobile installation and onboarding](MOBILE-INSTALL.md). The development candidate still requires physical-device qualification.

RDC can operate an owner-authorized Android device through ADB and can create dedicated native Appium sessions for Android, iPhone, and iPad. Mobile sessions have their own tools and `mobile-<uuid>` IDs. They remain separate from dedicated browser sessions.

This expansion has synthetic protocol and privacy tests. **Real Android, iPhone, iPad, emulator, and simulator qualification is still pending.** A configured profile or successful HTTP fixture does not establish hardware compatibility. The previous desktop/iMac verification applies to its tested revision and workflows.

## Available routes

| Route | Implemented behavior | Preparation |
| --- | --- | --- |
| Android ADB | Status, tap, simple ASCII input, key events, swipe, long press, explicit activity launch, privacy-checked screenshot | Owner-selected ADB serial and an already authorized device |
| Android Appium | Native observe, tap, nonsecure fill, swipe, screenshot, session lifecycle | Owner profile using UiAutomator2 and an exact device/emulator UDID |
| iPhone/iPad Appium | The same native session tools | Owner profile using XCUITest, exact device/simulator UDID, and Apple's required setup |
| Phone/tablet web browser | View the RDC owner dashboard or a supported host's preview | Access to the selected worker; viewing does not authorize control of that phone's OS |

Native actions use the selected device's screen and can interrupt someone using it. A separate emulator, simulator, or dedicated physical device provides a separate place to work. A native session does not create a second private screen on a physical phone. Host desktop input stays governed by its existing desktop setting.

## Owner setup

Configure Appium outside RDC, then add profiles to `config.json` in the worker's selected state directory. Restart that worker to load changes. RDC does not install drivers, pair devices, accept trust prompts, approve OS permissions, or enable Appium's insecure features.

For Android, the UiAutomator2 driver requires the Android SDK tools, a compatible JDK, and either a prepared emulator or an authorized device with debugging enabled. Choose matching Appium and driver versions from the [UiAutomator2 requirements](https://github.com/appium/appium-uiautomator2-driver#requirements). The driver provides `appium driver doctor uiautomator2` for its environment checks. The owner can identify the intended Android serial using the documented [ADB device selection workflow](https://developer.android.com/tools/adb#directingcommands).

For iPhone and iPad, use XCUITest with compatible Appium, Xcode, macOS, and device OS versions. The normal host is a Mac; the driver documents additional limits for other hosts. Consult its [compatibility requirements](https://appium.github.io/appium-xcuitest-driver/latest/getting-started/system-requirements/) before choosing versions. Real devices require owner-completed trust, the applicable Developer Mode/UI Automation settings, and a signed/provisioned WebDriverAgent. Follow the driver's [device preparation](https://appium.github.io/appium-xcuitest-driver/latest/getting-started/device-setup/) and [provisioning guide](https://appium.github.io/appium-xcuitest-driver/latest/getting-started/provisioning-profile/). RDC leaves those consent and signing steps with the owner. iPadOS profiles use `platformName: "iOS"`.

The agent chooses an alias from the configured profiles. It cannot submit an endpoint, UDID, capabilities object, locator, script, or shell command to a mobile tool.

### Profile example

Add `mobile_profiles` alongside the existing settings. Replace the example identifiers with devices and installed applications the owner intends to operate. Preserve the existing working roots, review mode, and desktop setting.

```json
{
  "mobile_profiles": {
    "android_work": {
      "platformName": "Android",
      "automationName": "UiAutomator2",
      "endpoint": "http://127.0.0.1:4723",
      "capabilities": {
        "appium:udid": "OWNER_ANDROID_SERIAL",
        "appium:appPackage": "com.example.app",
        "appium:appActivity": ".MainActivity",
        "appium:noReset": true
      }
    },
    "ipad_work": {
      "platformName": "iOS",
      "automationName": "XCUITest",
      "endpoint": "http://127.0.0.1:4723",
      "capabilities": {
        "appium:udid": "OWNER_IPAD_OR_SIMULATOR_UDID",
        "appium:bundleId": "com.example.app",
        "appium:noReset": true
      }
    }
  }
}
```

Profile rules:

- An alias has 1 to 64 ASCII letters, digits, underscores, or hyphens, beginning with a letter or digit. There may be at most 32 profiles.
- Each profile has exactly `platformName`, `automationName`, `endpoint`, and `capabilities`. The supported pairs are `Android`/`UiAutomator2` and `iOS`/`XCUITest`.
- An endpoint uses HTTPS, or HTTP on a loopback address. User information, query parameters, and fragments are rejected. An explicit base path such as `/wd/hub` is supported. Ambient proxies and HTTP redirects are disabled.
- `appium:udid` is required even when only one device is attached. RDC never relies on Appium selecting the first device. Endpoints, UDIDs, capabilities, and driver session IDs are omitted from public status.
- Use flat, vendor-prefixed capabilities. Nested `appium:options`, browser selection, and duplicate platform/automation settings are rejected. Capabilities are limited to 64 entries and 32 KiB of JSON. They stay in owner configuration; keep that file private.
- RDC supplies `appium:noReset: true` when omitted and rejects `noReset: false` or `fullReset: true`. It also rejects automatic permission grants, automatic alert acceptance/dismissal, automatic webview switching, and prompt handling other than `ignore`.
- The default `appium:newCommandTimeout` is 120 seconds. The owner may choose an integer from 30 to 600 seconds. This bounds idle driver lifetime; it does not prove cleanup after a lost creation response.

App installation or other setup implied by additional owner capabilities remains Appium behavior. The examples target installed apps. Only configure profiles and Appium services the owner trusts.

## Native workflow

1. Call `rdc_mobile_list` to see sanitized profiles and active sessions.
2. Call `rdc_mobile_start` with `{"profile":"android_work"}` or another configured alias. Retain the returned `session_id`.
3. Call `rdc_mobile_observe` with that ID. Retain the new `observation_id` and the relevant control's `handle`.
4. Use `rdc_mobile_tap` or `rdc_mobile_fill` with the exact session, observation, and handle. Fill additionally takes `text`, up to 4,000 characters. Only nonsecure editable controls support fill.
5. Use `rdc_mobile_swipe` with `start_x`, `start_y`, `end_x`, `end_y`, the current session/observation IDs, and optional `duration_ms` from 50 to 10,000. The default is 400 ms. Coordinates are native logical coordinates within the observed width and height.
6. Observe again after an input. Verify the resulting screen or application state independently. A completed driver command alone does not establish the intended app outcome.
7. Use `rdc_mobile_screenshot` or the selected preview session when an image is appropriate. Use `rdc_mobile_close` to end the exact driver session. Hiding a preview does not close it.

At most eight mobile sessions may run. A profile cannot start a second session while its first remains active or unresolved. Aliases for the same platform, UDID, and configured server are also prevented from starting competing sessions. Owners must avoid configuring different servers to control the same physical device concurrently.

Mobile start and input tools use RDC's existing owner review and pause controls. Mobile close is an explicit cleanup operation. The embedded preview remains a viewer; owner administration supplies authorized native controls. Mobile controls never offer the browser credential chooser.

## Observation, privacy, and image coordinates

The adapter reads native XML internally using the driver's [native context](https://appium.io/docs/en/latest/guides/context/) and [WebDriver endpoints](https://appium.io/docs/en/latest/reference/api/webdriver/). It requires `NATIVE_APP` and exposes no arbitrary execute endpoint. Internal positional selectors are generated from the observed tree, rather than accepted from the agent.

Raw XML and native `value` attributes never appear in observations. Editable controls have generic labels and `[redacted]` values. A native secure field also has `secure: true` and `can_fill: false`; the owner enters its secret directly on the device. Native saved-password providers are outside this expansion. Driver exceptions and ADB command output are replaced with fixed messages.

Parsing is limited to 1 MiB of XML, 5,000 nodes, and 64 levels. Malformed, unrecognized, oversized, or entity/DTD-bearing source fails closed. Up to 150 visible controls and 24,000 text characters are exported. Check `controls_truncated`, `text_truncated`, and each control's `name_truncated`. A complete hierarchy scan still checks for secure fields beyond the exported control limit.

Every native input requires a current observation. RDC compares the current hierarchy with the observed one before sending input and invalidates that observation before mutation. Dynamic screens may require frequent re-observation. The app or device owner can still change state between native protocol calls; this check is not an atomic OS transaction.

Screenshots require a verified hierarchy before and after capture. They are refused when a secure field is found, hierarchy verification fails, or the screen changes during capture. Once a secure field is observed, that native session keeps refusing images, including after a Show Password toggle. There is no native image-mask fallback. These protections use the native hierarchy supplied by the configured driver; they do not classify arbitrary text painted into images or secret copies made by an app.

**Never bypass a screenshot refusal with raw ADB, another screenshot client, the shared desktop, or a newly opened session.** Continue with safe redacted observations or owner assistance. A privacy refusal does not mean the RDC worker disconnected.

Appium screenshots may have more physical pixels than the native coordinate system. `width`/`height` and `input_width`/`input_height` describe native logical coordinates. `source_width`/`source_height` describe the PNG. Multiply a pixel position in the original PNG by `input_scale_x`/`input_scale_y` before interpreting it as an input coordinate. The ordinary native workflow prefers observed handles.

## Android ADB additions

ADB remains bound to `adb_serial` in owner configuration. Every command uses an argument vector and detached stdin. The tools never choose another serial, pair a device, grant a permission, install an app, or execute agent-supplied shell text.

| Tool | Arguments |
| --- | --- |
| `rdc_android_swipe` | `start_x`, `start_y`, `end_x`, `end_y`, optional `duration_ms` (default 400) |
| `rdc_android_long_press` | `x`, `y`, optional `duration_ms` (default 800; minimum 300) |
| `rdc_android_launch_app` | `package`, `activity`, such as `com.example.app` and `.MainActivity` |

Coordinates are integers from 0 to 10,000; the owner/agent must still use the actual device bounds. Swipe and long press use Android's documented `input swipe` implementation, with identical start/end points for a hold. Activity launch uses `am start -n package/activity`, with no force-stop or data-reset option. The package and activity syntax rejects shell metacharacters. See the [Android input implementation](https://android.googlesource.com/platform/frameworks/base/+/master/services/core/java/com/android/server/input/InputShellCommand.java) and [ADB activity manager reference](https://developer.android.com/tools/adb#am).

ADB screenshots require two readable native hierarchy snapshots around the image capture. RDC uses a forced PTY and `uiautomator dump --verbose /dev/tty` to avoid leaving private XML files on device storage. This combines the documented [ADB shell PTY option](https://android.googlesource.com/platform/packages/modules/adb/+/refs/heads/main/docs/user/adb.1.md) with the native dump command's output-file argument in [Android's implementation](https://android.googlesource.com/platform/prebuilts/fullsdk/sources/android-29/+/refs/heads/main/com/android/commands/uiautomator/DumpCommand.java). A device that cannot provide this hierarchy receives a fixed screenshot refusal, without raw capture fallback. The ADB privacy latch lasts for that worker's lifetime after a secure field is seen.

RDC disables ADB hierarchy capture while native Appium sessions are active, avoiding a competing UiAutomation connection; use the active mobile session's screenshot operation. ADB command dispatch and Appium native automation still require separate hardware qualification.

## Failures and recovery

| Result | Required next step |
| --- | --- |
| `stale_observation` | Observe again and reassess the intended action. |
| `secure_input_required` | Let the owner enter the value on the device. |
| `screenshot_redaction_required` | Continue without an image; preserve the privacy boundary. |
| `screenshot_failed` | Treat the image as unavailable; inspect the returned fixed message and current worker/session status. |
| `mobile_session_gone` | Explicitly close the retained RDC record, then start the profile if still needed. A confirmed invalid-session response permits record cleanup. |
| `mobile_cleanup_required` / `setup_status: cleanup_required` | Close the exact listed session. Failed cleanup keeps it listed and blocks replacement. |
| `mobile_creation_unknown` / `setup_status: creation_unknown` | The owner inspects the configured Appium server, resolves any unconfirmed session, and then restarts RDC. RDC lacks a driver ID and cannot safely delete an unidentified session. |
| Driver/network failure during input | Inspect before considering another action. RDC never replays the mutation. |

Fill consists of clear followed by send-keys. If either response fails, the field may be partly changed. Swipe failure triggers one release-actions cleanup, without replaying the gesture. If that cleanup also fails, the session is retained for explicit close. No error includes the driver's raw response, XML, capability data, or supplied text.

## Verification boundary

`tests/test_mobile.py` uses a local synthetic Appium HTTP server with literal Android/iOS hierarchy fixtures and synthetic ADB subprocess responses. It covers owner-only configuration, exact device selection, setup/cleanup failures, expired sessions, bounded native observations, secure-field redaction, screenshot refusal and scaling, stale handles, touch payloads, no replay, fixed errors, ADB argument construction, adapter routing, and shutdown without a browser thread.

Run the focused gate with the project's supported environment:

```sh
python -m unittest discover -s tests -p test_mobile.py -v
```

Hardware acceptance must still verify the chosen Appium/driver/OS versions, owner-completed pairing and consent, native field classifications, coordinate scaling, gesture behavior, real secure-field refusal, lifecycle cleanup, and the intended AI host preview. Keep the working installation until the owner's required mobile route passes those checks.
