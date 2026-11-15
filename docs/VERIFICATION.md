# RDC alpha verification

Executed 2026-11-15. This record separates real execution, protocol fixtures, configuration examples, and unfinished work.

## Verified and installed source: 0.1.0a5

The frozen iMac gate passed **256 tests in 106.095 seconds**, with **zero failures, errors, skips, expected failures or unexpected successes** and exit code `0`. Wrapper time was **107.145 seconds**, on **macOS 26.6.2 arm64 with Python 3.14.7**. Discovery and execution both counted 256 tests across 17 modules. All **54 inputs** matched the frozen manifest and remained unchanged: 52 source inputs and two verification helpers. No `ResourceWarning` line was observed; this does not establish the cause of historical subprocess warnings.

The tested runtime was frozen from source commit `499fac031519746e558f0172b15a22aa205d0835` as candidate `repairs-0.1.0a5-final1`. The [sanitized public receipt](verification-results-0.1.0a5.json) retains its input hashes, counts, timings and qualification limits, and identifies the raw proof by SHA-256. Personal locations, identities, operational logs and private installation metadata are omitted. The coordinator independently verified the receipt and all 54 before/after hashes. This documentation update leaves all 52 tested source inputs unchanged.

The a5 repair source starts from the complete 225-file public a4 baseline and integrates two independently reviewed corrections: bounded waiting for an owned child remains reachable when termination cleanup raises, and credential alias, grant and decision controls all reflect the dashboard's busy state. The primary worker error remains authoritative; an unconfirmed child exit retains a null exit code and explicit uncertainty. Credential removal still requires an explicit retry after failure.

The preceding combined Linux gate passed **30 tests in 15.386 seconds**, with no failures, errors, skips or warning output and exit code `0`: 14 source UI contracts plus 16 worker-I/O and durable-job contracts. All 225 tracked file hashes remained unchanged during that execution. Local discovery found 256 tests without running the full suite. The known local browser sandbox restriction was respected; the subsequent isolated iMac execution supplies the complete native fixture gate above.

The embedded resource was rebuilt with the existing pinned MCP Apps SDK **2.0.4** and esbuild **0.28.2**, without installing or upgrading dependencies. All 17 installed dependency versions matched the lockfile. The 2,021,249-byte result matches the a4 bundle except for its explicit version string; SHA-256 is `076fbae87ce3829e3129c0604cf7b4b028dbd32cc8c347a493c27d3aabc3ce94`. Original logo bytes and third-party notices are unchanged. The gateway asset-sync script copied that resource; its 52-tool catalog and icon remain identical to a4. Gateway tests, a production build and deployment were not performed for this source preparation.

### Separate a5 activation, private cloud release and remaining gates

