# RDC 2.0 protected rollback: pinned-source archived-operation readback preflight

Date: 2026-11-19. Scope: isolated development worktree only. Production gate OPEN.

## Safety problem and requirement
RDC 2.0 can atomically retire completed or expired hot journal rows into
`rdc2_tombstones`. Older rollback binaries that only inspect `rdc2_ops`
cannot recognize an already-executed archived request key. After rollback,
such a reader may admit that same original mutation as a fresh operation.

Rollback must preserve the original owner, request key and digest, operation ID,
claim ID, completion hash, expiry semantics and no-replay guarantee. It must
reject foreign owners and altered duplicate payloads. A source file merely
containing the word "tombstone" does not prove that behavior.

## Test-first scope
Add `cloud-gateway/scripts/rdc2-rollback-readback.mjs`, a CLI and pure test
helper. It accepts a local `rdc2-journal.mjs` source file and exact 64-hex
SHA-256. A mismatch fails before evaluating the candidate. Import the exact
checked bytes into an isolated process, seed a synthetic in-memory SQLite
journal with one completed mutation and one expired unclaimed mutation,
sweep and archive both to tombstones, then instantiate the candidate reader
against the persisted state. No real commands, credentials, network calls,
production files or owner identities are involved.

The candidate must prove eight deterministic contracts: exact original IDs
for completed and queued archived requests, duplicate admission with
`reused=true`, expired result bytes withheld, changed request digest denied,
foreign owner denied, fresh unrelated admission accepted, and duplicate
completion recognized without another execution. A failure or missing SHA is
a hard negative receipt. The CLI reports `releaseApproved=false`,
`archiveEnablementApproved=false`, and
`hostedProtectedVersionVerified=false` even when the source passes.

Example:
```sh
node cloud-gateway/scripts/rdc2-rollback-readback.mjs \
  --candidate /absolute/authorized/path/rdc2-journal.mjs \
  --sha256 EXACT_LOCAL_SOURCE_SHA256
```

## Real candidate differentiation, November 19
Offline, exact Git sources were extracted into disposable QA folders:
- `291da0a` candidate SHA-256
  `1f7a57a50e5dd57a0a84a996a66ffdf7caf9a8eb2040afab7751ba4983c3b3dc`:
  readback failed closed (exit 2), no release approval. The pre-tombstone
  reader cannot safely recover original archived operation identity.
- `f35df58` candidate SHA-256
  `4a3359a643ae96379769ba5fd3a51d0cb591176072db8b49c2dfafe43e4e94ac`:
  passed eight source-level readback checks (exit 0). No release approval.

Exact receipts reside under
`~/RDC-Development/workspace/RDC-2.0-QA/rdc2-readback-candidates-20261119/`.

## What this does not prove
Source compatibility does not prove the existence of a protected, inactive,
owner-private hosted version, exact deployed binary checksum, retained Site
project identity, D1/R2/Durable Object migration compatibility, rollback
version selection, drain/recovery, worker compatibility, or ChatGPT speed.
A Site-version-management tool was not available in this run. Nothing is
activated, published, or deployed, and `RDC2_TOMBSTONE_ARCHIVE_ENABLED`
remains disabled outside isolated synthetic testing.

## Release rule
Before changing an owner Site, independently verify the protected candidate
version ID and source/build SHA, both old and new SQLite state readability,
worker rollback protocol, failure and retry behavior, and actual rollback
selection in a protected canary. Preserve all original operation identity
records. Do not use a pre-tombstone reader as rollback after any archives.
Require at least 30 correct live ChatGPT-connected samples per mandatory speed
metric plus paired Desktop Commander baselines before final replacement.
