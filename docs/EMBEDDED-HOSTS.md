# Embedded preview host contracts

Research checked against primary documentation on 2026-11-15. Documented host capabilities and executed RDC checks are separate evidence. The private ChatGPT tool connection is verified. An owner-provided alpha.7 screenshot confirms production mounting and shows the expired bootstrap recovery defect addressed in alpha.8. See [release verification](VERIFICATION.md).

## Product requirement

RDC opens one read-only live surface for the exact browser or device session used by the current task, with the agent cursor when available. The host owns its placement and controls. Viewer dismissal never stops a browser or job. File and command work use their own tool results. Owner administration is a separate workflow and never opens as the preview.

## Host compatibility

| Host | Documented presentation | Window controls and limits | RDC verification status |
| --- | --- | --- | --- |
| ChatGPT web and desktop | MCP Apps component inside the conversation; inline and fullscreen presentation; the current Extensions specification explicitly excludes picture-in-picture. Plugin extensions add conversation panels and sidebar entry points. [1][2][3] | Request an advertised mode and standard teardown. The host controls placement, dismissal and the surrounding window. Exact availability depends on the user's host and account. | Native tool calls and alpha.7 embedded mounting are verified. The owner screenshot exposed an expired-result recovery failure. Alpha.8 native layout, production behavior and further host-specific controls have separate qualification records. |
| Codex | Official quickstart explicitly documents MCP tools for ChatGPT and Codex, and optional UI in ChatGPT. [4] | Do not infer third-party MCP Apps rendering from Codex's built-in browser preview. No public third-party window-control contract was established in this research. | The older connected RDC cloud view rendered frames and cursor in Codex desktop on November 15, 2026. The v5 development build still needs rollout and separate host qualification. |
| Claude web and desktop | Inline, side panel, and full screen. Panel and full-site functionality are rolling out to the new Claude experience. [5][6] | `fullscreen` represents both side panel and full screen. The host offers the panel resize edge. Supported modes must be read from host context. | Product support documented; actual RDC embedded acceptance still required. |
| Claude iOS and Android | Interactive connectors are available; the new side panel, full-site view, and navigation entry points are not yet available on mobile. [5] | Use responsive layout and the modes actually advertised. | Unverified on hardware. |
| Claude Code | Tool execution as a text client; the official quickstart states that Claude Code does not render the MCP App UI. [7] | Preserve useful text/image tool responses. | MCP compatibility is distinct from UI rendering. |
| Other AI clients | An MCP Apps-compliant host can render the portable view. Standard MCP alone does not establish UI support. [8] | Host-negotiated capabilities decide presentation. | Verify each client before listing it as supported. |

## Portable preview contract

Use one predeclared `ui://` resource with MIME type `text/html;profile=mcp-app`. Link an explicit open-preview tool through `_meta.ui.resourceUri`. Keep ordinary action tools separate so actions do not repeatedly create new viewers. OpenAI recommends this separation. Return meaningful text alongside structured results. [1]

Initialize through `ui/initialize`, advertise `availableDisplayModes`, then consume host capabilities and context. Request a mode using `ui/request-display-mode`; always use the returned mode, which can differ from the request. Process partial `ui/notifications/host-context-changed` updates and `containerDimensions`. Send `ui/notifications/size-changed` when intrinsic content size changes. The standard has no API for arbitrary window X/Y placement. [8]

Current MCP Apps server negotiation uses:

```json
{
  "capabilities": {
    "extensions": {
      "io.modelcontextprotocol/ui": {
        "mimeTypes": ["text/html;profile=mcp-app"]
      }
    }
  }
}
```

Negotiate capability rather than assuming it from a product name. [8]

### Current task source and presentation

The current resource is `ui://rdc/preview-v7.html`; v1 through v6 remain readable for existing installations. A mount is bound to the exact session provided by the host invocation or the worker's explicit binding result. Missing or ended sessions cannot cause source discovery or fallback. The viewer requests only bound frames and read recovery; the previous activity subscription and dashboard controls are retired from the view.

### Historical Alpha.8 compact work window and terminal recovery

The advertised resource is `ui://rdc/preview-v4.html`; reads of v3, v2 and v1 remain available. Browser/computer actions use the verified session image. Current terminal work can take the main area when no current visual action or explicit session pin takes priority, and completed output remains visible with its completed status. No synthetic work or unrelated desktop capture is started to fill an empty view.

A completed, non-mutating `rdc_preview_open`, `rdc_preview_frame` or `rdc_preview_activity` whose result expired or became unavailable receives a normal terminal envelope with `preview_refresh_required`, the exact `refresh_tool`, original `operation_id` and `completed: true`. The UI permits one fresh observation per automatic recovery cycle, checks operation identity and view generation, and stops repeated expiry. Legacy host-wrapped expired-result errors are normalized only from bounded recognized payloads. A typed missing-operation reply from the lookup of a known pending preview read allows the same bounded fresh observation while retaining its retired ID. It never claims that the missing read completed. Unknown outcomes retain the original reference for explicit reinspection; no mutation is redispatched.

