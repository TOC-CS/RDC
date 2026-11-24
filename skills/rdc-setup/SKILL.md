---
name: rdc-setup
description: Guide first-time RDC connection and native Mac permission setup, or repair a missing Screen Recording or Accessibility grant for RDC Window Preview.
---

# Set up RDC

Use the existing TOC Ministries RDC connection and installed worker. Preserve its App identity, profile, tokens, pairing and grants. The separately named Remote Desktop Commander connector is not the same worker. Do not initialize over existing state or ask the owner to paste tokens into chat.

1. Check available RDC tools and the selected worker. Use `rdc_connection_status` on a cloud route, then `rdc_system_status`; recover pending calls by their original operation ID. If no worker is installed, use the repository's installation guide and distinguish installing a plugin from installing its local worker. Hosted chat cannot access the owner's localhost without a connected route.
2. For web tasks, use a headless RDC browser. No macOS screen/input permissions are needed. For native Mac preview or resizing, use the installation's `rdc setup-macos --json` with its existing state directory when an authorized local execution route exists. If unavailable, walk the owner through `rdc setup-macos`; do not pretend a remote cloud command ran on their Mac. Older workers lacking this command need the documented manual steps or an authorized update.
3. Follow [the macOS walkthrough](../rdc/references/macos-setup.md). The separate **RDC Window Preview** helper needs Screen Recording for capture and Accessibility for resizing. An older **RDC** grant does not establish either helper permission. Setup prints the exact helper path and reports each grant independently. Default checks do not prompt or change OS access.
4. Only when the owner chooses to enable a missing permission, request it through normal System Settings or the explicit `--request` setup option. Obtain any action-time consent required by the host. Let the owner complete native authentication; never edit TCC, reset unrelated permissions or treat elapsed time as approval. Rerun the check after the owner acts. A request dialog is not a successful grant.
5. Bind this chat's actual browser/device/window and open one preview for its returned session ID. A native window must come from current `rdc_window_list` discovery and `rdc_window_open`; enable `resize_to_view` only when authorized. Verify changing frames and, if authorized, a real size change. Do not create a duplicate browser as a substitute for another tool's source.
6. Keep the preview inside the actual AI workflow window. The embedded viewer needs no separate Electron download. Do not launch an external desktop viewer as a substitute. Verify any host floating-mode request by its actual result and visible placement.
7. Explain only remaining limits: each native window is one physical shared app, shared native input needs owner approval, and the host controls outer panel geometry and branding. Hiding the preview leaves work running and stays hidden until asked to reopen. Use `rdc serve` for a headless worker; do not open an owner-control interface as a preview or promise Codex's built-in floating computer-use viewer.

Finish with the worker connection, capture/resize permission results, and one concrete next step if setup is incomplete. Do not request Mac permissions for browser-only use.

If an already enabled helper is denied by the actual worker, inspect launch ownership and report setup incomplete. Do not keep asking for the same grant or enable a different AI app. Permission setup is a foreground handoff: stop agent native input while the owner is using System Settings. Match guidance to the actual OS; this Mac walkthrough does not establish Windows, Linux or mobile qualification.