| Check | Observed result |
|---|---|
| Exact source activation | Independent post-install verification confirmed all **52 live source input hashes** match the frozen a5 manifest. The complete previous runtime backup matched its recorded inventory, and protected state was preserved. |
| Process and listener checks | The previous processes had exited, and the sole worker listener matched the installed worker. Private process identifiers are omitted. |
| Public a5 release and hosted CI | Exact public head `cdf709cb2ba391c43b0e797760e50d8e168864f6` matched all 226 reviewed files. [Run 43707243784](https://github.com/TOC-CS/RDC/actions/runs/43707243784) completed successfully on Linux, macOS and Windows. The platform counts and skips are recorded below. |
| Matching private gateway | The coordinator verified source `f4ea8d5d4f89cf34bb97f08ce88d8faca04efb59`, containing only the two version/embedded-resource updates relative to a4. **9 gateway tests passed with no skips**, TypeScript checking and the production build passed, and deployment reached terminal success with MCP enabled. The owner-private audience was preserved. |
| Existing private plugin | The coordinator independently read back all **9 files** of App-backed plugin **1.0.6** exactly. Five files changed: two version-only manifests, the skill, cloud operations and compatibility guidance. The App binding, existing description and App-owned presentation, credential/mobile/diagnostic guidance and private audience were preserved. |
| Current native host checks | Worker status returned **0.1.0a5**. The current catalog exposes **53 model-visible tools**, matching 54 server tools with app-only `rdc_preview_frame`; host account routing is advertised. The old 41-tool snapshot is historical. Existing owner requests were preserved. |
| Native diagnostic report | The post-deployment call returned `available: true`, `storage_status: ready`, `incomplete: false` and `capture_scope: retained_history_and_current_process`. It reported 50 retained events, with zero dropped, pending or invalid diagnostic events. These counters do not establish the outcome of an unrelated task. |
| Configured mobile availability | Native listing returned zero profiles and sessions. No physical phone/tablet workflow is qualified. |
| Independent guardian | Not deployed. No guardian maintenance or automatic code-activation behavior is qualified by this suite or installation. |

The public suite receipt covers isolated automated fixtures; installation was verified separately. Native saved credentials, physical phones/tablets, actual AI-host rendering and an approved live cloud browser workflow retain their own qualification gates. The worker repair demonstrates a separate exception-path defect; the passing a5 run does not identify the cause of the historical hosted macOS subprocess warning. The 254-test a4 receipt below remains unchanged and applies only to its recorded source.

### Public a5 source readback and exact-head hosted gate

The public release [cdf709cb2ba391c43b0e797760e50d8e168864f6](https://github.com/TOC-CS/RDC/commit/cdf709cb2ba391c43b0e797760e50d8e168864f6) has tree `7382715a73aae8890b91d679b3b78351d892912c`, identical to reviewed source `689b799052304e01aef9dc9a205801cc04a751a8`. The untruncated recursive GitHub tree matched **226 files / 9,457,650 bytes**, plus 48 directory objects, on path, blob identity, mode, size and type. There were no missing or extra files. All 11 publication commits after the preserved concurrent head `e9fdae89d07552075ae4ba2ada02f2af916e818f` used TOC/GitHub names and GitHub no-reply attribution. Private source ancestry was not republished.

The [hosted workflow](https://github.com/TOC-CS/RDC/actions/runs/43707243784) ran against that exact public head and reached terminal **success at 2026-11-15 11:11:03 UTC**. Decoded job logs establish these results:

| Hosted platform | Discovery | Executed passes | Explicit skips | Suite time | Test-suite warnings / ResourceWarnings |
|---|---:|---:|---:|---:|---:|
| Ubuntu | 256 | 256 | 0 | 100.359 s | 0 / 0 |
| macOS | 256 | 256 | 0 | 140.463 s | 0 / 0 |
| Windows | 256 | 239 | 17 | 135.196 s | 0 / 0 |

Windows skips comprise 16 secure diagnostic-storage cases requiring POSIX descriptor operations and one POSIX FIFO contract. Windows diagnostic capture therefore remains unavailable; a green job does not remove that limit. Each job also emitted five infrastructure Node deprecation lines, separately from the test suite: three `DEP0040`, one `DEP0169`, and one notice concerning the Node 20 action runtime. These infrastructure notices are retained as observed evidence. The passing matrix does not identify the cause of historical subprocess warnings or qualify native devices, vaults, desktop isolation or AI-host rendering.

This later documentation-only evidence update preserves all 52 frozen runtime/test source inputs. The tested source remains the exact release head above; the documentation commit is not presented as another full test run.

## Historical verified source: 0.1.0a4

The frozen iMac gate passed **254 tests in 67.244 seconds**, with **zero failures, errors, skips, expected failures or unexpected successes** and exit code `0`. Wrapper time was **67.884 seconds**, on **macOS 26.6.2 arm64 with Python 3.14.7**. Discovery and execution both counted 254 tests across 17 modules. All **54 inputs** matched the frozen manifest and remained unchanged: 52 source inputs and two verification helpers. No `ResourceWarning` line was observed; this does not establish the cause of historical warnings.

The runtime was frozen from source commit `4a18ec0a87d30d4f37dea9b03a611098e14bc527` as candidate `diagnostics-0.1.0a4-final1`. The [sanitized public receipt](verification-results-0.1.0a4.json) preserves the exact input hashes, test outcomes and timings, and identifies the original receipt by SHA-256. Personal paths and operational logs are omitted. Live activation and the matching gateway deployment were subsequently verified separately, as recorded below.

| Check | Executed evidence |
|---|---|
| Diagnostic recorder | Independent review passed. **21 tests passed**, no skips, in **2.064 seconds**, covering finite data validation, bounded queues and retention, private file handling, corrupt/unsafe storage, incomplete capture, read-only reports and unsupported-platform behavior. |
| Relay and recorder integration | **55 tests passed**, no skips, in **5.470 seconds**. Existing delivery, restart, unknown-outcome and no-replay behavior remains covered when the recorder fails or secure capture is unavailable. |
| Credential removal and UI fixture regressions | **14 focused UI contracts passed**, no skips, in **1.412 seconds**. The contracts execute the dashboard source through the DOM fixture, hold the decision's refresh, check disabled removal through re-render, then verify one request, explicit retry and successful removal. LF and CRLF embedded-source variants are exercised. |
| Real Chromium credential workflow | The enhanced enrollment/consent/removal test passed on the iMac: **1 test in 12.511 seconds**, no skips. Its delayed status response forces the original busy-state race. Test cleanup releases the held response before unregistering its handler. Only synthetic credentials and isolated test state were used. |
| Gateway source | The matching **52-tool** core catalog was generated from alpha4, alongside the rebuilt embedded resource. **9 gateway contract tests passed**, the TypeScript check exited zero, and the production build passed. The exact source was pushed and deployed as `38ea4b59c04dab8e2f8966317a30e44e0aa72a88`. |

Private diagnostic capture records predefined event categories without arguments, raw errors, paths, credential locators, page content or operation identifiers. Existing relay reconnect and retained-result delivery provide the defined automatic recovery. Unknown device outcomes remain protected against replay; unknown code defects require reproduction, reviewed repairs, tests and approved version activation. Windows secure capture reports unavailable while worker and relay operations continue. See [diagnostics](DIAGNOSTICS.md) for capture, retention and crash limits.

### Verified activation and private cloud route

The later a4 host and guidance observations below are preserved from the [concurrent public follow-up](https://github.com/TOC-CS/RDC/commit/e9fdae89d07552075ae4ba2ada02f2af916e818f). This reconciliation verified the published content and preserves its dated claims; it did not repeat that follow-up's private plugin readback, screenshots or host actions. The separately qualified a5 coordinator checks are recorded above.

| Check | Observed result |
|---|---|
| Exact source activation | The reviewed installer activated all **52 frozen source inputs** and retained the previous code for rollback. The configuration hash, paired device identity, grants, pause state, protected token-file metadata and existing virtual environment were preserved. |
| Native ChatGPT status | `rdc_system_status` reported **0.1.0a4**, the same device identity and idle online state after installation, after gateway deployment and in the later completion check. |
| Real diagnostic store | The local CLI exited zero with `available: true`, `storage_status: ready` and `incomplete: false`. It read **one real relay `result_uploaded` event**, zero dropped events and zero pending events. This confirms that stored observation; it does not identify or certify an unrelated user task. |
| Native ChatGPT diagnostics | The later `rdc_diagnostics_status` call succeeded with `available: true`, `storage_status: ready` and `incomplete: false`. This establishes access through the connected tool, without claiming complete capture or resolution of a particular task. |
| Matching private gateway | The existing owner-private Site reached terminal deployment success with MCP enabled, from source `38ea4b59c04dab8e2f8966317a30e44e0aa72a88`. Its matching catalog provides **52 core tools plus 2 gateway tools**. |
| Existing private plugin | App-backed plugin **1.0.4** was saved through the existing update route. All six changed files exactly matched the approved overlay; three protected files (App binding, cloud recovery and credential guidance) exactly matched the prior release. All nine files were accounted for and the private audience was preserved. The rendered publisher label in ChatGPT remains unresolved; no TOC Ministries label correction is claimed. |
| Host catalog freshness | The conversation initially retained **41 model-visible tool names** after deployment. A later direct catalog check exposed **53 model-visible tools**, including mobile and diagnostics, matching the **54-tool server catalog** with one app-only `rdc_preview_frame`. Current host schemas require an advertised account `link_id`. This observed refresh does not establish a guaranteed refresh procedure for every host. |
| Configured mobile availability | The native `rdc_mobile_list` call succeeded with `available: false`, `profiles: []` and `sessions: []`. The mobile tools are discoverable, but no mobile profile is configured on this worker and no physical phone or tablet acceptance is claimed. |
| App presentation and preview | Owner-supplied settings screenshots show App name and App description editors plus Refresh tools, with no icon or publisher editor. Branding requests remain optional and unresolved. A production preview opening showed "App unavailable" while the native preview tool returned successfully; its cause remains unconfirmed. |
| Public alpha4 release | The integrated source was published at [`e4f6f18c8d1002462fccd93f85a1be1e1983cb52`](https://github.com/TOC-CS/RDC/commit/e4f6f18c8d1002462fccd93f85a1be1e1983cb52). Independent readback matched all **225 manifest paths, blob IDs, modes and sizes** to approved local source `12335ccedf6e6464ae8924b051b2742296afd2d3`, with no missing, extra or mismatched files. Its exact-revision hosted matrix passed as detailed below. |

The embedded component's production rendering, host display modes and an explicitly approved live cloud browser workflow retain their separate acceptance checks. Existing owner permissions remain authoritative. The source inspection found the preview tool/resource binding and self-contained UI bundle present; that check does not establish the resource response or rendering observed by the production host.

### Reported a4 skill guidance follow-up

The concurrent public follow-up records an update of the existing App-backed plugin to **1.0.5** on 2026-11-15, with all nine files read back exactly: six changed files provide required host account routing, corrected diagnostic arguments and current qualification notes; the App binding, credential guidance and mobile guidance were retained. It reports that App-owned presentation and the private audience were preserved. This was a guidance-only update; runtime, tests, gateway assets and core version remained unchanged from the qualified alpha4 release. Its focused planning check retained the selected account and original operation identity without replaying an uncertain edit or mobile fill. It also records that personal-skill icon updates using the original logo were replaced with a generated SVG during saving. The original logo asset remains intact, but no custom-logo correction is claimed for the personal skill, plugin listing or integration activity. These reported 1.0.5 observations are separate from the coordinator's exact 1.0.6 readback above.

### Public alpha4 hosted matrix

The qualified public source commit is [`e4f6f18c8d1002462fccd93f85a1be1e1983cb52`](https://github.com/TOC-CS/RDC/commit/e4f6f18c8d1002462fccd93f85a1be1e1983cb52), published on **2026-11-15 at 09:34:56 UTC**, with tree `b7b1f0fc4181a86963e498a807f4579d3acb79f5`. That tree exactly matches approved local source `12335ccedf6e6464ae8924b051b2742296afd2d3`. The [exact-revision hosted workflow](https://github.com/TOC-CS/RDC/actions/runs/43699939501) reached **SUCCESS at 09:41:45 UTC**.

| Platform | Tests reported | Executed / passed | Skips | Suite time | Failures / errors | Job result |
|---|---:|---:|---:|---:|---:|---|
| Ubuntu | 254 | 254 | 0 | 106.264 seconds | 0 / 0 | Passed |
| macOS | 254 | 254 | 0 | 118.976 seconds | 0 / 0 | Passed |
| Windows | 254 | 237 | 17 | 158.131 seconds | 0 / 0 | Passed with skips |

The Windows result reports 254 discovered tests, comprising **237 executed passes and 17 skips**. The skips are one POSIX FIFO contract and **16 secure diagnostic storage contracts** requiring POSIX descriptor operations: 14 `DiagnosticsTests` and two `WorkerDiagnosticTests`. Windows secure capture remains explicitly unavailable. Passing the hosted job does not qualify that unimplemented capture path, physical devices or native credential providers.

The concurrent a4 follow-up reports a subprocess `ResourceWarning` during `test_capture_error_survives_command_timeout`, while the test and job passed; the retained coordinator summary counts two ResourceWarning lines. Its origin remains unestablished. That follow-up reports a targeted Linux review with 25 repetitions of the timeout test and the full ten-test worker-I/O module under forced collection: all observed children were reaped and no warnings appeared. It found no basis for a runtime change in that review. Those historical checks predate the separately reproduced a5 exception-path repair and do not identify the hosted warning's cause. The warning remains unresolved; the evidence establishes neither a harmless warning nor a confirmed surviving-child leak. The separate frozen a4 and a5 local Mac runs each recorded **zero ResourceWarning lines**.

### Public alpha3 CI and alpha4 repairs

All **218 intended alpha3 public files** matched their exact blob hashes and modes at commit [`76c5793e924612439d12b8d9ac7e288939fd07aa`](https://github.com/TOC-CS/RDC/commit/76c5793e924612439d12b8d9ac7e288939fd07aa), with no missing or extra paths. Its [hosted workflow run](https://github.com/TOC-CS/RDC/actions/runs/43695142921) completed with a failed matrix:

| Platform | Result | Confirmed cause and repair |
|---|---|---|
| macOS | **200 tests passed in 116.152 seconds**. | The job passed. Its output-capture timeout fixture also emitted a subprocess `ResourceWarning`; the warning's cause remains unassigned. |
| Ubuntu | One credential UI error. | Remove remained enabled while the preceding credential decision awaited its status refresh. The busy guard discarded the click before sending a request. Alpha4 disables existing and newly rendered removal buttons until that action completes, while preserving explicit retries. |
| Windows | Five embedded UI fixture failures. | The source fixture removed its leading import only for LF line endings. CRLF left an ES-module import inside the VM script. Alpha4 accepts both line endings and adds an explicit regression. |

The repairs were subsequently published at commit [`314ebb850ea4aca2af82c85a7a1a2b96f41e9884`](https://github.com/TOC-CS/RDC/commit/314ebb850ea4aca2af82c85a7a1a2b96f41e9884). [That repair run](https://github.com/TOC-CS/RDC/actions/runs/43697887451) **passed on Linux, macOS and Windows**. This successful matrix applies to the alpha3 repair revision; the integrated alpha4 source has its own verified publication and hosted matrix above.

## Historical verified source: 0.1.0a3

The final isolated iMac gate passed **200 tests in 67.774 seconds**, with **zero failures, errors, or skips** and exit code `0`. Wrapper time was **68.475 seconds**, on **macOS 26.6.2 arm64 with Python 3.14.7**. All **52 inputs** matched the frozen manifest and remained unchanged: 50 source inputs and two verification helpers. The [0.1.0a3 receipt](verification-results-0.1.0a3.json) records the hashes and result. No `ResourceWarning` line was observed in this run; this does not establish a cause for historical warnings.

This release adds owner-configured Android/iPhone/iPad Appium tools, mobile preview integration, expanded Android ADB input, and Windows test-fixture corrections. The full gate includes real local Chromium and embedded-component fixtures, synthetic Appium/WebDriver protocols, secure-field redaction and capture refusal, failed-session recovery, and nonblocking status during serialized mobile input. Physical phones/tablets, simulator behavior and production AI-host rendering remain unqualified. Native saved-password filling is unsupported. See [mobile setup and limits](MOBILE.md).

The preceding 200-test candidate run had one error: an embedded-preview test still expected “different browser session” after the shared browser/mobile preview changed its message to “different session.” Updating that exact assertion was the only input change for the final run; no runtime behavior or deadline was changed. The failed result remains in the verification chronology.

Source qualification, installation, and public-directory availability are separate. The alpha3 source passed the isolated Mac gate, its first public hosted matrix failed, and the repair revision subsequently passed all three OS jobs. Alpha5 activation and the historical alpha4 activation are recorded above; the alpha2 installation below remains historical evidence for its recorded source.

### Earlier hosted alpha2 run

An earlier hosted matrix executed the audited 0.1.0a2 source. Ubuntu passed 147 tests in 80.830 seconds with no skips. macOS passed 147 tests in 123.877 seconds with no skips. Windows ran 147 tests in 87.923 seconds with four fixture failures and one POSIX-only FIFO skip. Three failures assumed LF output where Python printed CRLF; the fourth supplied a real Windows path to a simulated Mac Keychain test. This candidate uses explicit byte-output fixtures and a synthetic POSIX home path. Production output remains raw bytes and native locator validation remains strict. The later alpha3 repair matrix above supplies passing Windows evidence for its recorded source.

The public repository was reinitialized on 2026-11-15 with a project-only author identity and GitHub no-reply commit metadata. The earlier hosted run belongs to a retained private history and is historical evidence, not a current publicly accessible CI link. Current source publication and hosted checks are verified against the new repository history.

## Historical audited and installed baseline: 0.1.0a2

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
- Windows: the exact alpha4 hosted job passed with 17 documented POSIX-only skips. Secure diagnostic capture remains unavailable; Windows ACLs, native input and actual credential providers require separate device qualification.
- iOS/Android: native adapter and preview fixtures are implemented in the current candidate; no physical phone or tablet was connected. Actual Appium drivers, OS/device behavior and native credential providers remain unqualified. Native saved-password filling is unsupported.
- Native independence: the desktop adapter is optional, and the Linux Xvfb/container recipe is unbuilt in this session. Actual native-app isolation and live native preview remain incomplete.
- Browser sessions are daemon-resident. They survive chat/bridge disconnect, not daemon exit. One session currently controls one page; broad popup/tab/frame and upload/download workflows need expansion.
- Production embedded hosts: the component and host protocol were tested, but rendering inside production ChatGPT or Claude remains pending. Codex's existing built-in preview does not establish third-party MCP Apps rendering support.
- ChatGPT web: the matching a5 private gateway and plugin 1.0.6 were verified, and native worker/diagnostic calls succeeded. The concurrent public follow-up's "App unavailable" preview observation remains unresolved. Real host rendering, advertised display modes and an explicitly approved live cloud browser workflow remain unverified. Desktop/Codex execution cannot substitute for embedded acceptance.
- Public GitHub repository: all 225 alpha4 files matched the approved release tree, and its exact-revision hosted matrix passed with the Windows skips recorded above. Public a5 publication and its hosted matrix remain pending. Public ChatGPT directory listing and multi-user OAuth onboarding remain separate from public source availability.
- Process diagnostic: attribute the historical timeout-fixture subprocess warning using owned-process and teardown observations before concluding whether cleanup needs another change.

## Reproducibility and data handling

Tests used separate source and fixture directories and did not replace the existing TOC Studio. ChatGPT's model/provider overrides were invocation-local. The test prompt restricted actions to synthetic fixtures; enabled commands still ran with the worker account permissions. Its worker was stopped after evidence capture. No subscription was cancelled. Source excludes credentials, private state, virtual environments, browser profiles, user output logs and personal TOC content.

Hosted CI evidence is recorded by exact source revision above. Installation remains an alpha development deployment; each required replacement workflow needs its own acceptance evidence.

## Historical local installation

RDC was installed into a separate iMac development directory. A default local owner profile and running worker were created, with a dedicated working root, command execution enabled, per-operation owner review, and native desktop input disabled. Codex and Claude Desktop received a new `rdc connect` entry; existing client settings were backed up and preserved. No application was restarted. The owner dashboard was connected and used in the actual local Chrome browser to start a separate session, navigate a synthetic page, fill a field, click a greeting button, and verify the rendered result. The live tab was retained for owner inspection.

That browser dashboard remains an administrator and diagnostic interface. It does not satisfy the primary requirement for a preview inside the AI application. The portable embedded resource supplies that interface for compatible hosts. The a5 activation, matching gateway and plugin 1.0.6 are recorded above; production UI acceptance remains pending. The worker and relay remain development processes without login-service registration, so a machine restart requires starting them again.
