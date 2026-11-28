# Platform and isolation matrix

RDC is an alpha. A route exists when code targets an adapter; an executed contract
or mocked protocol test does not certify a physical device, operating system, or
AI client. The repository's build log records executed commands and outcomes. Use
its evidence alongside this matrix before choosing a worker.

| Platform or task | Implemented route | Isolation and current qualification |
| --- | --- | --- |
| Linux browser workspace | Playwright Chromium, Firefox, WebKit | Headless processes and fresh contexts keep input and cookies separate from the owner's browser. Each browser binary and dependency must be installed. Real-browser results must be recorded per host; route availability alone is not a passed browser test. |
| macOS browser workspace | Playwright; configured W3C WebDriver | Playwright contexts keep browser work separate. Actual Safari uses Safari's own `safaridriver`, with owner-enabled automation. Safari hardware qualification remains separate from Chromium. |
| Windows browser workspace | Playwright; configured W3C WebDriver | Adapter route is present. Windows installation, native input permissions, process-tree cancellation, and browser versions require Windows execution evidence. |
| Linux native GUI | Optional PyAutoGUI on explicitly enabled display | Shared mode uses that display's OS cursor. An isolated Xvfb display or VM provides a separate cursor. The optional [container recipe](../deploy/README.md) provisions Xvfb; the recipe itself requires a real Docker build and native input test. |
| macOS native GUI | Optional PyAutoGUI with owner-granted OS permissions | Shared mode can interfere with the owner's input. For independent native input, run the worker in a separate macOS VM or an independently controlled login/session environment and verify routing. Opening another ordinary window does not create a second OS cursor. RDC does not provision macOS VMs. |
| Windows native GUI | Optional PyAutoGUI on its worker desktop | Independent operation requires a separate VM/session with verified desktop capture and input. A second application window shares the owner's cursor. Windows desktop/session provisioning is not automated here. |
| Android native device | Owner-configured ADB serial or Appium UiAutomator2 profile | ADB provides status, privacy-checked screenshots, taps, simple text, keys, swipes, long presses and explicit activity launch. Appium provides observation-bound native controls and a preview. Pairing and authorization remain with the owner. Protocol fixtures passed; hardware qualification remains pending. |
| iPhone/iPad native device | Owner-configured Appium XCUITest profile | November 23 development candidate: signed companion install/launch and native observation, tap, nonsecure fill, secure-screen refusal and cleanup verified on one iPhone. Swipe failed; live preview, wireless/recovery, app switching, Xcode-free WDA startup, iPad/simulator and AI-host qualification remain open. [Installers and evidence](MOBILE-INSTALL.md). |
| Phone dashboard | Responsive web page on an authenticated worker origin | Touch-friendly controller for the worker's browser and approvals. Phone-native control requires its separate device adapter. A gateway or private network route is needed when the worker remains bound to loopback. |
| ChatGPT/Claude local MCP clients | Official MCP SDK stdio, authenticated HTTP MCP | Verify each actual client and transport. Public ChatGPT web onboarding requires its supported authentication/discovery path; bearer HTTP alone is not proof of compatibility. |
| Private ChatGPT cloud connection | Owner-private Sites gateway and outbound `rdc relay` | Native RDC calls confirmed installed worker 0.1.0a4 online after activation and the matching gateway deployment. Private plugin 1.0.4 was saved and read back with its App binding and private audience preserved. Actual in-chat rendering, the publisher label and an approved live cloud browser workflow remain unresolved. See [verification](VERIFICATION.md). |
| Saved credential filling | Owner-authorized broker; classic macOS Keychain internet password or Windows generic Credential Manager target | Synthetic private fills and owner consent are tested. Native provider access, Apple Passwords/iCloud, browser extensions, Windows Hello and mobile providers require their own qualification. See [credential limits](CREDENTIALS.md). |
| Private diagnostic capture on POSIX | Bounded recorder shared by worker and relay, read-only MCP/CLI report | Requires descriptor-relative nofollow operations and SQLite serialize/deserialize. Linux recorder and relay contracts passed independent review and execution. The frozen macOS 26.6.2 arm64 candidate passed 254 tests with Python 3.14.7 and no skips. The report exposes predefined categories and incomplete-capture counters. [Diagnostic limits](DIAGNOSTICS.md). |
| Private diagnostic capture on Windows | Explicit unavailable result | `storage_status: unsupported_platform`, `available: false` and `incomplete: true`. The Python standard-library file APIs lack the required directory-relative nofollow guarantees. Worker and relay behavior continues; simulated missing-capability contracts passed. Native Windows capture requires a separate implementation and qualification. |