The compact default layout keeps diagnostics closed. An explicit session choice still pins that view. Host dismissal/hide continues to stop observation without stopping jobs or sessions. Opening remains a separate explicit preview tool so ordinary actions reuse the viewer instead of creating a new tool shell for every action.

### Alpha.7 actual work and observation

The alpha.7 resource is `ui://rdc/preview-v3.html`; reads of the published v2 and v1 aliases remain available with the requested URI echoed. Follow work is the default when opening without an explicit session. It follows a known in-progress target or successful visual focus; the workspace dropdown pins a session, and Follow work releases that pin. Configured desktop/Android ADB alone does not trigger a capture. Explicit or focused native frames retain existing owner grants and screenshot checks.

The app-only `rdc_preview_activity` snapshot supplies actual current/recent RDC operation names, status/times, session freshness, job summaries and the selected real job's latest 8 KiB of output. A live job may be followed automatically; a completed job requires selection. Output is bounded read-only text. The activity timer and pending-operation recovery are independent from screenshot/navigation waits, with no general-purpose concurrent input lane.

The relay enables parallel observation only after the gateway advertises the exact activity tool and confirms an activity-only claim. Without that negotiation it retains the existing heartbeat/normal-dispatch path. Uncertain observer results keep the original operation ID and stop automatic redispatch; hidden/disposed views stop polling. A newer user pin or availability observation takes precedence over older activity. The feed describes work handled by RDC and its retained jobs, without claiming visibility into unrelated applications or workspaces.

At this alpha.7 source checkpoint, 37 UI/tool checks, 15 backend checks and 23 gateway checks passed without skips. The native candidate gate, installation and v3 hosted rollout are pending; actual ChatGPT rendering remains unobserved. The historical alpha.6 results below remain distinct.

### Alpha.6 opening and recovery

RDC advertises `ui://rdc/preview-v2.html` and retains reads of the published `ui://rdc/preview-v1.html` URI. Both return `text/html;profile=mcp-app`; the requested resource alias is preserved in the response. The gateway advertises the complete MIME extension capability above. The new URI gives the current tool/resource binding its own identity while retaining compatibility with hosts that still request v1.

The private gateway returns an exact pending operation reference immediately after an authorized online open is queued. The view recovers that original operation instead of issuing another open. An authorized offline/busy request that was never queued can return a successful availability envelope so a capable host can mount the component and show its retry control. It carries no fabricated empty session list or work counts. The view preserves prior snapshots as last known and stops polling until explicit action.

Retry connection handles a failed initialize handshake after its previous transport closes. Retry preview handles displayed worker/gateway availability; it inspects a retained original request before starting a new read-only open. Newer availability observations take precedence over older responses, and disposed views ignore late host context. All these controls require the component to have mounted. At the alpha.6 checkpoint, the private gateway deployment, live original-operation recovery and a synthetic browser image were verified, but production ChatGPT rendering had not been observed and the local Sites preview relay was unavailable. The 28 passing focused contracts and 19 passing gateway contracts are protocol evidence; actual host acceptance remains required.

## ChatGPT additions

Use the MCP Apps SDK's `requestTeardown()` notification to request host-owned dismissal. The host chooses whether to remove the view; do not report it as closed until teardown is observed. `window.openai.requestClose()` and `window.openai.requestDisplayMode()` remain compatibility APIs; prefer the portable SDK methods. The current OpenAI Extensions contract supports inline/fullscreen only; portable PiP remains usable only when another host advertises it. Optional widget state can preserve presentation settings. [2][8]

For convenient reopening, an open-preview tool can also declare:

```json
{
  "_meta": {
    "ui": { "resourceUri": "ui://rdc/preview.html" },
    "openai/ui": {
      "entrypoints": [{ "type": "thread" }, { "type": "global" }]
    }
  }
}
```

`thread` targets a conversation panel; `global` adds a sidebar entry. OpenAI documents these as ChatGPT extensions, with web Free/Go availability still forthcoming. [3]

## Claude details that affect implementation

Call `requestDisplayMode({mode: "fullscreen"})` directly from a user click or key handler while the view has focus. Claude can refuse a request and resolve with the existing mode. Layout from the reported dimensions rather than the word `fullscreen`, because side panel and full screen share that value. Account rollout and narrow windows affect placement. Claude currently advertises inline/fullscreen, rather than guaranteeing PiP. [6]

An optional Claude-specific `_meta.ui.preferredDisplayMode: "fullscreen"` on resource contents can request initial panel placement. This is a host extension, not a portable guarantee. A user who closes a connector's panel is not automatically forced back into it by that preference. [6]

Claude also recognizes a `global` entry point under `openai/ui` for eligible remote verified/custom connectors. Inputs should be optional so `{}` provides a useful opening view. Entry points are rollout-dependent and are unavailable for community-listed connectors or local servers. Ordinary in-conversation opening must remain usable. [9]

## Lifecycle and authorization decisions for RDC

The following are RDC design decisions, derived from the requirement and host boundary:

