# RDC embedded preview

## User intent

The primary live preview belongs inside ChatGPT, Codex, Claude, or another
compatible AI host. The owner explicitly corrected the separate dashboard
approach. The view should expand, move where the host permits, resize, hide,
and reopen while the worker continues operating independently.

## Approaches and implementation choice

1. A portable MCP App uses the host's sandbox and MCP connection. This is the
   chosen implementation because it supports in-conversation UI without
   launching another program. Use the official client SDK and negotiated modes.
2. Host extensions supplement the standard where documented, including ChatGPT
   conversation panels and optional host dismissal. They cannot establish
   support in a host that does not render MCP Apps.
3. Keep the existing owner dashboard for administration and fallback. It is no
   longer the primary preview. An iframe of that dashboard would expose the
   wrong authority and loopback networking assumptions, so it is not embedded.

These technical choices are the builder's decisions under the existing build
authorization. They do not imply the user approved a particular host limitation.

## Architecture and lifecycle

`rdc serve` owns sessions and durable jobs. `rdc connect` forwards tools AND UI
resources to that same worker. `rdc_preview_open` selects an existing browser
session and returns view state; it never starts or closes a browser.
`rdc_preview_frame` returns a current screenshot and cursor through MCP.

One self-contained HTML resource bundles the official MCP Apps client and RDC
brand asset. No localhost fetch, CDN, owner token, or external iframe is needed.
The view polls one frame at a time, backs off on failure, and stops fetching
while hidden or torn down. Hiding, resizing, display-mode changes, and host
teardown must never close a browser, cancel a job, or stop the daemon.
Reopening with the same device/session reconnects to that session. Browser
survival still depends on the daemon remaining alive.

Inline, fullscreen, and picture-in-picture are requested only where offered.
The host decides the actual mode and outer position. An optional movable and
resizable panel operates only inside the allocated fullscreen canvas. The UI
must not claim to move the host's own window. Close/hide is a viewer operation;
pause input and cancel job remain distinct worker operations.

## Authority and compatibility

The embedded surface receives only agent permissions. It cannot approve its
own requests, change grants, read owner credentials, or silently bypass review.
App-only tool visibility is presentation metadata, never an authorization
boundary. Existing owner administration remains separately authenticated.

Use `_meta.ui.resourceUri`, `text/html;profile=mcp-app`, resources/list and
resources/read, and declared UI extension capabilities. Preserve these through
the stdio proxy. Include concise text results for clients without UI support.
Actual rendered support in each shipping host must be tested independently.
The current ChatGPT conversation cannot acquire a new connector merely because
an MCP server or skill was installed on the iMac.

## Acceptance

- Resource metadata and CSP survive real MCP HTTP/stdio forwarding.
- Preview open/frame calls are read-only and preserve review/pause state.
- The iframe initializes against the official protocol and receives real frames.
- Expand/float honor host capability and returned mode, including denial.
- Drag/resize stay within the host's allocated canvas and are keyboard usable.
- Hide, teardown, and client disconnect leave a real job/browser alive.
- Reopen displays the same session, stops duplicate timers, and resumes frames.
- Narrow layouts remain usable. The generated RDC logo ships with the app.
- Results distinguish fixture-host tests from actual ChatGPT/Claude rendering.
