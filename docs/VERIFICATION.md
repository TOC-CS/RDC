# RDC alpha verification

Executed 2026-11-15. This record separates real execution, protocol fixtures, configuration examples, and unfinished work.

## Verified source: 0.1.0a3

The final isolated iMac gate passed **200 tests in 67.774 seconds**, with **zero failures, errors, or skips** and exit code `0`. Wrapper time was **68.475 seconds**, on **macOS 26.6.2 arm64 with Python 3.14.7**. All **52 inputs** matched the frozen manifest and remained unchanged: 50 source inputs and two verification helpers. The [0.1.0a3 receipt](verification-results-0.1.0a3.json) records the hashes and result. No `ResourceWarning` line was observed in this run; this does not establish a cause for historical warnings.

This release adds owner-configured Android/iPhone/iPad Appium tools, mobile preview integration, expanded Android ADB input, and Windows test-fixture corrections. The full gate includes real local Chromium and embedded-component fixtures, synthetic Appium/WebDriver protocols, secure-field redaction and capture refusal, failed-session recovery, and nonblocking status during serialized mobile input. Physical phones/tablets, simulator behavior and production AI-host rendering remain unqualified. Native saved-password filling is unsupported. See [mobile setup and limits](MOBILE.md).

The preceding 200-test candidate run had one error: an embedded-preview test still expected “different browser session” after the shared browser/mobile preview changed its message to “different session.” Updating that exact assertion was the only input change for the final run; no runtime behavior or deadline was changed. The failed result remains in the verification chronology.

Source qualification, installation, and public-directory availability are separate. The installed alpha2 baseline below is retained as historical evidence until an alpha3 deployment is independently verified.

### Earlier hosted alpha2 run

An earlier hosted matrix executed the audited 0.1.0a2 source. Ubuntu passed 147 tests in 80.830 seconds with no skips. macOS passed 147 tests in 123.877 seconds with no skips. Windows ran 147 tests in 87.923 seconds with four fixture failures and one POSIX-only FIFO skip. Three failures assumed LF output where Python printed CRLF; the fourth supplied a real Windows path to a simulated Mac Keychain test. This candidate uses explicit byte-output fixtures and a synthetic POSIX home path. Production output remains raw bytes and native locator validation remains strict. The corrected candidate still requires its own hosted Windows result.

The public repository was reinitialized on 2026-11-15 with a project-only author identity and GitHub no-reply commit metadata. The earlier hosted run belongs to a retained private history and is historical evidence, not a current publicly accessible CI link. Current source publication and hosted checks are verified against the new repository history.

## Audited and installed baseline: 0.1.0a2

The final frozen iMac suite passed **147 tests in 55.091 seconds**, with no skips and exit code `0`. Wrapper time was **55.655 seconds**, on **macOS 26.6.2 arm64 with Python 3.14.7**. All **35 recorded runtime/test inputs** matched the manifest and remained unchanged during execution. The [0.1.0a2 receipt](verification-results-0.1.0a2.json) records the platform, result and individual SHA-256 hashes. This is the combined result for the [audit repairs](AUDIT-2026-11-15.md).

| Check | Current evidence |
|---|---|
| Real Chromium credential privacy | The direct screenshot pixel test passed after a synthetic credential fill, private-marker removal and a Show Password type change, before another observation. The field was black-masked and the subsequent observation remained redacted. |
| Embedded preview | The official SDK UI tests passed in a synthetic protocol host, including asynchronous ended-session recovery, explicit replacement selection, approval waiting, refreshed zero counts and browser labels. This qualifies the component; real ChatGPT/Claude rendering remains separate. |
| Native credential selection | Broker and low-level C API fixtures passed for an explicit classic Keychain file, unique-item metadata checks, exact HTTPS/port matching and legacy re-enrollment. No real Keychain or Windows credential store was opened. |
| Recovery and resources | The full suite includes partial stdin writes, input failure status, recoverable MCP protocol errors, undeliverable relay tombstones, bounded browser handles/truncation, uncertain WebDriver cleanup and closure of rejected HTTP response streams. |
| Actual ChatGPT connection | Native RDC tools are connected and functional. Connection status, worker status and preview open succeeded; identical cloud request-ID reuse returned the same pending owner approval ID. The approval was not granted for that workflow. |
| Private plugin | App-backed RDC plugin **1.0.2** was saved and read back successfully. That private plugin version is separate from the portable package version `0.1.0-alpha.2`. Actual embedded rendering and a newly approved cloud browser workflow remain unverified. |
| Live worker | Restarted onto **0.1.0a2** with the same device identity, unchanged configuration hash, workspace access, review mode and disabled native desktop input. Native ChatGPT status confirmed the version; connection status was online with zero pending operations. |
| Private gateway | Deployment reached terminal success on **2026-11-15 at 06:26:16.746308 UTC**, on the same owner-private Site with MCP enabled. This deployment result does not establish embedded rendering. |
| Public source | The audit checkpoint initially contained `LICENSE` only. Complete alpha2 source and the earlier hosted matrix followed; the public repository was subsequently rebuilt with project-only identity. Current publication is verified against the new history. |

