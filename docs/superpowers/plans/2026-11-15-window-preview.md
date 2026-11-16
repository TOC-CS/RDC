# Window-bound preview implementation plan

User requirements: capture only the exact native window used by the task; resize that window to the host preview (explicitly selected by the user); no desktop fallback, dashboard or session picker; hide/close preserve work. Outer App branding remains blocked by absent supported branding controls, independently of this implementation.

Use the existing isolated production-baseline checkout. Implement inline in this chat.

1. Add native-window tests for explicit binding, permission refusal, stale/reused identity, close without app termination, and resize authorization. Implement `rdc/windows.py` with opaque discovery IDs and session IDs, using a packaged macOS ScreenCaptureKit/Accessibility helper. Never capture the desktop or select the frontmost window as a fallback. Return actual dimensions after native minimum-size constraints.
2. Connect window list/open/close tools and snapshots to the existing adapters and engine. Reject `desktop` in the embedded preview while retaining the explicitly authorized desktop screenshot tool for its separate purpose. Add an app-visible resize mutation, authorized only for sessions explicitly opened with resize enabled. Recover exact pending resize operation IDs; never repeat uncertain mutations.
3. Make the viewer use the full host content area and request debounced source resizing. Keep aspect ratio, report source size constraints and allow overflow rather than silently crop controls. Test tall/narrow pane, hidden state, teardown, errors and source identity.
4. Build v6 resource and gateway assets, preserve previous aliases. Update installed skill with exact-window discovery/binding, resize behavior and stale-pane reload guidance. Run affected tests, full qualification, and isolated real-window verification before rollout. Preserve active work; no worker restart while another task is using it.
5. Roll out through the existing candidate installer and owner-private Site/App routes when idle. Visually verify the exact native window in the real host, including occlusion, pane resizing and close. Retain rollback. Update the handoff with evidence and any remaining icon limitation.

Review focus: source closes between list and capture; OS window ID reused by another process; resize request lost after execution; app enforces a minimum size; hide/teardown arrives during a pending resize.

Latest correction: use a landscape viewing area instead of a forced full-height portrait layout. Each chat must retain its own explicit source ID; reject the global desktop in both viewer and worker. No auto display-mode changes or foreground activation. Ship the desktop refusal independently of optional resize authorization where possible; do not describe any unpublished candidate as live.
