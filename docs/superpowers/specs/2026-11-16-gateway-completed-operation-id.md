# Gateway completed-result operation ID visibility

## Root cause
The gateway includes an operation ID in MCP result _meta for completed results, but the current ChatGPT connector drops that metadata while retaining structuredContent. Thus owner-only diagnostic lookup cannot be used on a successful first call unless the gateway ID was separately observed during a pending response.

## Approaches
1. Selected: extend completed structuredContent objects with a reserved _rdc_gateway_operation_id, without altering original content, return codes, worker payloads, permissions, and recovery.
2. Force all callers to return pending first: rejected as it breaks the fast terminal path.
3. New authenticated lookup endpoint by request key: deferred because it adds a separate API and database load.

## Safety
Only annotate plain-object structured results. The authenticated gateway overwrites any untrusted reserved placeholder field. Preserve _meta, original content, owner authorization, idempotency and original terminal result. No new routes, migrations or app publications. Work on an isolated branch while the existing cloud-storage candidate is under development.
