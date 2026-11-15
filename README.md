# RDC (Remote Desktop Commander)

<img src="rdc/assets/rdc-logo.png" alt="RDC logo" width="96">

**Independent agent workspaces with a live preview inside your AI app.**

RDC (Remote Desktop Commander) is an independent TOC Ministries project: a free, MIT-licensed local worker for self-hosted use with compatible MCP clients. It provides scoped file operations, durable terminal jobs, independent browser sessions, an embedded live preview in hosts that support MCP Apps, and owner-controlled approvals, pause, and saved-password consent. Optional native desktop and Android ADB tools require owner configuration; Android, iPhone, and iPad Appium adapters also require a prepared device or simulator, UiAutomator2 or XCUITest, and a compatible driver host. Preview modes depend on the AI host, and native mobile input uses the selected device's screen. The owner dashboard manages approvals, permissions, and takeover.

The local worker requires no RDC account, subscription, hosted service, telemetry, or model API key. Optional gateway hosting and your AI provider have their own terms and costs. This repository contains no Desktop Commander proprietary service code or assets.

**Version: 0.1.0a3 (alpha).** This release adds owner-configured Android, iPhone and iPad native sessions, touch controls, and mobile previews. It also corrects Windows-specific test fixture assumptions. Read [verification](docs/VERIFICATION.md), the [audit](docs/AUDIT-2026-11-15.md), and [mobile setup and limits](docs/MOBILE.md) for the exact executed evidence. Physical phones/tablets, native mobile credential providers, production AI-host rendering, a native desktop live viewer, automatically provisioned Mac/Windows VMs, and public ChatGPT web OAuth onboarding still require implementation or qualification. [Platform details](docs/platforms.md).

## What works

- A self-contained MCP Apps preview with the original RDC logo, live screenshots and cursor, session selection, host-negotiated expansion/float, and hide/reopen. In fullscreen, its panel can move and resize within the area allocated by the AI host. Hosts control outer positioning and supported display modes.
- A shared HTTP worker and a stdio bridge let ChatGPT/Codex, Claude configurations, and the owner preview use the same browser sessions. Disconnecting the bridge leaves the worker and its sessions running.
- Independent Playwright Chromium, Firefox, and WebKit contexts. Actual Safari uses configured W3C WebDriver. WebKit is not Safari.
- Browser text and control observations, fill/click, viewport pointer and keyboard input, navigation, image capture, and session cleanup. Screenshots use MCP image blocks instead of duplicating base64 into model text.
- Durable command jobs with stable IDs, persistent exit status, retained stdout/stderr, deterministic byte offsets, interactive stdin, timeout, cancellation, and duplicate-start prevention through retry keys.
- Bounded file listing/search, independent bulk reads, atomic UTF-8 writes, exact edits, hash preconditions, and consistent `file_path` arguments.
- Persisted owner review and a pause gate. An agent token cannot call owner API routes. Grants are configured by the owner, outside the MCP catalog.
- A private credential broker with opaque saved-password aliases, owner Allow Once / Always Allow for this site / Deny, and revocation. Passwords go through a private browser fill path; native Keychain or device authentication remains under the operating system's control. [Setup and limits](docs/CREDENTIALS.md).
- An optional outbound device relay for the companion private ChatGPT Sites gateway. It retains request/result state, verifies exact request hashes, and recovers pending results without automatically replaying uncertain actions.
- Optional PyAutoGUI desktop and authorized Android ADB routes, including Android swipe, long press and explicit activity launch. These require OS permissions and device setup. A native screenshot includes the scaling between captured image and logical input coordinates.
- Owner-configured Appium sessions for Android through UiAutomator2 and iPhone/iPad through XCUITest. Observe native controls, tap, fill nonsecure fields, swipe, and view privacy-checked screenshots in the existing preview. Physical-device input uses that device's screen; use a separate emulator, simulator or dedicated device for independent work. See [mobile setup](docs/MOBILE.md).

## Quick start

