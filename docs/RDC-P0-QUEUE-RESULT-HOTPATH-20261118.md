# RDC speed-first gateway fast-path qualification

Date: 2026-11-18
Branch: integration/rdc-speed-capacity-20261118
Release: source-only candidate, **not yet deployed to the owner's private Site**

## New measured old production baseline, host verification

30 sequential authenticated HTTPS heartbeat-only calls from the paired iMac
to the existing private Site v16 endpoint /device/poll with claim=false,
with 2 uncounted warmups; credentials loaded privately by the active worker
without printing or sending them to the AI host.

- 30/30 completed with valid authenticated responses.
- Median: **310.744 ms**, p95 nearest-rank **915.545 ms**,
  p99 **1,048.673 ms**, min **283.999 ms**, max **1,048.673 ms**.
- No operation claimed. This includes private edge access, round-trip HTTPS,
  heartbeat DB update, and v16 retention cleanup. It is **not** the ChatGPT
  terminal latency, a new release speed claim, or a post-deployment comparison.
- Repro on the paired worker, using actual connected RDC tool:
  python benchmarks/rdc_live_gateway_heartbeat.py --samples 30
  using the on-device private relay configuration.
  Never read the configuration text or reveal its credentials in reports.

## Source changes motivated by the actual expensive heartbeat/pickup

- **Queue pickup:** after authenticated heartbeat update, attempt the original
  conditional D1 queued claim FIRST. The claim query explicitly excludes
  expired rows. A successfully claimed operation returns immediately without
  the old four-query-plus-R2 retention cleanup sweep. A heartbeat-only
  request avoids the sweep, since it does not claim work.
- **Successful cloud dispatch:** the worker liveness condition is checked
  inside the same conditional D1 INSERT as the queue/backlog/byte limits. On
  a successful admission, one standalone SELECT last_seen_ms query is removed.
  If admission fails, a separate read distinguishes device_offline from
  gateway_busy before any bounded recovery. The device state and mutation
  identity are checked atomically at the original D1 admission boundary.
- **Healthy first-time MCP dispatch:** retain the original D1 admission with
  atomic worker liveness, backlog, size and mutation identity checks, but skip
  periodic retention cleanup before a successful admission. On a failed
  admission, run the original bounded cleanup and retry the exact SAME
  operation ID/arguments. Offline failures still run cleanup. Duplicate
  operations with overdue queued/claimed/completed TTL run cleanup before
  returning their original outcome. Completed result readback refuses
  expired data even if asynchronous retirement has not yet purged its bytes.
  No repeated local worker invocation occurs.
- **Bounded retention:** on an empty primary claiming poll, run the original
  clean(env) before returning. Ordinary authorized tool dispatch and
  on-demand recovery still perform their existing cleanup. Expired rows
  cannot be claimed and the mutation/no-replay guard is unchanged.
- **D1 notify-before-wait race:** a DO signal arriving in the narrow gap
  between D1 check and relay waiter registration is held as a one-shot hint
  for at most 750ms, device-local only. Consumed once. A missed/evicted
  hint falls back to the original bounded D1 poll.
- **D1 completion notify-before-wait race:** the DO retains at most 256
  recent completion UUIDs for 5s; a late waiter receives an immediate hint
  to recheck the original durable D1 completion. No result bytes, secrets,
  arguments or source are placed in this cache; original D1 record remains
  authoritative. Lost/expired hints still have the normal timer fallback.

## Executed red-green verification

- Queue/completion pre-registration race tests failed before the fix.
- Queue fast-claim/heartbeat tests failed before the fix.
- All were independently checked via the actual connected RDC worker.
- 94 gateway/acceptance tests passed, zero failures after the changes.
- Existing retention/TTL/rollback test checks are explicitly performed on
  the idle PRIMARY claiming lane rather than a heartbeat-only no-work lane.
- Source-only changes have **not** reduced the measured 2,726 ms current v16
  terminal median. Production gateway_busy can recur until the source
  capacity fix is deployed, and even after deployment if protected journal
  entries occupy all slots.
- 800ms terminal, 50ms queue pickup, 150ms claim-to-result, 1ms notification,
  one-request/800ms coding remain **all open** for live acceptance.

## Remaining activation and proof

Require protected compatible private Site rollback and owner-supported
Cloudflare Durable Object namespace RDC_WAKE_CHANNEL before activating
the new wake hints. No agent may infer site deployment or a new worker version
from a GitHub commit. Run at least 30 correct, timed live samples for each
target, preserve result and mutation identities, report p50/p95/p99 and
gateway_busy and verify the exact deployed release. Never claim a local
timing simulation or CI success is the required final speed qualification.

All builds use Remote Desktop Commander as directed. RDC is reserved for
actual regression tests and connected live verification. No scheduled tasks
or watch alerts.
