# RDC: independent agent workspaces

## Intent

The owner wants a free, public, open-source successor to TOC Commander that removes the mandatory commercial remote relay, works with ChatGPT and Claude, and carries out complete workflows while the owner continues working. The agent needs its own browser sessions, input stream, live preview, durable terminal jobs, and a path to full authorized desktop and mobile control. Safari matters as much as Chromium browsers. Windows, macOS, Linux, iOS, and Android must be represented honestly.

## Existing evidence

The existing TOC Commander on the iMac passed real ChatGPT/Codex file and isolated Chromium workflows. Its `edit_block` discovery schema uses `file_path` while a separate validator expects `path`; that contract is broken. Its approvals and browser sessions are process-local. Its custom loopback HTTP gateway is not a public MCP endpoint. It contains iMac paths and private state that must never enter a public repository.

Remote Desktop Commander already has asynchronous calls. Its three second wait is a synchronous response window, not a process lifetime limit. Its free local MCP implementation is MIT; the hosted remote implementation is proprietary. The opportunity is an original open implementation with durable job identity, predictable output, independent workspaces, and transparent operating constraints, verified against real workflows.

## Approaches considered

1. Extend the current TOC fork in place. This preserves integrations but carries machine-specific assumptions and private state into the portability work.
2. Build an original portable core with a documented TOC migration path. This creates a clean public boundary and lets existing TOC continue operating during testing.
3. Build a hosted remote service first. This introduces hosting and authentication operations before proving the worker and preview.

The builder selected approach 2 under the user's authorization to build and improve the harness. This choice is not represented as a separate user-approved design decision. Python 3.11+, SQLite, an official MCP SDK, and optional platform adapters keep the core small and portable. No proprietary code or assets are copied.

## Product behavior

- Each RDC installation has a persistent device identity.
- The default web work area is a dedicated headless browser context. Its tabs, cookies, input, and pointer indicator are separate from the owner's browser. Browser work has a live image preview and a structured observation of controls.
- Terminal commands are durable asynchronous jobs with retained output, explicit byte offsets, timeouts, cancellation, and retry keys. Disconnecting a chat does not cancel a job.
- Native GUI control operates on either an explicitly enabled shared desktop or an isolated desktop/VM. A second normal desktop window cannot provide an independent OS cursor. The UI must show which mode is active.
- Owner controls pause agent browser/native input and hand control to the preview. A pause is an input barrier, not a promise to freeze every subprocess or network request.
- Browser automation uses Playwright for independent Chromium/Firefox/WebKit workspaces and W3C WebDriver for actual Safari, Chrome, Edge, Firefox, and configured Appium sessions. WebKit must never be labeled Safari.
- A responsive dashboard can be used from phones. Controlling the phone itself requires an authorized Android or iOS automation adapter, separate from dashboard access.
- Full host mode enables the permissions of the worker account, not elevation past OS security. Shell execution is not confined by file-root checks. Use a container or VM for containment.
- No telemetry, mandatory subscription, mandatory relay, or model API key is required by RDC itself. AI provider, host, and connectivity costs remain independent.

## First release scope

Implement a real portable filesystem and job engine, owner review, MCP stdio and authenticated HTTP, live dashboard, isolated browser control, WebDriver, native desktop and Android adapter routes, installation/client examples, and a Linux isolated desktop worker definition. Test local core, browser contracts, HTTP authentication, disconnect recovery, and the iMac's actual ChatGPT integration. Hardware and clients unavailable for testing must be marked untested, not supported by assertion.

Public ChatGPT web OAuth onboarding, automatic VM provisioning on every desktop OS, native iOS provisioning, distribution signing, and a public hosted relay are subsequent integration work. Static bearer HTTP alone does not establish ChatGPT web compatibility. The first release remains explicitly an alpha until those gaps and the hardware matrix are resolved.

## Module and interface contract

`rdc/config.py`: `Settings(state_dir: Path, roots: list[Path], access_mode='workspace', approval_mode='review', allow_exec=False, desktop_mode='disabled', browser_backend='playwright', webdriver_url=None, webdriver_capabilities=None, adb_serial=None, max_output_bytes=10485760, max_read_bytes=262144, job_timeout=3600, allowed_origins=[])`. JSON load/save owner configuration; reject unknown and invalid fields. `public()` excludes tokens and returns effective capabilities.

`rdc/errors.py`: `RDCError(code, message, details=None)`.

`rdc/engine.py`: `Engine(settings)`; `catalog()` returns standard MCP tool dictionaries; `call(name, arguments)` returns `{ok: bool, ...}` and catches expected errors; `status()` returns device identity, settings, jobs, approvals and browser/desktop status; `decide(request_id, approve)` is owner-only, never an MCP tool; `pause(paused: bool)` sets the persisted agent input barrier. `close()` releases browser resources, not detached jobs. `snapshot(session_id=None)` returns `{mime_type, data: base64, ...}`. `owner_call(name,args)` bypasses review and pause for owner dashboard takeover but retains validation and path policy.

