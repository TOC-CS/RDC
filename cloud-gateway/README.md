# RDC ChatGPT gateway

An owner-private Sites MCP server connected to the existing RDC device worker through an outbound authenticated relay. Its embedded resource is built from the actual RDC UI and tool catalog. The web landing page reports connection state; the working preview lives inside a compatible AI app.

## Deployment configuration

The tracked hosting manifest declares `capabilities: ["mcp"]`, D1 binding `DB`, and R2 binding `BUCKET`. Sites provisions these and the private ChatGPT plugin. Publish the generated Drizzle migration with the source; never create tables during request handling.

Configure runtime environment values privately:

- `RDC_DEVICE_ID`: the exact paired worker identity.
- `RDC_DEVICE_SECRET`: a cryptographically random device credential, at least 32 characters. Save the same credential in the device pump's protected local configuration.
- `RDC_OWNER_BOOTSTRAP=private-site`: enable only after confirming the Site is owner-private. The first authenticated Site principal is pinned in D1. Later visitors cannot replace it, even if Site access changes. Keep the deployment private.

The device also requires the Site's service credential in `OAI-Sites-Authorization`. Sites consumes that credential at its private edge. The gateway independently verifies `X-RDC-Device-Key`; neither credential grants the device a ChatGPT user identity. `/mcp` tool calls require the Sites-authenticated, pinned owner. Worker execution uses only its existing local agent token and its existing permission/approval rules. Owner tokens are never sent to this gateway.

## Outbound relay contract

`POST /device/poll` receives `{device_id, claim?: true}`. `claim: false` refreshes the heartbeat without claiming work and should run every ten seconds during an active tool call. A claim poll waits up to ten seconds. Responses contain `server_time_ms`, `poll_after_ms`, and either `operation: null` or `{operation_id, claim_id, request_json, request_sha256, expires_at_ms}`. Verify SHA-256 over the exact UTF-8 `request_json`, then parse `{name, arguments}`. Use the server's clock to decide whether the operation can still start.

`POST /device/result` receives `{device_id, operation_id, claim_id, request_sha256, result_json}`. `result_json` is the exact JSON-serialized MCP CallToolResult. A successful acknowledgment is `{ok:true, operation_id, status:"completed", duplicate:boolean}`. Uploading the identical result again is safe; a conflicting result is rejected. Persist execution admission and the result before sending it. A crash after execution admission must yield an unknown-outcome result rather than re-executing a mutation.

Both device endpoints require `Content-Type: application/json`, `X-RDC-Device-Key`, and the private Site service access header. No inbound connection to the user's device is needed.

## Short-command terminal fast path

When the installed worker and this published gateway both advertise `rdc_job_run`, short authorized terminal actions can return the original durable job status and bounded output in one tool call. `argv` is executed directly as an argument vector, with an explicit `cwd`; supply a shell explicitly for shell interpretation. Use `wait_ms` up to 3000 and `output_limit` to bound the inline wait/output. A pending result is still the original job, not permission to rerun it. Keep the same `_rdc_request_id` for recovery, and use `rdc_operation_status` if the cloud call itself is pending. Long-running or interactive commands retain `rdc_job_start`, status, input, output and cancellation. Server-side and model/tool network latency can dominate local execution, so measure speed rather than assuming faster behavior.

## Recovery and bounds

Cloud mutating tools require `_rdc_request_id`; it is removed before passing the original arguments to the local worker. Reusing the key with identical arguments recovers the same operation. Reusing it with different arguments fails. A queue claim is atomic and is never redelivered. Work expires if not claimed within 30 seconds. Claims with no response for two minutes become uncertain, and late results can still resolve them.

The gateway waits at most 20 seconds per tool call, or eight seconds for preview operations, then returns a pending operation ID. `rdc_operation_status` retrieves that operation without dispatching work again. Closing an embedded view never stops the device worker, browser, or jobs.

Requests are bounded to 1 MiB, results to 12 MiB, uploads to 16 MiB, and the active backlog to 32 operations. D1 holds small queue and identity records; results live in R2. Preview frame payloads expire after 30 seconds; other results expire after one hour. Mutation request IDs remain for 24 hours. Completed, expired, or uncertain read-only frame records retire after 60 seconds from completion, claim, or creation, once their payload is removed. If a delayed result upload receives the exact authenticated `operation_not_found` response, the relay records that operation as `undeliverable`, preserves its identity and no-replay tombstone, and continues unrelated work. This applies to any operation, including a mutation; it never means delivered or acknowledges completion to the cloud. Terminal request and result payloads have a 64 MiB retention bound while identity tombstones remain. Other upload errors still fail conservatively. Admission is additionally bounded to 2,000 operation records, 32 MiB of queued request payloads, and 512 MiB of committed result bytes plus in-flight reservations. Completed request arguments are removed. Cleanup is bounded and runs during normal traffic.

R2 and D1 do not share a transaction. If an object upload succeeds but recording its result in D1 fails, an orphan object can remain. An identical upload retry uses the same object key, but cleanup driven by D1 cannot discover an unrecorded orphan. The 512 MiB admission check therefore is not a strict bucket-storage quota. A future object-inventory sweep or deployment-managed lifecycle rule is required to bound orphan retention independently.

## Verification

`node --test tests/gateway.test.mjs` runs actual SQLite migration and queue SQL through a D1-shaped test adapter, with an R2 fixture. It covers authorization, idempotency, concurrent claims, expiry, uncertain recovery, large images, and bounds. Hosted authentication, D1/R2 provisioning, and the actual ChatGPT preview still require deployment acceptance checks.

Refresh the bundled catalog, HTML and original logo using the RDC virtual environment:

```sh
/path/to/rdc/.venv/bin/python scripts/sync-rdc-assets.py --rdc-source /path/to/rdc
```

The source export includes no credentials or private device state.

## Public source template

This directory is the deployable gateway source exported from the verified private deployment. Its owner-specific project identity has been removed. Provision a new owner-private Site, keep its returned project identity in your own checkout, configure the three runtime variables above through the hosting control plane, and retain the D1 and R2 bindings and generated migration. Existing Site deployments must retain their existing project identity. No device credentials, service credentials, owner tokens, state databases or user files are distributed here.

The identity headers used by this template are supplied by the Sites authentication boundary. Deploying it behind an arbitrary HTTP server that accepts caller-supplied identity headers would not supply equivalent authentication. A different hosting provider requires a verified identity boundary and deployment-specific configuration.
