---
name: rdc
description: Use RDC (Remote Desktop Commander) by TOC Ministries for independent browser or configured Android/iPhone/iPad workflows, embedded live previews, file operations, durable jobs, private incident reports, recovery of pending cloud operations, and owner-approved saved-password fills through its connected App.
---

# RDC (Remote Desktop Commander)

Use the existing connected RDC App and its current tool schemas. Keep the user's worker, authorization, and task context together. Read [cloud operations](references/cloud-operations.md) when a call is pending or reconnecting, [diagnostics](references/diagnostics.md) for incident reports, [credentials](references/credentials.md) for saved-password fills, [mobile](references/mobile.md) for phones and tablets, and [compatibility](references/compatibility.md) before making platform or host-support claims.

## Keep the owner’s work in the foreground

Work in the background by default. Preserve the owner's active app/window, keyboard target, mouse pointer, active desktop/Space, and preview visibility. A general instruction to complete a task or watch a preview does not authorize taking over the shared desktop.

Use RDC's headless Playwright browser, file tools, APIs, or noninteractive jobs for independent work. Shared `rdc_desktop_pointer`, `rdc_desktop_keys`, and `rdc_desktop_type` use the owner's real input; they are not background controls. WebDriver and commands that launch or activate apps may also interrupt the owner. Use automation that could affect shared focus, input, or the active desktop only with verified isolation or explicit authorization for the foreground takeover. Explicitly authorized exact-window capture or resizing may proceed through a background-safe method that does not raise, activate, or redirect input. An `isolated` configuration label alone is not verification. Do not move focus away and then restore it as a substitute for background operation.

Keep a hidden or closed preview hidden across tool results, recovery, and task progress. Do not call `rdc_preview_open` again or change presentation mode automatically to show activity. Reopen only at the user's request. Background builds must not automatically launch or activate their GUI for verification. An authorized exact-window capture or resize must not raise or activate that window.

If a required native action has no background-safe route, continue independent work and report the specific limitation before requesting takeover. Do not claim shared desktop input is independent or silently provision another desktop, account, or VM.

Updated workers enforce a separate owner decision for each `rdc_desktop_pointer`, `rdc_desktop_keys` and `rdc_desktop_type` call even in trusted mode. A queued result means no input was sent. Recover the original request; do not evade the guard with shell input injection or app activation. Approval controls stay in local owner administration, never in the live preview. Older workers may lack this guard; check the installed release and keep the same background policy.

## Establish the working connection

1. Discover the RDC tools available in the current AI host. For the cloud route, call `rdc_connection_status`, then `rdc_system_status` to inspect the selected worker, roots, grants, adapters, and pause state.
2. Distinguish a registered plugin, a deployed gateway, an online device, and a successful tool call. Each is separate evidence. If the App is not connected or requires owner sign-in, use its supported connection handoff. Skill instructions alone cannot create access.
3. Use the selected App binding. Do not register another App, replace its connection settings, expose a worker port, or put tokens in ordinary tool arguments to solve a missing connection.
4. Choose dedicated file/API tools, independent browser sessions, or durable command jobs according to the task. Inspect state, act, and independently verify the outcome.

When the host schema requires `link_id`, select an exact advertised account ID using the user's request and established conversation context. Retain that link with the worker and all operation, job, approval, credential and session IDs, and use it throughout recovery. If more than one account remains plausible for a write, resolve the target before dispatch; never invent an ID or switch accounts to retry an uncertain action. Local clients need no host account field unless their schema requires it.

## Execute and recover cloud operations

Supply one stable `_rdc_request_id` for each intended cloud mutation whenever its schema requires the field. Retain the exact arguments and any separate worker `idempotency_key`. Reusing the same key with different arguments is a conflict.

When a call returns `pending: true`, retain `operation_id` and use `rdc_operation_status` to retrieve the original result. A slow response, disconnected conversation, or ended model turn does not authorize another dispatch. If no operation ID was received, reuse the original request key and identical arguments to recover its existing record. Never generate a new key to retry an uncertain mutation.

Interpret the worker result only after gateway recovery. It may identify a background job, an ordinary owner approval, a credential approval, or a completed action. Use the matching recovery tool and ID from the table in [cloud operations](references/cloud-operations.md). A transport-level completion does not prove the user's task finished.

Report `pending_approval` or a credential request's `pending` status as waiting for owner review. Retain and poll the same request within bounded waits, preserve the owner's decision, and continue independent authorized work.

Treat `outcome_unknown`, an expired mutation result, or a missing retained record as incomplete evidence. Inspect the worker's file, browser, or job state before deciding on a new action. Fresh read-only observations are appropriate when their short-lived preview results have expired.

