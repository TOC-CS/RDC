# RDC P0 latency, event-driven wake and completion design

**Status:** Source candidate only. **Priority:** 1 speed, 2 hardening, 3 added capabilities, 4 floating preview auto-clear.
**Design inputs:** 2026-11-17 REA comparison of Desktop Commander 0.3.1 and RDC v16, existing measured ChatGPT tool calls, 2026-11-18 repeated gateway_busy, existing performance worktree and capacity-repair PR #3.

## Objective
RDC must eventually outperform DC by at least 2x on matched real ChatGPT terminal, file, coding and browser workflows with p50 and p95 improvements and no accuracy or safety regressions. The prior 30-round shell baseline was RDC p50 3178 ms and DC p50 1820 ms. Existing 12-phase observations suggest RDC's D1 queue pickup p50 311 ms, claim-to-completion p50 678 ms and gateway total p50 982.5 ms. Host/connector overhead remains unattributed. Do not present synthetic timing as deployed speed.

## Options considered
1. Reduce all D1 poll intervals from 500 to 50 ms: easier, but increases idle D1 traffic about 10x and risks cost and queue contention.
2. **Selected:** optional private per-device Durable Object wake signal to notify the waiting relay after successful durable D1 admission, and to notify the waiting ChatGPT operation after D1 result completion. Keep the original 500 ms polls when the binding is absent, unreachable or loses an event. Never permit the signal to claim work.
3. Replace gateway/relay transport wholesale: highest deployment risk and rollback complexity, reserved for measured follow-up.

## Contract
- `createGateway` accepts optional `wakeChannel` or per-request `wakeChannel(env)` resolver. Absent binding = old D1 long polling, same schema, same results.
- Only successful new D1 admission calls `notify(device_id)`. Duplicate request-key recovery and refused admissions do not signal.
- Relay `/device/poll` may wait for a wake within the existing bounded step; it always claims through the existing conditional D1 SQL.
- Only *after* an authenticated result is committed to D1, call `notifyResult(device_id,operation_id)`. The original host dispatch can await `waitResult` but must re-read D1 before returning.
- All signal methods are best effort, bounded, nonsecret, scoped by the existing paired device, and never authorize work, change owner approvals, replay a mutation or return tool content.
- `RDCWakeSignal` Durable Object supports private POST notify/wait and operation-scoped result notify/wait. No public route, credentials or content. Waiters are short lived and cleaned on signal, timeout, or request abort.
- A lost hint may delay a request by up to the existing poll interval; D1 remains durable. Provisioning of `RDC_WAKE_CHANNEL` binding, migration and protected rollback is a separate owner release step.

## Acceptance, rollout and exclusions
Offline red-green tests must prove instant simulated wake before a 500ms sweep, duplicate/no-admission suppression, backend failure fallback, scope isolation, operation-specific completion, retention of original result IDs and unchanged no-binding behavior. Run all gateway and Python tests plus Windows/macOS/Linux CI; test actual Cloudflare DO and Site build in a private staging version with owner isolation before production. After deployment, alternate >=30 matched real RDC/DC calls per workload and compare p50/p95/p99, total capacity cost and failure rate. Do not touch production v16, existing plugin identity, other owner worktrees, keys, audio/MIDI, browser sessions, or native OS cursor. Resolve the separate gateway_busy admission-capacity PR before sustained speed acceptance.

**Later priorities:** harden D1 cleanup/recovery and authentication; expand bundled coding/browser workflows; allow a task-bound floating preview outside chat where supported, auto-close/clear on task completion without disturbing user focus.
