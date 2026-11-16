# Preview repair acceptance queue

The target is a portable RDC experience across Windows, macOS, Linux, Android, iPhone and iPad, accessible to different AI agents through supported interfaces. One machine's test does not qualify another platform or AI host.

## Blocking acceptance items

- **Floating views:** multiple compact, independently movable live views, each bound to the actual source used by that task. This remains unimplemented. Codex's built-in computer-use surface is not an exposed RDC API; the current public ChatGPT App contract supports inline/fullscreen, not PiP. An RDC-owned viewer must run on the viewing device, which may differ from the worker. A Mac-only companion on the worker does not meet the portable requirement.
- **Background work:** preserve active application, window, keyboard destination, pointer and desktop/Space. The v7 native-input approval guard is installed, but this does not isolate arbitrary shell commands or external tools. Owner setup must be an explicit foreground handoff, never a routine task side effect. Live cross-platform noninterference acceptance remains open.
- **Source isolation:** retain task-specific browser/device/window IDs. Reject whole-display and global-focus fallback. Two tasks using the same physical app window share its contents; separate viewers do not create isolated workspaces. Validate multiple simultaneous viewers and two separate chats on each supported host.
- **macOS resize permission:** an enabled RDC Window Preview switch did not make the current directly spawned helper trusted. Read-only macOS diagnostics attributed that launch to its parent AI app. Repair supported launch ownership and verify the actual worker path; do not repeatedly ask the owner to enable an already enabled entry, broaden another app's access, or edit TCC. Capture works; exact-window resizing is still blocked in this launch arrangement.
- **Chat tool-card branding:** the outer icon remains generic. Portable package and inner preview logos do not prove the App-owned chat receipt icon changed. Existing App-backed update controls preserve App presentation. Use a supported branding route; do not recreate the App or pairing to force a logo.

## Portable implementation contract

Separate the source adapter, session transport, viewer and AI-host adapter. A viewer consumes only its authorized source's frames, cursor and state. It never receives worker-wide job/activity feeds, source pickers or approval queues. Closing it revokes/stops that viewer subscription only. Missing or ended sources render empty. Hidden views remain hidden until explicitly reopened.

Desktop floating surfaces need background-safe platform implementations. Mobile views use the platform's supported presentation and orientation; multiple OS-level floating windows cannot be promised where unavailable. MCP is the agent interface where supported, with a documented integration boundary for other agents. No vendor name or configuration flag alone establishes compatibility.

Qualification records must name the source OS, viewing device, AI client, exact source type, presentation modes, cursor support, and measured focus behavior. Windows/Linux exact native-window capture and mobile/desktop viewing must each be exercised on real targets before support is claimed. Build and unit-test success alone do not establish live rendering or focus isolation.

## v7 evidence and limits

The release candidate passed 337 native tests and 26 gateway tests, embedded/gateway builds, TypeScript and skill validation. Its worker/gateway and setup skill were deployed to the existing private connection. GitHub uploads were read back and matched the qualified source tree. These facts do not close the blocking acceptance items above.

Official host contract: https://github.com/openai/mcp-extensions/blob/main/docs/spec.md#display-modes
