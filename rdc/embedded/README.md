# Embedded RDC preview

`preview.html` is the self-contained MCP Apps resource served by RDC. It includes
the official `@modelcontextprotocol/ext-apps` client, CSS, and the RDC logo. The
worker does not need Node, an asset server, or a CDN to serve it.

## Rebuild

With Node 20 or newer installed, run these commands in this directory:

```sh
npm ci --ignore-scripts
npm run build
```

The pinned dependency graph is in `package-lock.json`. The build retains bundled
upstream license texts in `THIRD_PARTY_NOTICES.txt`. Keep both generated files in
source distributions. The project logo must exist at `../assets/rdc-logo.png`.

## Host contract

The view uses the official SDK's parent-bound `PostMessageTransport` and
`ui/initialize` handshake. The host must provide `serverTools` and support the
registered MCP Apps resource. It reads only `rdc_preview_open` and
`rdc_preview_frame`, plus `rdc_operation_status` when the cloud gateway returns a
pending operation. The production view makes no direct network requests.

Expand, Inline, and Float controls follow the host's advertised display modes.
The view uses the mode returned by the host, including when a request is declined.
Moving and resizing inside the expanded RDC canvas stays within the allocated
canvas. Positioning a floating window outside that canvas belongs to the host.
Short host allocations keep the panel bounded and make its contents scrollable.

Hide stops frame polling and preserves the selected session in this view. Reopen
reconnects to that same session. Dismiss sends the standard host teardown request;
host teardown clears timers and image data without stopping the worker, browser,
or jobs. There is no worker shutdown call in the view.

On selection, hide, and dismissal, a host advertising `updateModelContext`
receives the selected device and session IDs so the agent can reopen the same
session explicitly. The hidden card also exposes the full selectable session ID.
A fresh `rdc_preview_open` invocation without an ID can select the first available
session; portable exact-session reopening passes the retained ID. The view has no
account credential and uses no local or session storage.

Frame reads are single-flight, every 1.5 seconds while visible, with bounded
backoff on errors. Hidden documents and hidden views stop polling. Session and
device mismatches are rejected before rendering. Screenshots are accepted only as
bounded PNG, JPEG, or WebP MCP image blocks.

Cloud operations that are still pending retain their original operation ID. The
view polls that operation's status instead of dispatching another preview read.
Hiding suspends recovery; reopening resumes the same pending operation. A
two-minute recovery deadline stops automatic polling and offers a manual request
for a new observation. The initial host tool result is awaited rather than
duplicating an open while the original invocation is still active.

## Verification

`tests/test_embedded_ui.py` runs the real SDK inside a sandboxed iframe with a
clearly labeled protocol fixture host. It tests mode negotiation and refusal,
movement and resizing, hide and teardown, selected-session recovery, mobile
layout, parent-source validation, and polling limits. One fixture forwards the
two read-only tools to a real RDC engine, Playwright browser, and durable job.
These tests do not establish that a particular ChatGPT, Codex, or Claude release
has enabled the resource for a user's connector.