### Verification chronology and diagnostic limit

An initial repair run passed 146 tests. A subsequent 147-test run failed only the older FIFO fixture's deadline: its two-second budget included Python imports and Engine startup. The fixture now waits for readiness under a separate ten-second startup budget, then triggers the FIFO read under the **unchanged two-second operation deadline**. The final frozen 147-test run passed. This is fixture isolation, with the same required `not_regular_file` result and bounded process cleanup; the operation deadline was not relaxed.

A Python `ResourceWarning` that a subprocess was still running was observed during the output-capture timeout fixture. No PID attribution was captured. The evidence does not establish its cause or whether that process persisted after teardown. All final assertions passed, and that diagnostic limit remains open. The separate WebDriver HTTPError cleanup regression verifies closure of an HTTP response stream and does not explain this subprocess warning.

## Historical 0.1.0a1 baseline

| Check | Evidence |
|---|---|
| iMac full suite | **109 tests passed**, no skips, **48.483 seconds**; macOS 26.6.2 arm64, Python 3.14.7. Includes embedded preview, owner credential enrollment, private filling, the shared resource bridge and idle relay backoff. All 32 recorded runtime/test inputs were unchanged during the run, and their SHA-256 hashes match the packaged source. See `verification-results-2026-11-15.json`. |
| iMac embedded preview suite | **13 tests passed**, no skips, **23.566 seconds**. The official MCP Apps SDK ran inside a sandboxed iframe in a synthetic protocol host. Includes pending cloud operation recovery without replacement dispatch. This verifies the component and lifecycle, not rendering inside production ChatGPT or Claude. |
| Linux development suite | **86 tests run, OK with 5 skips**, 27.406 seconds; Python 3.12.14, with a writable workspace TMPDIR. Browser/UI classes could not launch Chromium because the execution environment denied its singleton socket. Class-level skips account for differing discovered test counts. |
| Real ChatGPT/Codex | Existing ChatGPT login, OpenAI `gpt-6-astra`, ephemeral command invocation, shared `rdc connect` route; exit 0 |
| File workflow through real ChatGPT | Read fixture SHA, exact edit, independent readback `RDC edit verified\n` |
| Background job through real ChatGPT | Explicit `/bin/echo` fixture command; completed, exit 0, exact `RDC durable job verified\n` retained output |
| Browser workflow through real ChatGPT | Start isolated Chromium, navigate synthetic fixture, observe, fill, reobserve, click, verify `Hello, RDC!`, capture screenshot, list session |
| Shared browser after actual client disconnect | Owner API independently observed the same session and page text; valid 16,296-byte screenshot retrieved after Codex exited |
| Dashboard | Actual Chromium on iMac, desktop and 390 px phone-width fixture layouts, no horizontal overflow, preview image, pause, observed control click, owner review, job output, cancellation, disconnect clearing |
| Embedded preview controls | Hide and reopen; host teardown and remount; fullscreen, inline and PiP requests; host refusal; constrained pointer/keyboard move and resize inside the RDC canvas; narrow layout and a fixed 200 px host height with accessible scrolling |
| Embedded preview identity and lifecycle | Selected second session survives refresh; expired selection becomes explicitly unselected; incorrect-session frames are rejected; one in-flight frame read; missing server-tool bridge prevents polling. A real Engine browser session and durable job survived hiding and remounting the view. |
| MCP | Official SDK 2.3 stdio subprocess and real localhost HTTP tests; legacy initialize flow and modern Client image call; token/role/origin/host/body-size checks |
| Bridge | Actual TCP worker plus stdio subprocess; same-worker browser fixture, disconnect/reconnect persistence, token rejection, timeout without mutation replay; UI resource metadata, server identity and image forwarding; a missing resource returns a recoverable error without breaking the bridge |
| Native/Android/WebDriver | Protocol and mocked adapter tests, permission-disabled paths, UTF8 limits, screenshot/input coordinate scaling; no claim of actual device qualification |
| Independent review | Reproduced FIFO blocking, output-file failure, native scaling mismatch and Unicode queued-byte bug; corrected with regression tests. Secondary early-EOF regression was reproduced and corrected. |
| Embedded independent review | Reproduced session refresh switching to the first browser and a short host viewport being exceeded. Both were corrected and rechecked. Preview resource and frame routes expose no owner token or owner operation. |
| Plugin packaging and branding | Portable `plugin.json` and `mcp.json` passed the retrieved official Agent Plugins 1.0.0 schemas. Both icon fields reference the included original RDC logo; image dimensions and size satisfy documented limits. Package validation does not establish installation or host rendering. |
| Credential broker | **23 focused iMac tests passed in 13.627 seconds**, with no skips, and passed again in the final 109-test suite. They cover synthetic HTTPS filling, owner consent, atomic one-time use, origin/document binding, revoke/pause, restart without replay, private mapping enrollment/removal, interrupted-removal recovery, error redaction, owner routes, responsive approval and setup dialogs, and clearing private setup metadata on page exit. Real Keychain or Windows saved credentials were not read. |
| Cloud relay | **23 focused iMac tests passed in 2.821 seconds**, and passed again in the final 109-test suite. Real HTTP MCP fixtures cover lost result uploads with one dispatch, journal recovery, oversized outer envelopes, bounded teardown, delayed delivery expiry, cross-language hashing and bounded idle backoff. Idle polls back off to five seconds; active execution heartbeats remain separate. |
| Gateway | 9 tests passed using a SQLite-backed D1 shim and R2 fixture; TypeScript and the production Vinext build passed. The sanitized public export also passed all 9 gateway tests. |
| Live cloud deployment | Owner-private deployment succeeded. After the final verified-source restart, the worker exposed all 40 tools, including the three credential tools and both preview tools. Existing device identity and grants were preserved. The outbound service/device-authenticated heartbeat again returned HTTP 200 with the correct device identity. No inbound device port was exposed and the owner token remained local. |
| Private ChatGPT plugin | Canonical App-backed RDC plugin version 1.0.1 was saved through Plugin Creator; its skill and retained App configuration read back successfully. Installation/connection and production in-chat rendering were unverified at this baseline. Current connection evidence is recorded above. |
| Skill use | A fresh agent used the RDC skill to run a temporary job, reconnect from a new client process, recover 53 bytes of output in two chunks, verify independent file readback, and select the shared-preview connection command. |

