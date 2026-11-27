# RDC 2.0 compiled Site binding and migration guard

Date: 2026-11-19. Scope: offline, owner-authorized isolated worktree.
Status: candidate artifact preflight only. Live Site and protected rollback unverified.

## Release-risk finding

The prior regression suite checked the JavaScript binding generator, not the
actual generated `dist/server/wrangler.json` output or the compiled
`dist/server/index.js` bytes. A source-only test could pass while the
deployable artifact omitted its Durable Object namespace or changed the legacy
D1/R2 surface. This guard compares separate fully compiled opt-out and opt-in
artifacts and pins the candidate bundle digest. Its PASS is deliberately NOT a
release, archive activation, hosting version, or performance approval.

## Fail-closed contract

`cloud-gateway/scripts/rdc2-compiled-site-guard.mjs` expects an exact
baseline `wrangler.json`, candidate `wrangler.json`, candidate `index.js`
and an independently recorded SHA-256. It permits precisely one additive
Durable Object `RDC2_DEVICE` with exported class `RDC2DeviceActor` and one
SQLite migration `rdc2-device-sqlite-v1`. Every other emitted configuration
field must match the baseline, including existing migration history, D1, R2,
assets, services, routes, compatibility and output options. Both artifacts
must retain legacy DB and BUCKET bindings. Credentials in cleartext vars,
public routes, workers.dev exposure, or even dormant runtime/archive
activation variables fail the check. Bundle SHA mismatch, absent class
or missing transport route also fail.

A matching baseline and candidate with object-form public routes or malformed
`workers_dev` also fail. The candidate may preserve the previous wake binding
and migration unchanged. The report always sets `releaseApproved=false`,
`hostedProtectedVersionVerified=false` and
`archiveEnablementApproved=false`, regardless of a passing artifact check.

## Evidence and methodology

First test run failed because the guard module did not exist. Seven focused
tests then passed; an additional regression demonstrated malformed public
routing could pass in the first implementation. The guard was hardened;
nine focused tests and the complete Node suite passed. Rebuilt the isolated
Vinext Site twice with `RDC_ENABLE_V2_BINDING=0` and then `=1`. The compiled
OFF manifest had no DO binding. ON had exactly one new DO and migration.
Legacy DB/R2 and no public routes were unchanged; runtime remained disabled.
Candidate index.js SHA-256 was pinned, and six separate local adversarial
CLI processes verified good/bad generated artifacts. None contacted a cloud
deploy endpoint or changed production.

## Release gate still open

Obtain authoritative read-only existing owner-private Site version history,
binding metadata and stable project identity through the correct protected
Site management control. Validate deployed immutable worker hashes and
protected inactive rollback, with archived-operation readback and owner
isolation, before enabling any V2 runtime or archive writes. Only then use a
protected hosted canary and collect at least 30 correct live ChatGPT-connected
samples for each latency gate and matched RDC-vs-DC flows. Preserve the
existing production Site until all independent gates pass.

The local off/on build comparison, SHA and fast localhost tests must never be
advertised as hosted version verification or proof of production speed.
