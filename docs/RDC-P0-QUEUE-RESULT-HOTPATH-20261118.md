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
- **First-time request-key lookup:** attempt the original D1 conditional
  INSERT before any separate SELECT of the request key. Healthy new operations
  remove that duplicate-key database roundtrip. A failed INSERT checks the
  exact original request key and validates its SHA-256 digest before any
  retention cleanup or bounded retry. A request whose old key belongs to
  different arguments fails 409; a replayed/offline/retained original recovers
  the identical original status and identity, never invokes a second worker
  action. Actual live Cloudflare speed has not yet been measured.
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

## Further P0 transport savings in this source revision

- **One-step new admission:** the original protected D1 conditional INSERT
  is attempted before a duplicate-key lookup. A healthy new request removes
  one D1 SELECT. When admission is refused, the gateway recovers an original
  same-key operation first, checks its SHA-256, and then applies bounded
  cleanup/retry only when no matching original exists. Key conflicts still
  reject mismatched arguments. An offline duplicate retains its original
  operation identity and never redispatches.
- **One-step small result commit:** a standard inline result at most 8192
  bytes is validated and written using a single D1 conditional UPDATE. The
  SQL predicate checks the immutable claim_id and request SHA-256, original
  state, and absence of a prior result. Invalid claims cannot store bytes,
  and duplicate/conflicting outcomes fall back to original-row recovery.
  Preview TTLs are chosen from the original stored tool name within the
  same statement. R2-backed large results and backward-compatible rollback
  writers retain their prior guarded flow. Completion hint only follows
  a successfully committed original result. This removes the preliminary
  original-row SELECT from successful small result uploads.
- **Batched first queue pickup:** on a real claim poll, supported D1
  bindings batch device heartbeat and first conditional D1 claim into a
  single atomic database request, with the same authoritative result row.
  Adapters without batch retain the two-step guarded fallback, and later
  empty long-poll retries keep the existing conditional claim procedure.
  No UI preview, worker approval, mutation identity or retained data is
  bypassed. Cloudflare D1 supports batch according to the installed
  workers-types interface; production Site compatibility remains unverified.

## Executed red-green verification

- Queue/completion pre-registration race tests failed before the fix.
- Queue fast-claim/heartbeat tests failed before the fix.
- All were independently checked via the actual connected RDC worker.
- 100 gateway/acceptance tests passed, zero failures after the changes.
- Existing retention/TTL/rollback test checks are explicitly performed on
  the idle PRIMARY claiming lane rather than a heartbeat-only no-work lane.
- Source-only changes have **not** reduced the measured 2,726 ms current v16
  terminal median. Production gateway_busy can recur until the source
  capacity fix is deployed, and even after deployment if protected journal
  entries occupy all slots.
- 800ms terminal, 50ms queue pickup, 150ms claim-to-result, 1ms notification,
  one-request/800ms coding remain **all open** for live acceptance.

## Additional validation and rejected experiment

- Latest source-only worker gateway contract suite: **100/100 passed** via
  actual connected RDC, including two new duplicate recovery, two fast result
  admission/forgery contracts, and batch claim/fallback tests.
- Full Python regression suite: **486 run, 43 skipped, zero failures**.
- Production vinext build, TypeScript noEmit and ESLint all exit **0** on the
  iMac using existing matching locally installed dependencies. ESLint retains
  one pre-existing image optimization warning. The temporary dependency
  copy is removed after verification.
- Compared five separate database usage scalar scans to one merged scan on
  1,900 in-memory SQLite rows with 500 matched trials. Local p50 was
  **0.31571ms old vs 0.31631ms candidate**. The candidate did not improve
  local median; this experimental change was discarded rather than claimed
  as a live win. It was never deployed.
- A separate aggregate-only **read-only** observation of the local relay
  journal found **10,008 delivered operations** across November 15 to 18,
  with **1,690 created in the latest 24 hours** at measurement. The journal
  includes older retained identities. This does not reveal the owner-private
  Site's D1 record count and does not authorize deleting mutation identities
  or R2 objects. The production D1 journal uses maxOperations 2,000.

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