The historical 109-test iMac run and earlier core run also recorded a Python ResourceWarning about a process still running during output-capture timeout cleanup. All assertions passed. The current diagnostic limit is recorded above; historical warnings do not identify the process responsible for a later warning.

The embedded bundle uses the official MCP Apps SDK, bundled locally with its dependency licenses and the RDC logo. It makes tool calls through the host bridge and has no direct worker network connection. Hiding or dismissing the view performs no browser-close, job-cancel, or owner-pause action. A fresh view can attach using the saved session ID; an unqualified new open call selects the first available session. Optional model-context updates and a visible complete session ID support reopening the intended session.

In-canvas movement and resizing apply only within space the AI host allocates. The host chooses whether to provide PiP, a conversation panel, or fullscreen and may refuse a mode request. These tests do not establish an unrestricted movable window inside every AI application.

## Historical local worker measurements

Synthetic fixture measurements on the iMac, with no model or remote network latency included:

| Operation | Median | p95 | Samples |
|---|---:|---:|---:|
| Small file read and hash |0.175ms|0.201ms|25|
| Worker status |1.422ms|1.783ms|25|
| Retained job output |1.811ms|2.688ms|25|
| Warm browser observation |4.993ms|22.258ms|10|
| Browser screenshot |70.990ms|110.782ms|10|

