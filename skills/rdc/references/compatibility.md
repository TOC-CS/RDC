# Compatibility and qualification

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
unsupported. The historical campaign recorded 97/100 against its original allocation.
The owner retired the universal ceiling on November 25, 2026. Current
qualification uses scope-appropriate cases, exact counts, meaningful
timeouts and safe cleanup.

The following November 16 table is historical; use the dated update above for current mobile qualification.

Release qualification snapshot dated 2026-11-16. The installed worker reports core 0.1.0a8. The runtime/gateway candidate is prepared but not activated; an existing independent browser session remains open, and owner authorization to end it is pending. Preserve that session. The validated candidate runtime source remains commit 137a42d. Source, installed worker, deployed gateway, saved plugin guidance and the host catalog can be at different revisions. A saved documentation update does not deploy code or qualify a host. Prefer later explicit execution evidence and current tool schemas. Mobile adapters began in a3 and private diagnostics in a4; implementation is not device qualification.

| Route | Current evidence and boundary |
| --- | --- |
| Local macOS worker | The current source candidate passed 360 worker tests and 28 gateway tests. An isolated real MCP SDK stdio check passed 12 commands in batches of six, plus a script workflow and idempotent reuse, with 13 unique jobs total. These checks did not activate candidate code in the live worker. The existing a8 worker and active browser session were retained; do not restart it while another task uses it. File, durable-job and independent Chromium workflows have run through native connected tools. Browser sessions survive client disconnection while the daemon remains alive. Verify installed source and affected behavior after later activation. |
| Private cloud connection | Existing native connection, status, preview and diagnostic calls have succeeded. The 30-pair same-machine legacy RDC-versus-Desktop-Commander cloud baseline is complete. Legacy RDC was slower at p50 and p95 under the recorded tool-response boundaries; the candidate single-call fast path was not measured live. Runtime and gateway activation/readback remain pending. Preserve the App, plugin, pairing, grants, audience, connection and active browser session. Local tests and a heartbeat alone do not prove a queued call or production component completes. |
| Private diagnostics | Core 0.1.0a4 adds read-only incident history and observed relay recovery, preserved in a5. After the a5 gateway deployment, the native ChatGPT report returned `available: true`, `storage_status: ready`, `incomplete: false` and `capture_scope: retained_history_and_current_process`. POSIX capture requires the documented Python/filesystem capabilities. Windows capture is disabled with `unsupported_platform`, while ordinary worker and relay operations continue. Reports do not prove complete capture, worker liveness or repair of a user task. |
| Embedded MCP Apps component | Exact native-window and independent-browser sources have been exercised in the real Codex host. Source binding and cursor lifecycle have local regression coverage: match session/device, start the browser cursor hidden, reveal only after confirmed source-bound input, clear on navigation, clip to rendered image pixels, and suppress overlays when capture includes the cursor. A matching worker/component is required. Separate-chat ChatGPT web rendering, multiple simultaneous views and movable floating placement remain unqualified. Earlier ChatGPT App unavailable observations are historical, not proof of the current cause or status. |
| Claude | Configuration/protocol support exists. Actual Claude model execution and embedded rendering remain unverified. A text-only client cannot be assumed to display a component. |
| Safari | The real safaridriver route was attempted and blocked by disabled Allow remote automation. The owner setting was preserved. Playwright WebKit cannot substitute for real Safari qualification. |
| Windows | Hosted CI passed for commit 137a42d on both push and pull-request runs. This source-suite result does not qualify native Windows capture/input, credential providers or live host rendering; those require separate real-device evidence. |
| Linux / hosted macOS | Linux hosted CI passed for commit 137a42d on both push and pull-request runs. Hosted macOS remained queued at this snapshot, independently of the passing local Mac suite. The complete hosted matrix remains pending. Linux native-window capture and real host placement require separate qualification. |
| Android | ADB and native Appium UiAutomator2 routes are implemented, including gestures and privacy-checked preview. Protocol fixtures passed. Pairing, permissions and real phone/tablet/emulator qualification remain owner/device-specific work. |
| iPhone/iPad | Dedicated native Appium XCUITest sessions and preview are implemented, with observation-bound touch controls and secure-field refusal. Protocol fixtures passed. Actual hardware/simulator behavior, signing/trust setup and mobile saved-password access remain unqualified; native credential filling is unsupported. This release record establishes no physical iPhone 17 Pro Max, other iPhone, iPad or simulator acceptance. |
| Native desktop independence | Shared native input can affect the owner cursor/focus and requires the installed runtime owner-decision guard. Exact-window capture and independent browser sessions do not make arbitrary shell commands or global desktop input independent. Portable focus, pointer, keyboard and Space preservation remain acceptance items. |
| Saved-password providers | Synthetic credential, owner-consent, redaction, and browser tests passed. Actual native Keychain, Windows Credential Manager, browser-manager, and mobile provider access require separate qualification. |