- **Close preview:** stop frame polling and detach the viewer. Never send browser-close or job-cancel. Request standard host teardown for dismissal; retain an independently usable Hide/Reopen control when the host keeps the iframe.
- **Minimize:** retain session identity and show a compact status strip. The worker keeps running.
- **Expand or dock:** request an advertised host mode, preserving the active session. Respond to changed dimensions without navigating away or starting another browser.
- **Move:** use host-provided PiP or panel controls where available. Do not draw a misleading draggable title bar that promises to move the containing AI window. A control inside an iframe cannot move itself outside the host's allotted region.
- **Resize:** adapt to host dimension changes; optionally resize content within a flexible inline container. The host decides outer size constraints.
- **Reopen:** read authoritative worker status by session ID. Handle an expired or missing session explicitly; do not silently replace it.
- **Pause input and stop job:** distinct operations with distinct state and authorization. Neither is implied by closing a view.
- **Owner authority:** never embed the owner token in HTML, tool metadata, or model-visible results. App-only visibility organizes tools; server-side authorization remains necessary.
- **Multiple viewers:** maintain independent subscriptions. Closing one viewer must not invalidate another or terminate the worker.
- **Teardown:** acknowledge host `ui/resource-teardown` and release local timers/listeners only. Persist required session state before the iframe is discarded. [8]

## RDC logo and plugin identity

The image inside the preview and the icon beside a tool invocation have separate installation paths. Package the original RDC artwork with the plugin. Current OpenAI packaging recommends a portable root `plugin.json` and `mcp.json`; presentation fields go under `extensions.com.openai.interface`, including `displayName`, `composerIcon`, `logo`, and optional `brandColor`. Icon paths are relative to the plugin root, usually `./assets/`. [10]

OpenAI distribution supports PNG, JPEG, WebP, and SVG icons up to 5 MiB, square, at least 48 by 48. Raster maximum dimensions are 4096 by 4096. Both composer icon and logo are required by Codex package validation. Supplying artwork does not alter the identity of the existing Desktop Commander connector. RDC must be installed and registered as its own plugin for its identity to appear. [11]

The repository supplies a local development package in root `plugin.json` and `mcp.json`, with `rdc/assets/rdc-logo.png` as both logo assets. It connects an installed `rdc` executable to the existing local worker. See [plugin installation](PLUGIN-INSTALL.md). Separately, the private App-backed plugin 1.0.2 was saved and its configuration read back; native ChatGPT tool calls are functional. Package files and saved presentation metadata do not establish rendered tool branding, public registration or an actual embedded preview.

## Acceptance criteria

1. In a real supported host, call the preview tool and observe the live worker in the conversation or host panel.
2. Expand and restore while the same session continues updating.
3. Resize the host panel or window and verify controls remain reachable, including narrow mobile layouts.
4. Use host move/PiP controls where offered; state explicitly when absent.
5. Close the view during a durable job and reopen; independently confirm the same job and browser session persisted.
6. Test unsupported and refused display requests, missing close extension, host teardown, and host connection loss.
7. Confirm no owner credential enters the iframe, tool results, source bundle, or model context.
8. Confirm the installed RDC plugin displays the intended logo. A screenshot or custom test host alone cannot certify this.

## Primary references

1. [OpenAI: Add UI to your MCP server](https://developers.openai.com/plugins/build/chatgpt-ui)
2. [OpenAI: Component bridge reference](https://developers.openai.com/plugins/reference)
3. [OpenAI: Plugin extensions](https://developers.openai.com/plugins/build/extensions)
4. [OpenAI: MCP server and UI quickstart](https://developers.openai.com/plugins/build/app-quickstart)
5. [Anthropic: Use interactive connectors in Claude](https://support.claude.com/en/articles/13454812-use-interactive-connectors-in-claude)
6. [Anthropic: MCP Apps display modes](https://claude.com/docs/connectors/building/mcp-apps/display-modes)
7. [Anthropic: Add an interactive UI to your MCP server](https://claude.com/docs/connectors/building/mcp-apps/quickstart)
8. [MCP Apps specification](https://github.com/modelcontextprotocol/ext-apps/blob/main/specification/2026-01-26/apps.mdx)
9. [Anthropic: MCP Apps entry points](https://claude.com/docs/connectors/building/mcp-apps/entry-points)
10. [OpenAI: Package your plugin](https://developers.openai.com/plugins/build/plugins)
11. [OpenAI: Upload and submit your plugin](https://developers.openai.com/plugins/deploy/submission)

## Floating preview boundary (checked 2026-11-15)

The owner's acceptance reference shows Codex's built-in computer-use preview floating over the chat and capturing only System Settings. This is the intended experience. The public [MCP Extensions display-mode contract](https://github.com/openai/mcp-extensions/blob/main/docs/spec.md#display-modes) explicitly excludes `pip` for ChatGPT and defaults to fullscreen when both modes are offered without a preference. V7 supplies `preferredDisplayMode: inline` and declares only inline/fullscreen in OpenAI resource metadata. The portable app still offers PiP only if negotiated by another host. This corrects an avoidable side-panel default but does not reproduce the built-in floating surface. Do not report exact parity until a supported host integration exposes it and a real host test confirms it.
