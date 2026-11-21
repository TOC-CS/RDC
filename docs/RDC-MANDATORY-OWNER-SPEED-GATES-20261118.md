# RDC mandatory owner speed acceptance

Date: 2026-11-18
Status: **OPEN / NOT VERIFIED COMPLETE**
Project: TOC-CS/RDC, connected ChatGPT app, private Site and worker.

**Updated owner testing rule (November 19, 2026):** Every RDC testing campaign has a hard maximum of **100 total checks across all categories and platforms**. See `docs/RDC-TEST-100-EXECUTION-POLICY.md`. The required 30 correct real-live samples for EACH of the five metrics remain mandatory. Collect these in separately bounded campaigns, never launch over 100 at once, and leave the release OPEN while evidence is incomplete. An enabled recurring RDC development task may resume bounded work, but its existence does not prove continuous execution or live speed acceptance.

## Locked acceptance goals

| Metric | Previous RDC baseline | Mandatory LIVE median | Relative latency reduction | Speed multiplier |
| --- | ---: | ---: | ---: | ---: |
| Live terminal end-to-end | ~3,400 ms | **at most 800 ms** | **76.5%** | **4.25x** |
| Gateway queue pickup | 311 ms | **at most 50 ms** | **83.9%** | **6.22x** |
| Claim-to-result | 678 ms | **at most 150 ms** | **77.9%** | **4.52x** |
| Local notification | 501.591 ms (timer) | **at most 1 ms** | **99.8%** | **501.6x** |
| Coding discovery plus selected file read | 2 cloud requests | **exactly 1 request and at most 800 ms** | **50% fewer requests** | Live time baseline required |

Reference reductions/speedups are rounded from the stated historical baseline
and goal. The original connected host 30-call baseline measured terminal median
3,178 ms; the ~3,400 ms owner baseline is a rounded reference, not a new run.
A terminal median below 900 ms but above 800 ms FAILS.

## Release must remain OPEN until all five pass

1. Read back the exact deployed Git revision, connected worker version, current
   owner-private ChatGPT Site version, real provisioned RDC_WAKE_CHANNEL binding,
   and protected rollback. Do not mutate production without proven compatibility.
2. Record at least 30 unique real live production timing samples for EACH metric,
   including actual duration, success, output correctness, gateway_busy errors,
   matching source revision, original evidence, and p50/p95/p99. Retain exact
   request identities without exposing payloads, secrets or private content.
   RDC V2 owner phase telemetry now exposes validSampleCount,
   invalidSampleCount, and timingStatus per sample. A wall-clock reversal yields
   timingStatus='invalid_clock_order' with null phase times, never a synthetic
   zero-ms success. Exclude and remeasure invalid samples, and fail the release
   gate if they enter a receipt. Durable SQLite timestamps resolve to 1 ms;
   those timestamps alone cannot prove the <=1 ms notification target.
3. Each coding sample must discover source and read selected matching file contents
   in exactly one authorized cloud request, with complete correct results.
4. Any wrong output, non-live measurement, missing record, duplicate ID, missing
   rollback, unavailable binding, version mismatch, gateway_busy, or median above
   an owner's hard target FAILS. Source unit tests or Cloudflare DO simulations do
   not count as measured live success.
5. Run the fail-closed policy checker:

       node benchmarks/rdc_speed_acceptance.mjs LIVE-RECEIPT.json

   Exit 0 means every policy condition passed on that receipt. Exit 1 keeps the
   gate OPEN. Independently inspect the actual host and original evidence
   references even after an exit 0 receipt. NO receipt exits 1.

## Required receipt schema

This is a structural example only, with a deliberately INVALID one-item sample
and a zero duration. Never use this example as performance evidence.

~~~json
{
  "schemaVersion": 1,
  "environment": {
    "mode": "production-live",
    "host": "ChatGPT-connected-RDC",
    "gitRevision": "EXACT_DEPLOYED_SHA",
    "siteVersion": "READ_FROM_LIVE_SITE",
    "workerVersion": "READ_FROM_LIVE_WORKER",
    "wakeBindingVerified": true,
    "rollbackVerified": true
  },
  "metrics": {
    "live_terminal": {
      "origin": "production-live",
      "measuredRevision": "EXACT_DEPLOYED_SHA",
      "evidenceRef": "REAL_INDEPENDENT_LIVE_RECEIPT_REFERENCE",
      "samples": [
        {
          "requestId": "UNIQUE_REAL_REQUEST_ID",
          "latencyMs": 0,
          "success": true,
          "outputCorrect": true,
          "gatewayBusy": false
        }
      ]
    }
  }
}
~~~

Other required metric keys: gateway_queue_pickup, claim_to_result,
local_notification, coding_discovery_read. Coding sample records additionally
need cloudRequests=1. Every metric requires 30 or more unique timed samples and
matching observed deployed source revision.

## Verified work and outstanding operational blockers

The combined integration candidate in draft PR #12 introduced coding context,
event-driven DO hints and retained journal capacity recovery. The candidate
passed 12 hosted checks in two CI runs across macOS, Ubuntu and Windows. That
source remains UNDEPLOYED and production RDC remains on the older release.
The live Site binding, protected rollback and full live speed acceptance are
OPEN. The source guard's red-green policy tests verify a contract, NOT the
user's real target performance. The active project remains speed priority,
then reliability/security/hardening, then capability expansion beyond DC,
then external floating preview auto-clear.

No subscription models or AI provider keys are required by the policy. Follow
Superpowers TDD, systematic debugging, isolated branch/worktree, measured
performance, verification-before-completion and no-replay policies. Do not
use background scheduled tasks, hourly monitoring or alerts for this work.
