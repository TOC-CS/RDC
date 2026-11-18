# RDC P0 Private Durable Object Wake: staging and release qualification

**November 18, 2026. SOURCE-ONLY. PRODUCTION v16 UNCHANGED.**
This is a speed-first transport improvement. The target is at least 2x improvement over Desktop Commander on matched real ChatGPT workflows, without execution, retention, authorization or resource regressions.

## Why
Prior connected 30-round shell workload: RDC p50 3178ms vs DC p50 1820ms, both 30/30 correct. Twelve recorded RDC operations showed queue wait p50 311ms and claim-to-result p50 678ms. The selected-file REA review of Desktop Commander 0.3.1 showed a Realtime doorbell with guarded persisted claim. RDC uses D1 long polling with 500ms probes. These findings motivate event-driven hints; they do not establish that the whole host roundtrip will become 2x faster.

## Source behavior
- `createGateway` accepts an optional env-bound wake channel; `cloud-gateway/lib/rdc-gateway.ts` uses `makeBoundWakeChannel`.
- After successful D1 enqueue, notify only the paired device. Relay `/device/poll` waits on optional private DO signal instead of the next 500ms sweep, then still runs conditional D1 claim.
- After authoritative D1 result completion, notify only the original operation ID. The waiting cloud request re-reads D1 before returning the retained result.
- No binding, failed signal or lost signal falls back to previous bounded polls. No tool arguments, content, key bytes or result text enter the DO, and the wake channel never authorizes or executes an operation. Duplicate request/result identities never wake again.
- The DO has short-lived waiters, timeout and abort cleanup. No generic external endpoint or shared OS control is provided.

## Owner-controlled staging requirement
Before this source can improve real RDC, the owner-private host must support a same-Worker Durable Object namespace and protected rollback. The exported class is `RDCWakeSignal` in `worker/index.ts`. Add exactly one **private** binding named `RDC_WAKE_CHANNEL`, with class_name `RDCWakeSignal`, to a compatible isolated Site staging version. Use an SQLite-backed namespace. In a new Wrangler configuration with declarative exports, the conceptual fields are:

```json
{
  "durable_objects": {
    "bindings": [{"name": "RDC_WAKE_CHANNEL", "class_name": "RDCWakeSignal"}]
  },
  "exports": {
    "RDCWakeSignal": {"type": "durable-object", "storage": "sqlite"}
  }
}
```

Existing Workers using legacy migrations should instead add a unique `new_sqlite_classes` migration, not both configuration forms. This example is NOT a completed configuration or a deployment. The ChatGPT private Sites hosting plane may have additional restrictions and could require a separate compatible service. A source export alone does not install the binding or activate event delivery.

Official docs: https://developers.cloudflare.com/workers/wrangler/configuration/ and https://developers.cloudflare.com/changelog/post/2026-07-09-restrict-new-kv-backed-namespaces/

## Verification gates
1. Record source SHA and exact isolated branch, no owner-worktree modifications.
2. Run Node gateway/DO tests, Python worker suite, TypeScript build and platform CI; keep warnings/skips explicit.
3. Verify private staging DO binding is actually present and the exported class is deployed before timing it. Missing binding must remain functional, with no increased D1 query count.
4. Measure DO invocation charges, idle duration, queue wait, claim-to-completion and host response, with at least 30 balanced A/B trials per route on the same device. Include p50/p95/p99, failed calls and exact output verification.
5. Combine with the separately held gateway_busy capacity repair (PR #3), preserve protected owner-private rollback Site, mutation recovery and original plugin App identity.
6. Only after authorized deployment, compare RDC against DC using the same terminal, coding, browser and file work. Claim 2x superiority only if measured.

## Current outstanding limitations
The source branch is not the installed v16 worker/Site. Hosted Site bindings/rollback version have not been read back, the capacity fix is unactivated, and real host-level performance superiority is OPEN. Floating preview cleanup is fourth priority and remains separately unverified. No API key was read or sent during this implementation.
