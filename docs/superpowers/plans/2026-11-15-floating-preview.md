# Portable Preview Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task by task. The acceptance items remain open; this document is not evidence of delivered compatibility.

**Goal:** Independent live previews across Windows, macOS, Linux, Android, iPhone and iPad, available to different AI agents, without dashboards or foreground takeover.

**Architecture:** Floating views belong INSIDE the AI workflow window; external OS windows are not an acceptable substitute. No separate Electron installation for end users. Separate source adapters, authenticated session transport, viewing-device renderer, and AI-host adapters. A viewer belongs to the device where the owner watches, which may differ from the execution worker. A native Mac companion alone does not meet this requirement. Keep the existing worker pairing, App identity and private audience.

**Spec:** [Portable acceptance queue](../../PREVIEW-REPAIR-QUEUE.md), including the owner's multiple-floating-window reference and background-operation requirements.

**Tech Stack:** Existing Python worker and MCP gateway; shared web renderer; supported native platform capture and viewer integrations where needed. Choose desktop packaging only after checking platform requirements; do not make a Mac-only launcher the architecture.

## Global constraints

- Every view has a task-specific exact source ID and principal/device binding.
- No whole-display or globally focused fallback, dashboards, job feeds, approval queues or source picker.
- Close/hide only ends that viewer subscription; source work continues and hidden views stay hidden.
- Use verified background-safe operations. Shared native input requires explicit owner takeover.
- No worker-wide credentials in a viewer; any transport grant is bounded to its source, owner, device and expiry.
- Keep existing production routes and pairing until replacements pass real host/device acceptance.
- Do not call support universal because one OS, one AI host, or simulated fixtures pass.

## Tasks

1. **Portable session contract.** Define source capability and lifecycle reports independently of platform. Test invalid/missing/ended IDs, concurrent sources, reconnect, hide persistence, stale frame rejection and wrong-principal/device refusal.
2. **Viewing-device transport.** Build a read-only live-frame subscription on the existing authenticated route, with per-view revocation, bounded frames, backpressure and expiry. Test that no view receives another source or job data. Never expose the worker port or owner token.
3. **Shared renderer.** Reuse the image/cursor-only presentation and responsive sizing. Test multiple concurrent view instances, landscape layout, mobile orientation, empty states and close/reopen. No session chooser or automatic fullscreen.
4. **Host adapters.** Negotiate supported inline/fullscreen/PiP/floating presentation. MCP clients use supported resources/tools; other agents need an explicit documented adapter. Report missing host capability instead of silently opening another source or pretending the host supports floating windows.
5. **Desktop adapters.** Qualify exact native-window capture and optional resize on macOS, Windows and Linux separately. Capture must remain exact while occluded and after focus changes. A configuration flag or full-desktop crop is not proof. Resolve macOS helper launch attribution before claiming resizing works.
6. **Mobile adapters and viewers.** Qualify Android and iOS/iPadOS source privacy and lifecycle, plus rendering on phones/tablets viewing a different worker. Use OS-supported presentation; simultaneous OS-level floating windows may be unavailable and must be reported.
7. **Setup and branding.** Provide OS-specific first-run guidance and permission checks through the actual runtime identity. Setup is an explicit foreground handoff. Keep the outer App icon issue separate from renderer/installer icons; use a supported App branding route.
8. **Release gate.** Record source OS, viewing OS, AI client, source type, actual mode, cursor behavior and focus evidence. Exercise two chats, two sources, hide/reopen and durable work. Run platform CI plus real-device acceptance before rolling out each platform claim.

## External constraints to resolve

The current public ChatGPT MCP extension contract exposes inline/fullscreen and explicitly does not support PiP. Codex computer-use floating surfaces are host-owned; the computer-use REPL refused inspection of the Codex app itself. Do not bypass that block or claim access to its implementation. An RDC-owned surface can mirror behavior where the OS allows it, but cannot force every AI host to offer identical in-chat windows.

The v7 helper grant is enabled on the test Mac, yet the current worker launch is attributed to the parent AI host. A hidden LaunchServices probe failed with -10810 in this environment. No privacy database changes or broader host grants were made. This remains an explicit setup blocker, not a reason to repeat the same user action.

## Current implementation boundary

The external viewer experiment was removed from this release after the owner clarified the in-workflow requirement. The current candidate tests the documented optional host bridge and retains standard MCP host negotiation. No external fallback is shipped. Source and viewing devices remain independent; unsupported host modes are reported honestly.
