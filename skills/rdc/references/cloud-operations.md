# Cloud operations and recovery

Use the current RDC App tool schemas. The cloud gateway adds `rdc_connection_status`, `rdc_operation_status`, and a `_rdc_request_id` field to worker tools. Local stdio or loopback worker tools do not need the cloud field unless their advertised schema says otherwise.

Some AI hosts also require `link_id` for account routing. Copy an exact ID from the current advertised account choices and select it using the user's request and established conversation context. Do not derive it from an account name or email. If more than one account remains plausible for a write, resolve the target before dispatch. Retain the selected link with the worker identity and every operation, job, approval, credential and session ID, and keep the same link throughout recovery. Two connections reaching the same worker do not justify switching accounts to retry an uncertain action. Add this field only where the current schema requires it.

## Select the right recovery ID

| Result or state | Retain | Recover with |
| --- | --- | --- |
| Gateway `pending: true` | `operation_id` | `rdc_operation_status {operation_id}` |
| Worker job admitted | `job_id` and worker idempotency key | `rdc_job_status` and `rdc_job_output` |
| Ordinary owner review, `status: pending_approval` | `request_id` | `rdc_request_status {request_id}` |
| Credential broker response | `request.id` | `rdc_credentials_status {request_id: request.id}` |
| Independent browser | `session_id` | Browser observations and `rdc_preview_open` for that session |

The table identifies result IDs; each recovery call must also include the selected host account routing when required by its schema.

Unwrap a completed gateway operation before interpreting the worker result. A cloud operation completing can mean the worker created an owner approval request, rather than that the requested action finished. Owner administration is separate from the agent tool catalog.

For `pending_approval`, tell the owner the action is waiting in the paired computer's owner panel and poll the existing `request_id`. For a credential request's `pending` status, retain `request.id` and use its separate credential status tool. Leave decisions and native authentication to the owner; continue independent authorized work without creating replacement requests. Preview approval/job counts reflect the last status check, so refresh status before relying on them.

## Dispatch one intended mutation

1. Confirm the selected account, connection and worker state, then use the current schema.
2. Generate a unique `_rdc_request_id` for the intended cloud mutation. Retain it with its exact tool and arguments. Keep a required worker `idempotency_key` as well.
3. Send the request once. If it returns pending, retrieve the original operation ID until it reaches a meaningful outcome, within a bounded wait.
4. After transport loss, recover the saved operation ID. If no operation ID was received, reuse the same request key and identical arguments to recover its existing record. Never substitute a new key to retry an uncertain mutation.
5. Verify the actual result with a readback or observation. Report pending approval, uncertainty, or unavailable evidence accurately.

An explicitly offline response means no new operation was queued. The device claims queued work once; expired queued work is not dispatched. A claimed operation whose response is lost is never automatically redelivered. A worker-side timeout may occur after the action took effect.

## Job input and incomplete evidence

An input response containing `queued: true` and `input_id` confirms queue admission only. Retain that ID with `job_id` and the original cloud request identity. If delivery fails, the worker leaves the affected input unacknowledged, closes its input stream, and reports incomplete input in the job error without replaying it. A prefix may already have caused effects, even if the process later exits with code zero.

Inspect `rdc_job_status` and retained `rdc_job_output` before deciding what remains to do. Do not automatically resend the input, start a replacement command, clear the journal, or invent a new request key to recover from uncertain delivery. Keep output truncation and capture errors separate from process exit status when reporting completion.

## Retention and large results

Mutation request identities are currently retained by the gateway for 24 hours. Other result payloads normally expire after one hour. Preview images expire after 30 seconds and their terminal operation records have a short retention period of approximately 60 seconds. These are current implementation values; inspect deployment configuration if they matter to a recovery decision.

Read-only preview observations can be requested afresh after their original result or record expires. An expired mutation result does not authorize replay. The local relay preserves execution tombstones and reports uncertain interrupted work rather than repeating it. If an authenticated gateway response confirms that an operation identity has expired, the relay records the outcome as `undeliverable`, preserves its request and result within the 64 MiB terminal-payload retention bound, and continues unrelated work. That state never means the action failed or its result reached the cloud. Inspect the worker before any new mutation; do not clear the journal to force replay. Identity tombstones remain after payload pruning.

Current request/result/upload limits are 1 MiB, 12 MiB, and 16 MiB respectively. Oversized output may produce a small `result_too_large` result after an action already ran. Inspect retained job output, files, or browser state instead of rerunning the action to retrieve the same oversized response. The gateway's storage admission checks do not guarantee a strict R2 bucket quota because interrupted writes can leave orphan objects.

## Preview lifecycle

Open `rdc_preview_open` through the App host and preserve the selected session. The embedded component recovers pending frame operations by ID. It uses the host's tool/resource bridge, without embedding worker or owner credentials. If a selected session ended, refresh offers the remaining sessions for explicit selection. Preview status counts describe the last status check; approval requests must be reviewed in the owner panel on the paired computer.

Hiding, closing, resizing, moving, changing display mode, or tearing down the iframe affects only the viewer. Those actions do not cancel jobs, close browser sessions, stop the relay, or terminate the worker. Use explicit authorized tools for those actions. Reopen the same session when appropriate.
