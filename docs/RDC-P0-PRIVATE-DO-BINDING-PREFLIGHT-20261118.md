# RDC private wake binding release preflight

Date: 2026-11-18
Branch: perf/rdc-wake-binding-preflight-20261118
Base: combined draft PR #12 at f35a807
Current state: **SOURCE ONLY. LIVE SITE UNCHANGED.**

## Exact opt-in

The Cloudflare/Vinext gateway build defaults to the original binding surface:
D1 DB, R2 BUCKET and no Durable Object. A new helper in
cloud-gateway/scripts/wake-bindings.mjs requires the exact build-time variable
RDC_ENABLE_WAKE_BINDING=1 before adding the single private DO binding
RDC_WAKE_CHANNEL, class RDCWakeSignal, with migration tag
rdc-wake-sqlite-v1 and new_sqlite_classes RDCWakeSignal.

The DO class remains exported from worker/index.ts and has no public route.
Wake hints carry only device/operation identifiers. The existing conditional
D1 claim remains authoritative and a lost hint falls back to bounded polling.

## Verified build gates

With matching installed dependencies from the existing local build cache,
both npm run build modes completed successfully and the resulting generated
dist/server/wrangler.json values were independently read and checked.
- OFF/default: zero DO bindings, zero DO migrations, DB and BUCKET intact
- ON/explicit: exactly one RDC_WAKE_CHANNEL binding to RDCWakeSignal and
  exactly one SQLite class migration, with DB and BUCKET unchanged
- TypeScript noEmit: exit 0
- ESLint: exit 0, one existing image warning
- Node gateway suite: 105 tests passed, zero failures via actual RDC
- No private Site deployment, D1 migration, R2 write, worker restart or
  credential disclosure was performed

## Mandatory release blockers

Do not enable the opt-in DO binding or activate the fast D1-inline writer until
the SAME owner-private Site project and its exact release history have been
read back. A verified, protected, inactive rollback-compatible version must
exist first. The historical v16 gateway reader cannot recover new D1-inline
result rows. Preserve every D1 record, R2 result, owner grant, idempotent
mutation and private audience.

Activation requires authenticated access to the existing private ChatGPT Site
deployment/version manager. The available RDC and Remote Desktop Commander
tools cannot currently publish or read back a Site version ID, bind
RDC_WAKE_CHANNEL on that Site or create its protected inactive rollback.
A local Vite build, source export, GitHub push or Plugin Creator skill update
does not supply that control.

After approved owner-host deployment, independently confirm the Site version,
worker version and source SHA, then collect at least 30 correct live timings
for each locked speed acceptance metric: terminal <=800 ms, gateway pickup
<=50 ms, claim-to-result <=150 ms, local notification <=1 ms, and coding
discovery/read in exactly one cloud call with <=800 ms median. Any missing
live evidence or gateway_busy makes completion FAIL. Do not use scheduled
tasks, alerts or silent retries for deployment.
