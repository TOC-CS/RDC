# Claimed completion polling optimization

## Intent
Short RDC cloud commands already execute locally in approximately 65 ms, but the cloud route spent 3.112 seconds median in 12 live tool-level pairs. The gateway's first tool call polls its own durable operation record at 500 ms intervals, potentially adding up to 500 ms after a worker uploads a result. Improve only that interval without increasing idle or queued operation reads, changing worker configuration or mutating retry semantics.

## Approaches considered
- **Preferred: bounded post-claim fast checks.** Keep the current initial 500 ms interval until a gateway operation has actually been claimed by the device. Once the claim is observed, check completion at most three times at 100 ms. Then return to the existing 500 ms interval. The maximum extra read load is bounded and applies only to actively claimed work.
- Always poll at 100 ms: rejected because it multiplies idle/slow-job D1 reads up to five times, increasing cost.
- Use a new push gateway or Durable Object: deferred; higher infrastructure cost, migration and deployment risk without isolated timing evidence.

## Scope
Modify only `cloud-gateway/lib/rdc-gateway-core.mjs` dispatch completion loop and `cloud-gateway/tests/gateway.test.mjs`; leave local relay, worker, provider credentials, plugin identity, gateway audience, and BandMates alone. No new routes or fields, no schema migration.

## Acceptance and non-goals
A fast completed operation whose claim is observed on the first 500ms read returns on the next 100ms read, rather than on a later 500ms read. An unclaimed operation retains the original 500ms schedule. A claim with no result gets exactly three 100ms probes, then resumes 500ms. Current timeout bound and idempotent recovery are preserved. This change does not guarantee that the complete cloud service beats Desktop Commander or solves host PiP/cursor issues.

## Failure modes
- Upload raced with claim read: the gateway must still retrieve persisted completion without repeat execution.
- Claim remains stuck: after three probes normal backoff resumes, bounded until original deadline.
- Client connection lost: existing idempotency and recovery paths remain untouched.
- Operation expires or becomes unknown: return existing terminal status immediately.
- Disabled/zero wait: no extra polling or time beyond configured deadline.