## Choosing the independent input path

For web work, start with the headless Playwright backend. Every session gets a
fresh context and browser-controlled pointer. The live preview is an actual image
from that session. Owner actions use the same session as agent actions. Session
cookies and pages last only for the daemon lifetime; durable terminal jobs use a
separate retained record and log.

The dashboard's Owner control switch pauses new agent input before enabling
preview clicks. Observed controls use current observation handles. Browser keys
are available through the observed session. The displayed pointer belongs to the
workspace. Pausing gates new agent browser/native input; it does not terminate
commands, stop network traffic, roll back a completed action, or cancel an input
already admitted. Owner actions can still operate while agent input is paused.

For native applications, choose an isolated virtual display, separate OS session,
or VM before enabling `desktop_mode: isolated`. That setting reports your
configuration; it cannot create or prove an independent desktop. Shared mode
explicitly uses the worker desktop's normal pointer. The dashboard exposes the
mode so that a shared desktop is visible to the owner. The preview covers browser
and Appium mobile sessions; native desktop screenshots remain adapter tools.
An Appium session uses the selected device's normal screen. It does not create a
second private display on a physical phone or tablet.

## Safari and mobile boundaries

[Playwright's browser documentation](https://playwright.dev/docs/browsers) explains
that its WebKit build uses patches and does not automate branded Safari. Label it
WebKit. To test actual Safari on macOS, follow
[Apple's WebDriver instructions](https://developer.apple.com/documentation/safari-developer-tools/webdriver/),
enable automation as the owner, and configure RDC's WebDriver URL/capabilities to
the local Safari driver. Protect that driver listener as well as RDC. This route
must pass observation, input, screenshot, and closure on the actual Safari build
before being marked tested.

Apple's device automation has separate requirements. The
[Appium XCUITest requirements](https://appium.github.io/appium-xcuitest-driver/latest/getting-started/system-requirements/)
and [device setup](https://appium.github.io/appium-xcuitest-driver/latest/getting-started/device-setup/)
describe macOS/Xcode compatibility and WebDriverAgent setup. RDC's dedicated
native Appium adapter is separate from its web-context WebDriver route. See
[mobile setup and limits](MOBILE.md) for exact device profiles, privacy refusals,
and the remaining hardware acceptance checks. Android requires the
[official ADB pairing and authorization flow](https://developer.android.com/tools/adb).
The [X.Org Xvfb documentation](https://www.x.org/docs/man/man.pdf) describes the
virtual framebuffer used by the Linux recipe.

## Qualification record

A platform can move from **adapter route** to **tested** only with a recorded host,
OS/browser version, command or client, and observed result. Browser qualification
covers create, navigate, observe, fill/click, changed page state, valid screenshot,
stale-reference rejection, pause, owner takeover, and close. Native qualification
adds a harmless GUI application, screenshot/input routing to the intended display,
and simultaneous usability of the owner's normal desktop. Phone qualification
adds a real touch browser, narrow layout, authenticated connectivity, and owner
review. Native mobile qualification is its own device test.

`tests/test_dashboard.py` uses an explicitly test-only API fixture and a
browser-generated fixture image to verify page behavior at desktop and phone
sizes. Its screenshots illustrate the UI; they are not evidence that a hardware
adapter or AI client passed. Static packaging and JavaScript checks also do not
replace those tests. Any skipped browser test must remain reported as skipped.
