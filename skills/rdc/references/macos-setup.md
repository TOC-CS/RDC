# macOS native-window setup

Headless RDC browsers and file/background jobs do not need these permissions. Native window capture requires macOS 14 or later, Apple command-line tools to build the helper, and the owner's native desktop grant in RDC configuration.

## First installation

Initialize a new profile only. Add `--desktop-mode shared` when you want native-window previews. This enables the optional native adapter; it does not grant macOS permissions or authorize silent input takeover. Existing profiles must keep their configuration, tokens and pairing.

Run the installation's command, with its existing `--state-dir` if customized:

```sh
rdc setup-macos
```

It builds the named **RDC Window Preview.app**, prints its exact location, checks both permissions, and provides the walkthrough below. Running the check does not display a permission prompt or change a grant. The older **RDC** app is a different entry; an enabled switch for it does not establish permission for this helper.

## Allow capture and resizing

1. Open **System Settings → Privacy & Security**.
2. Under **Screen & System Audio Recording** (called Screen Recording on some macOS versions), enable **RDC Window Preview** for window capture.
3. Under **Accessibility**, enable **RDC Window Preview** for exact-window resizing.
4. If the helper is missing, click **Add (+)**. Press **Command-Shift-G**, paste the helper path printed by setup, press Return, select the app, then click **Open**. The default is `~/Library/Application Support/RDC/native-window-helper/RDC Window Preview.app`.
5. Complete any macOS authentication yourself. Never paste your password into chat. The OS grant permits accessibility control; RDC's helper uses it to match and resize the selected window without raising or activating it.
6. Run `rdc setup-macos` again. It must report **allowed** for both permissions. Then use **Retry window resizing** in the existing preview. A permission dialog or enabled-looking switch alone is not verification.

The owner can explicitly request the normal OS prompt to register a missing entry:

```sh
rdc setup-macos --request accessibility
rdc setup-macos --request screen-recording
```

Run only the permission request you need. These commands request access; they cannot approve it. Apple requires the owner to grant access, and its Accessibility prompt is asynchronous. Normal capture, resizing, worker startup and `rdc doctor` never request permissions automatically. [Apple's Accessibility instructions](https://support.apple.com/en-ie/guide/mac-help/mh43185/27/mac/27) and [permission API](https://developer.apple.com/documentation/applicationservices/1459186-axisprocesstrustedwithoptions).

For an installer or support check, `rdc setup-macos --json` returns separate `screen_recording`, `accessibility`, `ready` and `helper_path` fields. `rdc doctor` also checks them for an enabled native adapter. Missing resize permission does not stop capture of the already bound window. The app can impose minimum sizes even after permission is allowed.

## Enabled switch but denied at runtime

Check permissions from the same launch route as the worker. macOS can attribute a directly spawned helper to its parent application. In the v7 live test, the named helper was enabled but its request was attributed to the AI host, and Accessibility remained false. Do not repeatedly toggle the helper or grant the AI host broader access to hide this mismatch. Resolve the supported app/service launch ownership first, then rerun the worker check. Setup is incomplete until that real path succeeds. See [the acceptance queue](preview-repair.md).

## Updates and background operation

Keep the helper in the same location. This source installation signs locally; a rebuilt helper can require a fresh OS decision. Recheck after updates. Do not reset all privacy permissions, edit TCC databases, approve unrelated apps, or promise permanent permission across ad-hoc rebuilds. A distributable, consistently signed and notarized installer remains separate release work.

The worker requires an owner decision for every shared native pointer/key/type operation, including trusted mode. An `isolated` label does not verify a separate desktop. Those decisions use the local owner-only CLI or authenticated owner API, never agent tools or the live preview. Use headless browser sessions, APIs and noninteractive jobs for background work. Arbitrary owner-authorized commands can still launch applications; the input guard is not an operating-system sandbox.

Each chat retains its own actual browser or native-window session ID. Never select the entire display or global foreground window. Hiding the view keeps work running. The AI host controls its outer panel dimensions and tool-card branding; RDC cannot promise a floating landscape panel or an outer logo change from an inner image.