Historical catalog evidence: the 0.1.0a5 source defined 52 core tools and the gateway added 2 cloud recovery/status tools. On the later 2026-11-15 checks, the connected host exposed 53 tools to the model; `rdc_preview_frame` is app-only. Host catalogs and account-routing fields can differ across sessions. Supply an advertised account `link_id` only where the current schema requires it, using the selection and recovery rules in [cloud operations](cloud-operations.md). These dated observations do not replace checking the current connection and worker before a new workflow.

The native `rdc_mobile_list` call succeeded with `available: false`, empty `profiles` and empty `sessions`. That observation established no configured mobile profile at the time; read the current result before assuming a profile exists. Follow [mobile guidance](mobile.md) for owner device setup and separate hardware qualification, and [diagnostics](diagnostics.md) for private incident reports.

Browser sessions currently belong to the daemon and control one page each. Broad popup, tab, frame, upload, and download workflows need further work. Public multi-user onboarding and an AI-provider public directory listing are separate from this private App and the open-source repository.

The a5 repairs keep an owned-child wait reachable after termination cleanup raises and keep credential alias, grant and decision controls consistently busy during owner requests. The primary error remains authoritative, uncertain process exit remains explicit, and failed credential removal requires an explicit retry. The passing native run does not establish the cause of historical hosted process warnings. The independent repair guardian is under development and is not installed or enabled by this release.

Do not claim unrestricted control of every device function, a universal embedded-window API, elimination of operating-system consent, or a measured performance advantage without evidence for the specific workflow. Continue useful authorized work through the routes that are actually available.


## Current setup and presentation boundaries

The installed Mac runtime reports Screen Recording and Accessibility granted. Do not repeat the grants. Preserve active user work; use a disposable or explicitly available native window for any further resize test. The setup command and runtime owner-decision guard do not authorize bypassing operating-system consent.

The OpenAI resource metadata prefers inline. The current [MCP Extensions specification](https://github.com/openai/mcp-extensions/blob/main/docs/spec.md#display-modes) supports inline/fullscreen, while the [optional component bridge](https://developers.openai.com/plugins/reference#request-another-presentation-mode) still documents PiP requests. The a8 UI feature-detects that bridge and checks the actual returned mode; refusal or an unconfirmed mode is not floating support. Do not open an external desktop window as an automatic fallback.

Outer App-owned logo and publisher attribution are blocked by the controls actually exposed for this App. A November 16 inspection of the existing RDC App found name editing, description editing, Refresh tools and Delete app, but no logo editor or publisher field. The name dialog contained only the name. Plugin More actions exposed uninstall, download ZIP, upload version and delete. The description credits TOC Ministries, while the publisher byline still uses the owner's personal name. The original mark and credit in source, website or embedded preview do not verify the outer receipt or listing. Keep the existing App and plugin identity; see [preview acceptance](preview-repair.md).

## Terminal timing evidence and limits

The local terminal-completion candidate was compared with baseline commit 3461af5 using four alternating-order rounds, 10 measured commands per method/variant/round and three warmups per method/round. All 160 measured commands and 48 warmups produced expected output. Single-call job_run p50 fell from 96.707 ms to 59.806 ms (38.16%); p95 fell from 99.214 ms to 65.111 ms (34.37%). These are direct-local RDC baseline-versus-candidate measurements with 40 observations per method/variant, not RDC-versus-Desktop-Commander cloud results or isolated shell-runtime measurements.

The completed legacy cloud baseline used 30 alternating-order pairs on the same Mac, with unchanged live worker and gateway. Timing is tool-orchestration wall time excluding model thinking. Desktop Commander's primary boundary is its initial start_process response; RDC's is durable start plus concurrent status/output retrieval. These are the recorded product routes, not equivalent single-call APIs or isolated shell-runtime measurements.

| Legacy live route | p50 | p95 |
| --- | --- | --- |
| Desktop Commander initial call | 4.972 s | 7.212 s |
| RDC start plus concurrent status/output | 9.420 s | 11.426 s |

All 60 commands produced exact expected output. RDC retained numeric exit 0 for all 30 jobs. Desktop Commander confirmed numeric exit 0 for 19; follow-up numeric-exit verification was unavailable for 11 completed sessions. Those 11 are not failed commands and must not be reported as verified zero exits. Including Desktop Commander's separate verification attempts gives p50 6.814 s and p95 9.104 s, without recovering the unavailable exit codes. Trial 1 sums measured stages to exclude a model inspection gap; later pairs used continuous orchestration. All final pairs, including transport outliers, were retained; pilot pairs were excluded. Tail estimates from 30 observations remain preliminary.

The requested 2x p50/p95 speed target is not met by this legacy baseline. The candidate's live-cloud performance and BandMates workflow acceptance remain unverified because runtime/gateway activation is pending. The isolated SDK test establishes protocol/workflow correctness only. Relay serialization, gateway polling and host/tool round trips remain separate costs. Use the existing job-start route or wait_ms=0 for known long work instead of occupying the relay with an inline wait. Preserve operation identity and verify output, exit status and recovery before claiming completion.