When ChatGPT itself reports a connection interruption, check RDC and recover existing operation IDs before attributing the problem to the worker. A healthy RDC worker stays running while the owner refreshes or troubleshoots the chat page. Follow [conversation interruption guidance](references/cloud-operations.md#chatgpt-conversation-interruptions); do not repeat a device action to repair the viewer.

## Inspect private incident reports

When the current catalog exposes `rdc_diagnostics_status`, use this read-only report to inspect recent worker failures and observed relay recovery. Follow the current schema, including required host account routing such as `link_id`, and optionally set integer `limit` from 1 through 50. The report accepts no repair action or free-text payload. Inspect `available`, `storage_status`, `incomplete` and `capture_scope`; a readable history or an empty list cannot establish worker liveness or a complete incident record.

Recover the original cloud operation and inspect its actual result before concluding a user task succeeded. `reconnected` confirms an observed transport recovery; `result_uploaded` confirms delivery of a recorded result, which may itself contain an error or unknown outcome. Preserve the original request identity and never replay an uncertain action from an incident entry. Follow [diagnostics](references/diagnostics.md) for report limits, local CLI use, platform qualification and repair boundaries.

## Preview inside the AI host

RDC targets multiple operating systems, viewing devices and AI agents. Report support per source OS, viewing device and host; never treat one Mac test, an embedded resource, or a configured adapter as universal qualification. Multiple floating views are an open requirement, not a verified feature. Floating views must operate inside the actual AI workflow window. Never substitute external OS windows or a separate Electron app. The embedded UI requires no Electron download. A viewer on the worker Mac does not establish that it works on a separate phone or computer. See [preview acceptance](references/preview-repair.md). Feature-detect the host's standard display modes and optional documented component bridge. Only call a view floating after the host confirms that mode and its placement is visually verified. If unavailable, report the missing host capability; do not escape the iframe or change the source.

Keep the agent cursor attached to the same source ID and device as its image, clipped to that image, and hidden when the view is hidden, ended, or unbound. Do not duplicate a cursor already included in a captured frame. A cursor marker on the physical desktop may belong to the AI host or another tool; establish its producer before attributing it to RDC.

When the user wants to watch work, open one live view for the exact RDC browser or configured device session used in this task. Retain its `session_id` from this chat's action result and pass it explicitly to `rdc_preview_open`, using the same worker and account. Each concurrent chat retains its own source ID; never reuse another chat's ID, a global desktop source, or the worker's most recent source. If two tasks intentionally target the same physical app window, they share that window's content and input; separate previews do not make separate native workspaces. Reopen with that same ID. File and command tasks use their normal tool results and job output, with no visual panel by default.

For a native Mac app, use `rdc_window_list` to identify its exact window, then pass that row's current opaque `target_id` to `rdc_window_open`. Use the returned `window-` session ID for the preview. Never pass `desktop` or substitute the foreground app: the preview must exclude the rest of the display even when other apps cover the selected window. An ended window needs a new explicit binding. `rdc_window_close` forgets only the binding and leaves the app running.

When the user authorizes the native window to resize with the pane, open its binding with `resize_to_view: true`. This changes the actual selected app window. The viewer requests bounded sizes and recovers pending resize mutations by their original operation IDs. Native minimum/maximum sizes may require scrolling; report the constraint rather than claiming every app can reflow. Screen Recording is required for capture, and Accessibility for resizing, using the RDC Window Preview helper. Preserve OS permission decisions.

For first macOS native setup or a permission refusal, guide the owner through the installed `rdc setup-macos` command with that worker's existing state directory. It prepares the helper, checks Screen Recording and Accessibility independently, and prints its exact path. `--json` is a nonprompting status check. In System Settings > Privacy & Security, enable **RDC Window Preview** under Accessibility for resizing and Screen & System Audio Recording for capture. If absent, use Add (+), Command-Shift-G and the reported helper path. The older **RDC** permission entry is separate. Treat permission setup as an explicit foreground handoff. Once the owner takes over, stop native mouse and keyboard input until they finish. Do not intermingle native setup automation with background task execution. Only an explicit owner setup action may use `--request accessibility` or `--request screen-recording` to display the normal OS prompt. Obtain required action-time consent before granting OS access; leave authentication to the owner. Never edit TCC or treat a prompt as a grant. Rerun setup through the actual worker launch path to confirm permission, then retry resizing on the same source. If the helper switch is enabled but the worker still reports denial, inspect launch ownership; macOS may attribute a directly spawned helper to its parent AI application. Do not repeat the same grant or broaden another app's permissions as a workaround. Keep capture working and report resize setup incomplete until the real worker succeeds. Capture can continue while resize permission is missing. Recheck after helper updates; ad-hoc signing does not guarantee persistent permission. Headless browser tasks do not require these Mac grants. See [macOS setup](references/macos-setup.md).

Use the preview for the source the agent is actually operating. Another chat, Codex's built-in browser, and the separately tagged Remote Desktop Commander connector do not automatically share RDC visual sessions. If the active surface is outside RDC, use its native preview where available or report that RDC has no live source for it. Never open a duplicate browser, pick a globally focused session, or show an administration page as a substitute.

The embedded preview uses a landscape viewing area and reports its content size to the host. The host controls the outer pane; do not automatically switch to fullscreen or floating mode to change its shape. The embedded preview is a single live image with the agent cursor when available and the host's window controls. It has no dashboard, session picker, job logs, or approvals. Honor the host's advertised and returned display modes. Hiding or closing the view affects only the viewer; the existing session and work continue. Resizing changes the source window only when explicitly enabled as above.

Confirm the host actually shows a changing frame from the selected session. A successful open result, static screenshot, or simulated host does not qualify live rendering. If the host cannot render it, keep working through normal tools and report the preview limitation. For pending or expired preview reads, see [preview recovery](references/cloud-operations.md#preview-lifecycle).

After an App update, an already-mounted pane may retain the old dashboard HTML. Refresh the existing App's tools through its supported settings, then reload the affected chat when its draft is safe. Verify the newly mounted pane. Do not restart the worker, recreate the App, or open a duplicate source to clear host UI caching.

## Use saved credentials privately

Call `rdc_credentials_list` for configured opaque aliases and permitted HTTPS origins. Observe the intended page and obtain fresh session, observation, and password-control handles. Request a fill with `rdc_credentials_request` using its current schema, a stable worker `idempotency_key`, and the cloud `_rdc_request_id` when required.

Recover the cloud operation first, then retain the broker's `request.id` and call `rdc_credentials_status` with it as `request_id`. The owner chooses Allow Once, Always Allow for this site, or Deny in owner administration. A matching persistent grant can avoid a new RDC consent prompt; the owner can revoke it there.

Preserve owner and operating-system prompts. Do not select Always Allow, approve or revoke grants, read owner tokens, automate native authentication, or extract a password vault on the owner's behalf. General trusted mode does not bypass credential consent.

Keep password bytes and provider locators out of chat, ordinary tool calls, logs, clipboard, public files, and revealing screenshots. The broker fills one selected password control privately and returns status. Filling does not submit the form. Keep subsequent account actions within the user's authorized workflow. Follow [credentials](references/credentials.md) for stale observations, redirects, grants, restart recovery, and provider limits.

## Complete files, browsers, and jobs

For files, use the current `file_path` schema consistently. Read the current SHA-256 before replacement or exact editing; resolve a hash conflict with a fresh read and deliberate edit. Bound searches and inspect truncation or skipped-file indicators.

For browser work, start or recover the intended independent session, navigate, observe, act with fresh observation/control handles, and reobserve after mutation or a stale-handle error. The preview cursor belongs to that browser session. Browser sessions survive a bridge/chat disconnect but are resident in the worker daemon and do not survive its exit.

Check `text_truncated`, `controls_truncated`, `control_scan_truncated`, and each control's `name_truncated` or `value_truncated` flags. Treat flagged observations as partial; missing content or handles do not establish absence. Obtain missing evidence through a narrower normal page view or another authorized nonsecret read. If a screenshot or preview refuses safe capture, preserve that refusal and follow [credential privacy guidance](references/credentials.md); never bypass it with another capture route.

For long commands, use `rdc_job_start` with an argument vector, explicit working directory, and stable idempotency key. Retain the job ID and recover it through status/output tools. Output offset zero starts at the beginning; carry `next_offset` forward. An exit code of zero does not make truncated or failed output capture complete evidence. Cancel only the intended authorized job.

Treat queued stdin as admission only. If delivery fails or becomes uncertain, retain the job and input IDs, inspect status/output, and never automatically resend the input or restart the command. Follow [cloud operations](references/cloud-operations.md) for recovery.

## Preserve owner control and report evidence

Use mobile tools only when the connected App advertises them and the selected worker supports them. For phones and tablets, choose an owner-configured profile with `rdc_mobile_list`, start or recover its `mobile-` session, and act through fresh observation IDs and handles. Never submit arbitrary driver endpoints, capabilities, scripts or locators. Physical-device input affects that device's user. Use a separate prepared emulator, simulator or dedicated device when the task must leave the owner's phone alone. Native secure fields require owner input; the browser credential broker does not fill native fields. Preserve screenshot refusals across capture routes. Follow [mobile](references/mobile.md) for lifecycle and uncertain-result recovery.

Honor pause, review, roots, and granted actions. Owner approvals remain outside the agent tool catalog. An authorized shell runs with the worker account's operating-system privileges; application file roots do not create an OS sandbox.

Use headless browser sessions for web work that leaves the user's pointer and focus alone. Native desktop control uses the selected desktop's pointer and focus unless a separate display, desktop, account, or VM is actually configured and verified. The `isolated` label does not provision that environment. Obtain a fresh native screenshot and use its coordinate-scale metadata before input.

Report actual observations separately from implemented adapters, fixtures, and planned support. Preserve authentication and permission boundaries on every platform. Do not claim that local Codex success proves production ChatGPT or Claude rendering, that WebKit proves Safari, or that a phone-sized web dashboard proves native phone control. Measure comparable workflows before asserting a speed advantage. Keep the user's existing working route until the replacement they need is verified.