Use Python 3.11 or newer. From this source checkout:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install '.[browser]'
.venv/bin/python -m playwright install chromium
.venv/bin/rdc init --root /absolute/path/to/your/workspace
.venv/bin/rdc serve
```

On Windows use `.venv\Scripts\python.exe` and `.venv\Scripts\rdc.exe`, and a Windows path for `--root`. `python` can replace `python3` where appropriate. Firefox and WebKit browser runtimes are installed separately with `python -m playwright install firefox webkit`.

Initialization defaults to owner review, file operations within the working root, no shell execution, and native desktop input disabled. To grant terminal execution at initialization, add `--allow-exec`. To explicitly grant file access across the host, add `--access-mode full-host`. The account's ordinary OS permissions still apply. To permit agent mutations without per-operation review on a trusted dedicated worker, add `--approval-mode trusted`. Existing initialization is preserved; grants can be edited in its private `config.json` while the service is stopped.

Connect your AI client as described below and ask it to open the RDC preview. For owner administration, open `http://127.0.0.1:8765/`. Run `rdc owner-token` in your own terminal and paste that credential into the administration page. The page retains it only in memory. It is separate from `agent-token`; do not send either credential to an AI conversation. `rdc doctor` reports dependencies and selected capabilities without printing tokens.

Default state directory:

| System | Directory |
|---|---|
| macOS | `~/Library/Application Support/RDC` |
| Windows | `%LOCALAPPDATA%\RDC` |
| Linux | `$XDG_STATE_HOME/rdc` or `~/.local/state/rdc` |

Every command accepts `--state-dir` for a separate worker/profile. Token files are restricted on POSIX. Windows relies on the account profile and deployment ACLs; dedicated Windows ACL hardening remains a release qualification item.

## Connect AI clients to the shared preview

Start `rdc serve` once. Then configure your client to run:

```sh
/absolute/path/to/.venv/bin/rdc connect --url http://127.0.0.1:8765/mcp
```

Add the matching `--state-dir` if the worker uses a custom state directory. `connect` reads the private agent credential locally and forwards tools and UI resources through the official MCP transport. It never receives the owner credential and never closes the worker on disconnect. A reconnected preview attaches to the same active browser session.

Use the ready examples for [Codex](examples/client-codex.toml), [Claude Desktop](examples/client-claude-desktop.json), or [direct HTTP](examples/client-http.py). They contain placeholders for your installation paths. A model can use RDC when its host supports the relevant MCP transport. Client permissions, tool approvals, image support, and context limits still apply.

`rdc stdio` also runs a standalone worker inside one client's process. Its browser sessions end when that process exits and are separate from a separately launched dashboard. Choose `connect` when you want the shared preview.

### Private ChatGPT web gateway

The companion [RDC ChatGPT gateway](cloud-gateway/README.md) supplies a private Sites MCP route. A device-side `rdc relay` process makes outbound HTTPS connections to that gateway and invokes the existing loopback worker with its agent credential. This route keeps the worker's listener and owner administration local. It requires a private deployed Site, its supported ChatGPT connection, and an owner-created pairing configuration. The public multiuser OAuth onboarding flow remains unfinished. [Installation details](docs/PLUGIN-INSTALL.md#chatgpt-web-and-remote-clients).

Run the relay alongside the worker, selecting its matching private state:

```sh
rdc relay --config /absolute/path/to/private/relay-config.json
```

The local catalog contains **51 tools**. The gateway adds `rdc_connection_status` and `rdc_operation_status`, for **53 tools** when its bundled catalog matches this version. Gateway source deployment and actual rendering inside ChatGPT are separate acceptance checks. An embedded component, a registered route, or a logo asset alone does not establish that the production AI host renders RDC's preview or tool identity.

