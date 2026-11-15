# Compatibility and qualification

Treat this as release context dated 2026-11-15. Prefer later explicit execution evidence and the current tool schemas when they become available. An advertised adapter identifies an implemented route, not a completed test on every host.

| Route | Current evidence and boundary |
| --- | --- |
| Local macOS worker | File, durable-job, and independent Chromium workflows have run through local ChatGPT/Codex. Browser sessions survived client disconnection while the worker remained alive. |
| Private cloud connection | Native connection/status/preview-open tools succeeded in production ChatGPT on the audit baseline. The gateway is owner-private. The new mobile catalog requires the matching deployment and client discovery. Production embedded rendering and a completed approved live cloud workflow remain separate checks. |
| Embedded MCP Apps component | The official SDK and component ran in a sandboxed synthetic host with preview controls, pending-operation recovery, resize/mode handling, and lifecycle checks. These fixtures do not prove production ChatGPT, Codex, or Claude host behavior. |
| Claude | Configuration/protocol support exists. Actual Claude model execution and embedded rendering remain unverified. A text-only client cannot be assumed to display a component. |
| Safari | The real safaridriver route was attempted and blocked by disabled Allow remote automation. The owner setting was preserved. Playwright WebKit cannot substitute for real Safari qualification. |
| Windows | Hosted Windows execution of the audit baseline found four fixture assumptions concerning CRLF and a synthetic Mac path. This release corrects those fixtures. Use current hosted results to assess that revision; Windows native input and credential providers still require separate qualification. |
| Android | ADB and native Appium UiAutomator2 routes are implemented, including gestures and privacy-checked preview. Protocol fixtures passed. Pairing, permissions and real phone/tablet/emulator qualification remain owner/device-specific work. |
| iPhone/iPad | Dedicated native Appium XCUITest sessions and preview are implemented, with observation-bound touch controls and secure-field refusal. Protocol fixtures passed. Actual hardware/simulator behavior, signing/trust setup and mobile saved-password access remain unqualified; native credential filling is unsupported. |
| Native desktop independence | Shared desktop input can affect the user's cursor/focus. Independent native desktop/display/VM provisioning and native live streaming remain incomplete or unqualified. |
| Saved-password providers | Synthetic credential, owner-consent, redaction, and browser tests passed. Actual native Keychain, Windows Credential Manager, browser-manager, and mobile provider access require separate qualification. |

The current source exposes 51 core tools and the gateway adds 2 cloud recovery/status tools. A host may cache its tool inventory. Check the connected App before claiming those tools are usable in the current conversation. Follow [mobile guidance](mobile.md) for phones and tablets.

Browser sessions currently belong to the daemon and control one page each. Broad popup, tab, frame, upload, and download workflows need further work. Public multi-user onboarding and an AI-provider public directory listing are separate from this private App and the open-source repository.

Do not claim unrestricted control of every device function, a universal embedded-window API, elimination of operating-system consent, or a measured performance advantage without evidence for the specific workflow. Continue useful authorized work through the routes that are actually available.
