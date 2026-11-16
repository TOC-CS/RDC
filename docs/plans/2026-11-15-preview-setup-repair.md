# RDC remaining preview repair

Use the deployed v6 production branch, preserving the App, pairing and permissions.

1. Add behavioral regression tests: no shared native input in trusted mode without an owner decision; isolated labels do not assert isolation; permission setup reports capture and resize independently and never grants access itself.
2. Implement owner-only macOS setup: prepare the named helper, query both permissions without prompting, explicitly request the selected permission, show exact System Settings/Add steps, and recheck. Surface this in initialization and doctor. Keep capture/resize paths free of prompts or activation.
3. Update README, installation guide and packaged ChatGPT skill to explain exact sources, background defaults, permission setup, host layout and branding limits. Preserve existing App-owned metadata.
4. Run the native suite, relevant real-helper checks and gateway checks. Publish the repair branch to GitHub and update the existing private ChatGPT skill. Deploy matching worker code only after checking active work and preserving rollback.
5. Walk the owner through the macOS grant using supported System Settings UI, then verify exact-window resizing without activation. Recheck host acceptance where exposed; record unsupported outer branding/geometry honestly.

The owner has authorized repairs and rollout. macOS consent/authentication remains an explicit owner action. No broad permission reset, TCC edits, replacement App, or duplicate preview source.
