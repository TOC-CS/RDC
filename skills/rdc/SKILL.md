---
name: rdc
description: Use RDC (Remote Desktop Commander) by TOC Ministries for independent browser or configured Android/iPhone/iPad workflows, embedded live previews, file operations, durable jobs, private incident reports, recovery of pending cloud operations, and owner-approved saved-password fills through its connected App.
---

# RDC (Remote Desktop Commander)

Use the existing connected RDC App and its current tool schemas. Keep the user's worker, authorization, and task context together. Read [cloud operations](references/cloud-operations.md) when a call is pending or reconnecting, [diagnostics](references/diagnostics.md) for incident reports, [credentials](references/credentials.md) for saved-password fills, [mobile](references/mobile.md) for phones and tablets, and [compatibility](references/compatibility.md) before making platform or host-support claims.

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

Use `rdc_preview_open` to render the embedded MCP Apps resource in a compatible host. Retain the selected `session_id` and reconnect to it. The preview receives frames through the host's tool/resource bridge and never needs an owner credential.

Expand, resize, move, float, hide, close, and iframe teardown are viewer operations. They must not cancel jobs, close browser sessions, pause input, stop the relay, or terminate the worker. Hiding stops frame polling; reopening can attach to the same session. Use explicit authorized tools for cancellation, browser close, or owner control.

Offer only display modes the host advertises and honor its returned mode. The host owns outer placement and may refuse fullscreen or PiP. Movement within RDC's fullscreen canvas stays inside the allocated host area. Do not promise unrestricted movable windows in every AI application.

Use ordinary tool results when the host does not expose the UI bridge. An owner administration dashboard remains useful for approvals and diagnostics, but does not demonstrate that the embedded preview rendered in the AI host. Preserve the App's existing branding and presentation.

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