`rdc/store.py`: SQLite WAL store for identity, approvals, idempotency, jobs, input queue, and state. All IDs are random UUIDs, never plain PIDs. Permission-sensitive state is private to the worker account. No remote tool can change its own permission grants.

`rdc/files.py`: workspace path validation, file read/list/search/bulk read, atomic write and exact-block edit with hash preconditions. Use `file_path` consistently. Reject symlink traversal in restricted roots. Full host explicitly opts out of workspace restrictions, but protects RDC private state from file tools.

`rdc/jobs.py` and `rdc/worker.py`: detached worker per job. Request creates durable record before launch. Repeated key with same arguments returns original job; different arguments conflict. Worker captures merged stdout/stderr to a bounded on-disk log, keeps draining after limit, records exit status. Input queue allows interactive stdin. Worker polls cancellation without arbitrary-PID kill. POSIX process group termination; Windows process tree best effort explicitly documented. Heartbeat permits honest interrupted status after worker loss.

`rdc/adapters.py`: `Adapters(settings)` with `catalog() -> list[dict]`, `call(name,args) -> dict` (raises RDCError), `status() -> dict`, `snapshot(session_id=None) -> dict`, `close()`. Names begin `rdc_browser_`, `rdc_desktop_`, `rdc_android_`. Each descriptor includes `x-rdc-mutating: bool`. Browser actions take observation-bound handles; no automatic retry of uncertain mutation. Real browser state persists for server lifetime; reconnect can recover jobs but not claim browser restoration after daemon exit. The module owns adapter locks and tool schemas. Agent control is subject to engine approval/pause; owner preview control shares the adapter path.

`rdc/server.py`: official SDK transport, schema discovery, thread-offloaded core invocation. `create_app(engine, agent_token, owner_token)` builds authenticated HTTP MCP at `/mcp` and dashboard at `/`. `/api/status` GET, `/api/call` POST `{name,arguments}` owner only, `/api/decision` POST `{request_id,approve}` owner only, `/api/pause` POST `{paused}`, `/api/preview?session_id=...` GET image, `/api/jobs/{id}/output?offset=0&limit=...` GET. Agent token cannot enter owner routes. Constant-time token checks, same-origin checks, bounded JSON, loopback binding by default. GET UI is public shell; data require owner bearer. Do not embed tokens in URLs or HTML.

`rdc/cli.py`, `__main__.py`: `init`, `stdio`, `serve`, `doctor`, `owner-token`. Owner initialization grants capabilities explicitly. `serve --open` is owner-selected preview launch. Secrets generated privately, never written into client examples. Direct HTTP clients use agent token; local stdio trusts the host process boundary.

`rdc/web/`: responsive static dashboard with access-token input, connection indicator, active workspace/preview, separate input/cursor display, observation controls, jobs/logs, approvals, pause and owner takeover. No third-party assets or CDN. Adaptive polling stops when hidden, backs off on errors, and avoids fetching concurrent screenshots. Show empty/setup/error states truthfully. Keyboard/touch accessibility.

## Acceptance gates

1. A schema-correct edit using `file_path` succeeds; conflicting hash causes no write.
2. Job start survives transport disconnect; a new engine instance can retrieve exact output and exit status.
3. Retrying a start key creates one job; changed arguments conflict.
4. A quickly failing process retains stderr and exit code. Repeating an explicit output offset is deterministic.
5. Worker cancellation and timeout reach terminal states; output limits bound disk use.
6. Agent cannot approve its own review, access owner API, change grants, or bypass a paused input gate with a new client.
7. Real browser fixture fills and clicks, observes changed text, creates a valid screenshot, and closes. Stale references are rejected.
8. Preview displays a real workspace, pauses and owner controls act on that same session, and the user's ordinary desktop cursor is not used by headless browser work.
9. Protocol/client claims are tied to executed tests. Untested Safari, Windows, iPhone, Android, and Claude are clearly labeled until actual tests run.
10. Repository contains no existing user tokens, private TOC content, machine-specific paths in public examples, or proprietary assets.

## Performance measurements

Record startup time, tool discovery bytes, file call median/p95, durable job admission/finish timing, browser observe/action/screenshot timing, and number of AI round trips per fixture. Compare equivalent workflows when feasible. No unmeasured claim that RDC is faster than Codex or Desktop Commander. Structured observations, batched independent reads, warm browser sessions, background jobs, and adaptive preview polling reduce avoidable overhead.

## Sources

- https://desktopcommander.app/pricing/
- https://github.com/desktop-commander/remote-desktop-commander
- https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/main/SECURITY.md
- https://py.sdk.modelcontextprotocol.io/get-started/installation/
- https://developer.apple.com/documentation/safari-developer-tools/webdriver.md
- https://playwright.dev/docs/browsers
- https://www.w3.org/TR/webdriver1/
- https://developer.android.com/tools/adb
- https://appium.github.io/appium-xcuitest-driver/latest/getting-started/system-requirements/

