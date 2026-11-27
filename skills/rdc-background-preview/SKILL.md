---
name: rdc-background-preview
description: Apply RDC background-only adapter policy, exact-session floating preview and terminal-job completion safeguards; diagnose preview v10 compatibility and distinguish deployed capabilities from source-only updates.
---

# RDC background execution and floating previews

Use this skill with the existing [RDC skill](../rdc/SKILL.md) for non-interrupting automation, preview troubleshooting, and repair verification. The November 24 repair branch is `fix/rdc-background-preview-20261124` (PR #23). Source qualification and plugin publication do not prove runtime activation. Inspect current advertised tool schemas and installed capabilities before invoking an optional argument or reporting a fix as live.

## Background policy

- Prefer independent headless Playwright browser sessions, noninteractive terminal jobs, file tools, or supported APIs. Never control the user's ordinary Chrome tabs, foreground applications, keyboard or pointer via AppleScript, shell, WebDriver or other indirect routes to evade the background-only policy. A terminal command running asynchronously is not proof of UI isolation.
- The repaired worker defaults to background-only mode. It rejects shared desktop keyboard, pointer and typing, unverified WebDriver sessions, and preview-driven resizing. The exact native window can be observed without resizing when the owner and platform permit capture. Do not request a resize grant for a background preview. Explicit foreground configuration and existing approval controls remain necessary for intentional foreground work. Do not weaken these controls to make a task succeed.
- If a supported independent browser is not authenticated, preserve the existing account and obtain authentication through an appropriate owner-approved path. Do not silently fall back to the ordinary browser, copy cookie databases, or borrow a different task's authenticated session.

## Floating view lifecycle

- Use the exact session_id obtained from the task's own visual operation. If both live preview tools advertise job_id and the task has an associated durable job, provide its exact original job_id when opening the preview. Never guess a session or job, substitute another chat's source, use a worker-wide display, or bind an unrelated job to force closure.
- Repaired preview v10 offers a user-initiated Float request through a documented host bridge when available and verifies the returned mode. Automatic PiP requires advertised host support. Fullscreen is not floating; request inline restoration if the host substitutes fullscreen. If the host refuses floating, report the limitation, retain the available inline view, and never create an external OS window as a fallback.
- A confirmed terminal job (completed, failed, cancelled, timed out) allows its own job-linked floating view to clear without another capture. Interrupted or uncertain status is not terminal proof. Closing the viewer never cancels the source or job. A session without job binding cannot be represented as automatically closing on job completion.
- Preserve all historical resource aliases. A plugin version bump, source SHA, or mocked browser fixture alone cannot prove actual ChatGPT floating placement or live job-bound teardown. Verify live gateway catalog, exact resource and worker compatibility separately.

## Release and speed boundaries

The narrow background/preview repair is distinct from the unreleased RDC 2.0 transport migration. Keep the existing owner binding, app identity, private audience, permissions, durable operation IDs, no-replay behavior, and rollback. Do not change the transport or merge the protected V2 PR merely because this skill is published. Independent local/offline operation and optional owner VPS remain the intended architecture; no new Cloudflare or Sites dependency.

Use the 100-check hard maximum per test campaign, counting repeats and nested checks conservatively. Measure actual end-to-end speed on exact, matched workloads and distinguish local or VPS benchmarks from the connected ChatGPT host. Do not claim the production speed targets or host placement gates are met without verified live evidence. Preserve ongoing jobs when installing a worker update; do not restart the existing worker while it has active jobs or needed browser sessions.
