# RDC P0 atomic owner authorization and dispatch qualification

Date: 2026-11-18
Source: isolated perf/rdc-owner-admission-20261118 branch
Base: combined speed/capacity integration PR #12 at f35a807
Status: source-only, not deployed to the owner-private ChatGPT Site.

## Objective

On the original gateway, a healthy newly submitted worker tool request
performs an authenticated pinned-owner D1 SELECT, followed by a separate
conditional D1 INSERT for queue admission. Each roundtrip incurs additional
Cloudflare database transport latency.

This candidate checks the exact pinned owner principal within the SAME D1
conditional INSERT as device liveness, backlog, byte bounds and immutable
request identity. A successfully admitted first-time source tool therefore
saves the extra standalone SELECT. Every failed admission performs the
original authoritative owner check before any recovery or housekeeping.

## Security preserved

- Missing authenticated user ID is denied before any D1 insertion.
- An unrecognized principal cannot insert, claim, recover or alter a worker
  operation, even if the device is online.
- First-ever owner enrollment still follows the existing owner-private
  bootstrap policy. The identity is pinned in gateway_owner and cannot be
  transferred by future callers.
- Exact repeated request IDs recover the original operation and stored result,
  with request SHA-256 mismatch rejected as a conflict, never replayed.
- Malformed arguments from an unrecognized visitor are still denied with
  owner_mismatch before validation information, matching the original policy.
- On a failed fast dispatch, the original owner read is required even when
  the worker returns an error. Other owner-only tools retain the old path.
- Gateway-owned connection, diagnostics, chat status and recovery retain
  explicit owner verification even if a future worker catalog accidentally
  duplicates a built-in gateway tool name.
- This change requires no new permissions, secrets, tables, migrations,
  Cloudflare bindings, public endpoints, or worker input access.

## Verification

Red-green cases:
- The healthy pinned-owner flow originally incurred one extra D1 SELECT;
  new test failed before source modification.
- New successful route contains pinned-owner equality in atomic D1 INSERT.
- Unauthorized principal, initial enrollment, duplicate request, mismatched
  arguments, malformed request precedence all have passing regression cases.
- Node gateway suite 107/107 passed through actual connected RDC.
- Full Python suite: 486 tests run, 43 skipped, zero failures via the
  actual connected RDC worker. Production build, TypeScript and lint returned
  exit 0 with one existing image warning after the final owner-only
  catalog collision guard was added.
  Hosted CI and production deployment retain separate gates.

The owner's five live latency acceptance goals remain 0/5 verified until
a matching protected Site version is activated with an independent rollback
and at least 30 real timed samples per metric. The old status-only live host
30-call baseline was p50 683.5ms / p95 972ms, not an end-to-end terminal
measurement. No local test justifies a claim that the 800ms terminal target
has been achieved.