Job admission 3.307 ms; tiny job end-to-end 192.104 ms; browser cold start 294.831 ms; engine startup 18.275 ms. This earlier core benchmark measured a 35-tool, 16,840-byte JSON catalog before adding the two embedded-preview tools. These are small-sample measurements, not a comparative benchmark or guarantee. Model response time, client approvals, relay/network latency, page complexity and CPU load change end-to-end results.

Reproduce with `python scripts/benchmark.py --browser` in the installed environment. Use equivalent tasks on each product before asserting a speed advantage.

## Remaining qualification

- Actual Claude model execution: CLI exists on the iMac but reports no logged-in account. Configuration and protocol examples exist; no Claude model result is claimed.
- Actual Safari: launched the real Apple safaridriver and attempted a W3C session. Safari rejected creation because **Allow remote automation** is disabled in Safari Settings. The setting was not changed. The live fill/click/screenshot check remains blocked until the owner enables it; WebKit cannot substitute for this test.
- Windows: the hosted baseline ran and exposed the fixture failures recorded above. The new fixture corrections need hosted execution at their published revision. Windows ACLs, native input and actual credential providers require separate device qualification.
- iOS/Android: native adapter and preview fixtures are implemented in the current candidate; no physical phone or tablet was connected. Actual Appium drivers, OS/device behavior and native credential providers remain unqualified. Native saved-password filling is unsupported.
- Native independence: the desktop adapter is optional, and the Linux Xvfb/container recipe is unbuilt in this session. Actual native-app isolation and live native preview remain incomplete.
- Browser sessions are daemon-resident. They survive chat/bridge disconnect, not daemon exit. One session currently controls one page; broad popup/tab/frame and upload/download workflows need expansion.
- Production embedded hosts: the component and host protocol were tested, but rendering inside production ChatGPT or Claude remains pending. Codex's existing built-in preview does not establish third-party MCP Apps rendering support.
- ChatGPT web: the private gateway and plugin are connected, and native RDC tool calls succeeded. Real host rendering, advertised display modes and an explicitly approved live cloud browser workflow remain unverified. The earlier installation-page navigation obstacle is historical. Desktop/Codex execution cannot substitute for embedded acceptance.
- Public GitHub repository: the new source publication and its hosted matrix require verification at their exact revisions. Public ChatGPT directory listing and multi-user OAuth onboarding remain separate from public source availability.
- Process diagnostic: attribute the timeout-fixture subprocess warning using PID and teardown observations before concluding whether cleanup needs another change.

## Reproducibility and data handling

Tests used separate source and fixture directories and did not replace the existing TOC Studio. ChatGPT's model/provider overrides were invocation-local. The test prompt restricted actions to synthetic fixtures; enabled commands still ran with the worker account permissions. Its worker was stopped after evidence capture. No subscription was cancelled. Source excludes credentials, private state, virtual environments, browser profiles, user output logs and personal TOC content.

Hosted CI evidence is recorded by exact source revision above. Installation remains an alpha development deployment; each required replacement workflow needs its own acceptance evidence.

## Historical local installation

RDC was installed into a separate iMac development directory. A default local owner profile and running worker were created, with a dedicated working root, command execution enabled, per-operation owner review, and native desktop input disabled. Codex and Claude Desktop received a new `rdc connect` entry; existing client settings were backed up and preserved. No application was restarted. The owner dashboard was connected and used in the actual local Chrome browser to start a separate session, navigate a synthetic page, fill a field, click a greeting button, and verify the rendered result. The live tab was retained for owner inspection.

That browser dashboard remains an administrator and diagnostic interface. It does not satisfy the primary requirement for a preview inside the AI application. The portable embedded resource supplies that interface for compatible hosts. The current private ChatGPT connection and 0.1.0a2 worker restart are confirmed above; production UI acceptance remains pending. The worker and relay remain development processes without login-service registration, so a machine restart requires starting them again.
