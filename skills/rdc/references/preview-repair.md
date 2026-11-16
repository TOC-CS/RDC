# Preview repair acceptance queue

The target is a portable RDC experience across Windows, macOS, Linux, Android, iPhone and iPad, accessible to different AI agents through supported interfaces. One machine's test does not qualify another platform or AI host.

## Blocking acceptance items

- **Floating views:** multiple compact, independently movable live views, each bound to the actual source used by that task. The required surface must stay inside the actual AI workflow window. External desktop windows, including an RDC-branded bundled Electron app, do not fulfill this requirement and must not be used as an automatic fallback. Codex's built-in computer-use surface is not an exposed RDC API; the current OpenAI MCP extension specification supports inline/fullscreen, while the optional component bridge reference still documents PiP. Feature-detect, request through the host, and verify the actual returned mode and placement; neither documentation nor a mocked test proves live support. An RDC-owned viewer must run on the viewing device, which may differ from the worker. A Mac-only companion on the worker does not meet the portable requirement.
- **Background work:** preserve active application, window, keyboard destination, pointer and desktop/Space. The v7 native-input approval guard is installed, but this does not isolate arbitrary shell commands or external tools. Owner setup must be an explicit foreground handoff, never a routine task side effect. Live cross-platform noninterference acceptance remains open.
- **Source isolation:** retain task-specific browser/device/window IDs. Reject whole-display and global-focus fallback. Two tasks using the same physical app window share its contents; separate viewers do not create isolated workspaces. Validate multiple simultaneous viewers and two separate chats on each supported host.
- **macOS resize permission:** the installed runtime now reports Screen Recording and Accessibility true after the owner grant propagated. Do not repeat the grant. Preserve active BandMates work; further resize testing must use a disposable target or an explicitly available work window. Cross-installation setup still needs qualification.
- **Cursor attachment:** owner screenshots show detached white cursor markers over the desktop. A read-only macOS inspection identified a separate 'Software Cursor' window owned by ChatGPT Computer Use. That overlay is drawn outside the RDC iframe; correlating it with every reported white marker and finding a supported host visibility control remain open. RDC must keep its own cursor inside the bound image, use only that source's coordinates, hide it on teardown/source mismatch, and avoid duplicating cursors already baked into a captured frame. Do not claim a web-renderer fix repairs host-owned desktop overlays.
- **Chat tool-card branding:** the outer icon remains generic. Portable package and inner preview logos do not prove the App-owned chat receipt icon changed. Existing App-backed update controls preserve App presentation. Use a supported branding route; do not recreate the App or pairing to force a logo.

## Portable implementation contract

Separate the source adapter, session transport, viewer and AI-host adapter. A viewer consumes only its authorized source's frames, cursor and state. It never receives worker-wide job/activity feeds, source pickers or approval queues. Closing it revokes/stops that viewer subscription only. Missing or ended sources render empty. Hidden views remain hidden until explicitly reopened.

Desktop floating surfaces need background-safe platform implementations. Mobile views use the platform's supported presentation and orientation; multiple OS-level floating windows cannot be promised where unavailable. MCP is the agent interface where supported, with a documented integration boundary for other agents. No vendor name or configuration flag alone establishes compatibility.

Qualification records must name the source OS, viewing device, AI client, exact source type, presentation modes, cursor support, and measured focus behavior. Windows/Linux exact native-window capture and mobile/desktop viewing must each be exercised on real targets before support is claimed. Build and unit-test success alone do not establish live rendering or focus isolation.

## v7 evidence and limits

The release candidate passed 337 native tests and 26 gateway tests, embedded/gateway builds, TypeScript and skill validation. Its worker/gateway and setup skill were deployed to the existing private connection. GitHub uploads were read back and matched the qualified source tree. These facts do not close the blocking acceptance items above.

Official host contract: https://github.com/openai/mcp-extensions/blob/main/docs/spec.md#display-modes

## In-workflow host adapter candidate

The v8 UI requests floating presentation only through standard MCP Apps or the documented optional `window.openai.requestDisplayMode` bridge. It never launches an OS window, opens another browser, escapes its iframe, or changes the worker/source lifecycle. A refused or unconfirmed request remains unverified. Late host mode notifications are honored. Cursor overlays now require matching session/device metadata and are suppressed for captured cursors. Real ChatGPT/Codex placement remains a release acceptance item. No separate Electron installation is needed for this in-host UI.

Component bridge reference: https://developers.openai.com/plugins/reference#request-another-presentation-mode

## Cursor lifecycle qualification

- A fresh RDC browser has cursor visible=false. After a successful source-bound pointer action the frame reports visible=true with local coordinates; navigation clears visibility. Do not draw an agent cursor for an unconfirmed legacy (0,0) placeholder.
- A native capture whose cursor_in_image is true must never receive another CSS marker. Clip a visible browser marker to the actual rendered source image, accounting for letterboxing, scaling and scroll.
- Detached macOS windows named Software Cursor belong to the separate ChatGPT Computer Use helper. Inspect its lifecycle separately. Do not terminate that helper or hide an active session to force an overlay away; avoid reliance on host Computer Use for independent RDC browser operations.
