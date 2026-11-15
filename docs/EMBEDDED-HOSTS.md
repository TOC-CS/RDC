# Embedded preview host contracts

Research checked against primary documentation on 2026-11-15. Documented host capabilities and executed RDC checks are separate evidence. The private ChatGPT tool connection is verified; production embedded rendering remains unverified. See [release verification](VERIFICATION.md).

## Product requirement

RDC's primary preview belongs inside the AI application. The worker owns the browser and jobs. A preview is a detachable viewer of that worker. Expanding, resizing, moving, hiding, or closing the viewer must not stop its browser session or background jobs. A later viewer must reconnect by device and session ID.

The existing standalone dashboard can remain an administrator and diagnostic interface. Opening it in a browser does not satisfy the embedded-preview requirement.

## Host compatibility

| Host | Documented presentation | Window controls and limits | RDC verification status |
| --- | --- | --- | --- |
| ChatGPT web and desktop | MCP Apps component inside the conversation; inline, fullscreen, and picture-in-picture presentation. Plugin extensions add conversation panels and sidebar entry points. [1][2][3] | Request an advertised mode and standard teardown. The host controls placement, dismissal and the surrounding window. Exact availability depends on the user's host and account. | Private RDC plugin 1.0.2 was saved/read back and native tool calls succeeded. Actual rendered preview, window behavior and approved cloud browser acceptance remain unverified. |
| Codex | Official quickstart explicitly documents MCP tools for ChatGPT and Codex, and optional UI in ChatGPT. [4] | Do not infer third-party MCP Apps rendering from Codex's built-in browser preview. No public third-party window-control contract was established in this research. | RDC MCP workflow tested separately; embedded rendering remains unverified. |
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

## ChatGPT additions

Use the MCP Apps SDK's `requestTeardown()` notification to request host-owned dismissal. The host chooses whether to remove the view; do not report it as closed until teardown is observed. `window.openai.requestClose()` and `window.openai.requestDisplayMode()` remain compatibility APIs; prefer the portable SDK methods. Mobile PiP requests may become fullscreen. Optional widget state can preserve presentation settings. [2][8]

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
