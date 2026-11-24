# Phones and tablets

Use the connected tool catalog as the authority. Mobile support begins with core 0.1.0a3 and a matching gateway catalog. Confirm that the active worker and gateway have that capability; a prepared release, saved skill or cached host catalog does not establish an active deployment. A responsive dashboard alone does not control a phone's operating system.

## Select the intended device

Call `rdc_mobile_list` for safe profile aliases and current sessions. The owner configures the Appium endpoint, exact device UDID and native application outside the agent catalog. Android uses UiAutomator2; iPhone and iPad use XCUITest. Do not pair a device, accept trust prompts, change Developer Mode, grant application permissions or configure credentials on the owner's behalf.

Use `rdc_mobile_start` with a listed profile. Save the returned `session_id`, then call `rdc_mobile_observe`. Retain its `observation_id` and control handles. Use those exact identifiers for tap or nonsecure fill; use its native logical bounds for swipe. Observe again after an input and verify the actual app outcome. Never retry an uncertain mutation automatically. On a cloud connection, use the original `_rdc_request_id` and `rdc_operation_status` before interpreting the worker result.

The selected physical device's screen is shared with its user. A separate prepared simulator, emulator or dedicated phone/tablet provides an independent work surface. Starting a native session does not provision isolation or create a second private screen. Label preview sessions with their actual platform and keep browser/mobile identities distinct.

## Preserve privacy

Native observations redact editable values and secure-field labels. `secure_input_required` means the owner must enter the secret directly on the device. Do not use the browser credential picker for native controls or supply secrets through ordinary fill/text tools.

Screenshots require verified native hierarchies before and after capture. A secure field, stale screen, invalid hierarchy or existing privacy latch can make an image unavailable. `screenshot_redaction_required` is a privacy refusal, not a worker disconnect. Continue through safe redacted observations or owner assistance. Never bypass it with raw ADB, another screenshot client, desktop capture, or a new session. Hierarchy-based checks do not classify secrets painted into arbitrary app images.

Observe all truncation indicators. Image source pixels can differ from native logical coordinates; use the reported scale when interpreting a screenshot, and prefer observed handles for control input. A native fill clears the field before sending text; a failed response can leave a partial change. Inspect the current field state before deciding another action.

## Recover and close

Hide, resize, move or close the preview without closing the native session. Explicit `rdc_mobile_close` targets one exact driver session. A failed cleanup remains listed and blocks replacement. When `mobile_session_gone` confirms driver expiry, explicitly close the retained record before starting again. `mobile_creation_unknown` lacks an exact driver ID: the owner must resolve the Appium server's state before restarting RDC. Do not clear this state to force another start.

Android ADB adds swipe, long press and explicit package/activity launch through a configured serial. It does not accept arbitrary shell text, choose another device, or bypass pairing. ADB screenshots refuse competing native Appium capture and secure/unverifiable hierarchy states. Use the active native session's permitted route.

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
phone control. Follow [mobile installation](mobile-install.md) for the included
Android development APK, native source, iPhone signing/install requirements
and the owner-private iPhone artifact. This plugin update does not install
or activate candidate worker code. Check the actual connected catalog.

The source fixes cover visible SwiftUI Form descendants behind a nonaccessible
CollectionView and iOS WDA selectors omitting the AppiumAUT wrapper. They retain
hidden-window and secure-field protections. Native saved-password filling is
unsupported. The campaign is 97/100; no unrestricted tests or CI reruns.

## Client-independent mobile command preview

When the connected worker actually advertises rdc_mobile_command_read and
rdc_mobile_command_execute, inspect capabilities first. Choose direct device
operations for application lifecycle, native UI for accessible controls, and
verified visual gestures only where needed. For local commands, select the
RDC companion's local terminal and require a fresh matching result receipt.
Existing durable jobs run on the selected worker host, not the mobile OS.
No arbitrary driver scripts, guessed coordinates, or automatic replay.
See the development preview guide in the source repository:
https://github.com/TOC-CS/RDC/blob/feature/rdc-mobile-command-engine-20261124/docs/MOBILE-COMMAND-ENGINE.md
Source availability does not establish installed runtime or physical speed
qualification.