Native RDC tools are connected and functional in ChatGPT. Connection status, worker status and preview open succeeded; identical cloud request-ID reuse returned the same pending owner approval ID without granting approval. The private App-backed plugin 1.0.2 was saved and read back, the worker restart confirmed 0.1.0a2 with unchanged configuration, and the private gateway deployment succeeded. The preview-open check had no active browser sessions. Rendering of the embedded component and an owner-approved live cloud browser workflow remain unverified. See the [audit evidence](docs/AUDIT-2026-11-15.md#current-chatgpt-connection).

The local stdio package still works without a relay. Hosted clients need a reachable authenticated route; their `127.0.0.1` does not point to the user's computer. Direct HTTP clients that support the worker's bearer authentication can use an appropriately secured endpoint.

### Preview window behavior

`rdc_preview_open` opens the embedded component in an MCP Apps-capable host. Pass an existing `session_id` to reopen that specific session. It never creates or cancels a browser session. The worker must stay running. Inline screenshots and ordinary tool results remain available to clients without embedded UI.

| Control | Effect on the view | Effect on work |
|---|---|---|
| Expand / return inline | Requests a mode supported by the host | Session and jobs continue |
| Float | Requests picture-in-picture when the host offers it | Session and jobs continue |
| Move / resize panel | Adjusts the panel within the allocated fullscreen canvas | Browser viewport and task remain unchanged |
| Hide / reopen | Stops frame polling, then reattaches to the same session | No browser close or job cancellation |
| Dismiss | Requests removal of the view from the host | Worker remains running |

Moving the host's outer window is controlled by the AI application. Standard MCP alone does not guarantee any embedded rendering. See [host contracts](docs/EMBEDDED-HOSTS.md) and [plugin installation](docs/PLUGIN-INSTALL.md). ChatGPT and Claude document MCP Apps support; actual RDC rendering in each production host is a separate acceptance test. Codex's built-in preview does not establish third-party UI support.

The committed UI bundle runs without Node, a CDN, or direct network access from the iframe. To rebuild after editing `rdc/embedded/src`, run `npm ci` and `npm run build` inside `rdc/embedded`. The pinned build preserves bundled dependency licenses.

On the private cloud route, the preview can recover a pending open, session refresh or frame by its existing operation ID. Hiding and reopening retains that recovery identity. If an ended session is reported through pending-operation recovery, the viewer clears that selection, fetches one available-session list and waits for an explicit choice. A newer selection made during recovery is preserved. A bounded recovery deadline eventually asks for a fresh observation; it never silently redispatches an uncertain operation.

The footer identifies pending action reviews and directs the owner to RDC's owner panel on the paired computer. Job and review counts are labeled as the last status check and update when Sessions is refreshed. The embedded component has no owner credential or approval controls. Session labels use the actual browser name where available.

## Work without taking over the owner's desktop

| Task | Execution area | Interference |
|---|---|---|
| Browser automation | Dedicated headless browser contexts | Separate browser input and profiles; shares CPU/RAM/network |
| Terminal jobs | Detached worker processes | No pointer use; commands may affect files/apps according to grants |
| Native apps with `shared` mode | Current desktop | Uses that desktop's cursor/focus |
| Native apps with `isolated` mode | Owner-provisioned separate desktop/display/VM | Independent only when that environment is actually separate |
| Phone dashboard | A mobile browser viewing the worker | Does not grant control of the phone OS |

A second window alone cannot create a second OS cursor. RDC's `isolated` setting describes the environment the owner must provision; it does not create a VM. The [optional Linux container recipe](deploy/README.md) provides a private Xvfb display, but its image and native input path still need deployment qualification. Containers share a host kernel; use a VM where that distinction matters.

The owner takeover control pauses new agent mutations, then directs preview clicks to the browser worker. Actions already admitted may finish. Existing background jobs keep running and can be cancelled individually. Human activity, native app services, and other clients outside RDC are not frozen.

## Operating contracts

File read offsets and command output offsets are **bytes**. Zero always means the beginning. Text decoding uses UTF-8 with replacement for split or invalid sequences; retrieve source files directly for binary fidelity. File writes are capped by the configured text limit. Larger/binary transformations can use authorized jobs. Hash checks coordinate RDC writers and detect changed content; they do not create a filesystem transaction with unrelated applications.

Command `argv` is passed without shell expansion. Use an explicit shell when a command requires shell syntax. Start returns immediately with a durable job ID. Save that ID and retry key. Reusing a key with the same normalized command retrieves the original job; changing arguments conflicts. A dropped tool response never justifies blindly replaying a mutation. The bridge preserves complete protocol rejections and remains usable for later calls. A timeout or lost connection still latches an uncertain failure and requires inspection before reconnecting.

Interactive stdin delivery accounts for partial pipe writes before marking queued input delivered. A stalled or broken input stream records an incomplete-input failure, even when the child exits zero; partially delivered input is never replayed automatically. Inspect both job status and its error field when recovering a command.

Logs merge stdout/stderr in arrival order and are capped at 10 MiB per job by default. The worker keeps draining excess output and records truncation. Metadata and retained output remain in the state directory until the owner removes them; there is no automatic retention cleanup or global disk quota in this alpha. A lost worker heartbeat after two minutes is marked interrupted, never assumed completed. A machine restart may terminate running processes. Browser sessions are memory-resident and end with the daemon.

Owner review lasts 15 minutes and persists across a client restart. A request already executing at daemon failure requires investigation; it is not automatically replayed. The dashboard displays the exact action being approved. Read files again after a hash conflict and observe the page again after a stale handle.

Cloud mutations require a stable `_rdc_request_id`. Keep that ID and the original arguments after a dropped response. A pending gateway response supplies an `operation_id`; call `rdc_operation_status` with it to retrieve the original result without issuing the action again. Core job retry keys and credential `idempotency_key` values remain separate from this transport request ID. The relay journals admission before execution and retains results before upload. An execution whose outcome is unknown after a crash is reported as uncertain and requires inspection.

If the authenticated gateway no longer retains an operation's identity, the relay records its result as `undeliverable` locally and continues with unrelated work. That state never claims a successful upload or permits execution again. The original request/result remain subject to the local payload retention bound; an identity record remains after payload pruning. Inspect the worker before another attempt, and preserve the relay journal.

Browser observations export at most 150 control handles and 24,000 characters of page text. They report `text_truncated`, `controls_truncated`, `control_scan_truncated` and per-control name/value truncation. Control selection uses a 5,000-element and 300-candidate scan budget; unused or failed handles are released. A truncated result may require another observation path or a narrower page state.

If WebDriver creates a session but later setup fails, RDC attempts to close that exact session. Unconfirmed cleanup leaves a discoverable session marked `cleanup_required`; close that session explicitly before starting a replacement. It accepts cleanup only. This recovery route still requires qualification on actual Safari and other configured drivers.

Empty relay polls gradually back off from 250 milliseconds to five seconds, using the longer of the gateway's bounded poll interval and the local delay. Receiving work immediately resets the local delay and the pump checks for more work after returning its result. At steady idle, each empty response is followed by a five-second delay; server-side long polling can reduce the request rate further. A newly queued task after a quiet period may incur up to five seconds of additional pickup delay, plus network time. Heartbeats during execution and operation-expiry checks remain separate.

## Saved-password permissions

The owner enrolls an existing native credential in the owner administration page by supplying a safe alias, exact HTTPS origin and native item locator. macOS enrollment now requires the specific classic **Keychain file**, server and account. The private version-2 locator binds one HTTPS origin; older server/account-only aliases require removal and re-enrollment before filling. The form never asks for a password or enumerates the vault. It generates an opaque ID and writes the private `credential-locators.json`; advanced owners may edit that mapping privately. Enrollment does not authorize a fill or verify that the native entry exists. With no mapping file, this feature is simply unconfigured. The agent can list safe aliases, request a fill into a fresh observed password field, and inspect request status. It cannot enroll or remove credentials, approve a request, create a persistent grant, or revoke a grant through MCP.

The existing owner administration page automatically presents pending requests. **Allow Once** authorizes one attempt. **Always Allow for this site** binds the credential, origin, device and mapping until revoked. **Later** dismisses the prompt while work continues. The owner can revoke a grant or remove an alias there. The broker checks consent and pause again before native lookup and before input, and rechecks the actual browser origin, document and password-field type. The initial feature fills only the password field; it does not click Sign in. Revocation blocks future use and does not sign out an already authenticated website session.

The macOS helper opens only the selected classic Keychain, requires one matching internet-password item, checks its server/account/HTTPS/port metadata, and reads the password from that same retained item reference. Missing, ambiguous or mismatched items fail before a password read. Windows uses a configured generic Credential Manager target. These routes do not expose arbitrary Apple Passwords/iCloud or Chrome/Edge vault access. Browser-provider autofill and mobile credential adapters remain future work. The automated tests use synthetic credentials and native-API fixtures; actual native vault access still requires platform qualification. See [credential setup, APIs and security boundaries](docs/CREDENTIALS.md).

Observations keep broker-filled inputs redacted after a page's Show Password control changes their type. Playwright capture independently checks document sensitivity and masks every input in a document that received a broker credential, including other visible form inputs. Fresh nonsensitive documents return to normal password-field and private-marker masking. WebDriver screenshots fail closed for credential-sensitive documents until fresh nonsensitive navigation. Probe or masking failures return no image. The authorized website can still read its form values and copy them elsewhere. See the [privacy limits](docs/CREDENTIALS.md#security-and-practical-limits).

## Permissions and security

Read [SECURITY.md](SECURITY.md) before exposing a worker outside your computer. File roots, schemas, review, and separate HTTP credentials prevent common mistakes. **An authorized shell runs as the worker OS account and can access that account's files, credentials, and configuration. These application checks are not an OS sandbox or a defense against that fully authorized account.** Separate identities, containers, or VMs supply stronger boundaries.

The service binds to loopback. Remote use needs a secured tunnel or authenticated HTTPS gateway, correct `allowed_origins`, and independent access controls. No unauthenticated public listener is provided. Browsing has the worker's network access, including local networks. Website text is untrusted task data, not authority to change grants, reveal secrets, or issue unrelated commands.

## Test and measure

For a guided run inside a real AI host, follow [client acceptance](docs/ACCEPTANCE.md). It covers the actual connection, independent browser, view lifecycle, durable jobs, credential consent and platform evidence.

```sh
.venv/bin/python -m pip install '.[browser,test]'
.venv/bin/python -m playwright install chromium
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/benchmark.py --browser
```

Use the installed virtual environment. The managed system Python may contain an older incompatible MCP SDK. CI defines Linux, macOS, and Windows runs; a workflow file is not evidence that those runs have happened. Tests report unavailable browser runtimes as skips. macOS and Windows hardware/permission checks are separate from a fake WebDriver protocol test.

Benchmarks report local worker latency and call counts. They do not establish that RDC is faster than Codex or Desktop Commander. Comparable task success, recovery, total round trips, and end-to-end time are the intended performance measures.

## Project and contribution

See [design](docs/superpowers/specs/2026-11-15-rdc-design.md), [implementation plan](docs/superpowers/plans/2026-11-15-rdc-plan.md), [comparison](docs/COMPARISON.md), [TOC migration](docs/TOC-MIGRATION.md), [release verification](docs/VERIFICATION.md), and the [current audit and priorities](docs/AUDIT-2026-11-15.md). Contributions should include a reproducer and actual platform evidence. Use synthetic fixtures rather than personal credentials or production data.

Priority next work: public multiuser ChatGPT OAuth onboarding and production host acceptance, native desktop streaming and input handoff, browser tabs/popups/frames/download-upload workflows, verified Safari and Windows runs, native credential-provider qualification, mobile device qualification, and packaging/signing. See the platform matrix for precisely what is implemented.

