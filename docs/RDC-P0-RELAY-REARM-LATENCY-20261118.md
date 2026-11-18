# RDC P0 relay rearm latency qualification

Date: November 18, 2026
Source branch: perf/rdc-relay-idle-credit-20261118
Base: integration/rdc-speed-capacity-20261118 at f35a807
Status: source-only, NOT deployed to the owner worker or private Site.

## Root cause

The live relay in rdc/relay.py used a minimum poll_delay sleep after every
empty authenticated claim poll, even when the server's bounded long-poll request
had already waited ten seconds. For the normal poll_after_ms=250, a ten-second
wait would be followed by an unnecessary 250 ms client-side gap before the next
claim. This makes the relay unavailable to claim new queued work during that
gap, even if the gateway has just admitted a new request.

## Change

The new helper _idle_poll_sleep credits total elapsed gateway long-poll time
against max(poll_delay, idle_delay), never letting the resulting local delay
fall below zero. Once the server wait itself meets or exceeds the enforced
backoff, the relay re-arms the next authenticated claim immediately. An
immediate empty response still enforces the server minimum plus exponential
idle backoff. The change only schedules the next read-only claim; it never
reissues an already claimed worker mutation.

Examples from verified virtual-clock tests:
- Before: 10,000 ms genuine long poll + 250 ms additional local sleep
- Candidate: 10,000 ms genuine long poll + 0 ms extra sleep
- Saved idle gap: 250 ms (100% of that redundant extra gap) in this
  artificial timing scenario, NOT a verified overall RDC latency improvement
- Immediate empty replies: existing 250, 500, 1000, 2000, 4000, 5000 ms
  bounded backoff sequence preserved, preventing a high-rate poll spin.

## Verified source tests

1. Red: explicit helper test failed before _idle_poll_sleep existed.
2. Green: focused virtual-clock tests pass, checking long poll gap 0 and
   preserving immediate empty-response backoff and work-claim identity.
3. Full connected RDC Python regression:
   487 tests run, 43 skipped, zero failures in 129.329 seconds.
4. Isolated local Cloudflare-compatible Miniflare Durable Object smoke,
   through the real RDC connected tool, verified queue hint, completion
   hint, and cached late completion via the source RDCWakeSignal class.
   This used a disposable local workerd/DO namespace, not the private Site.
   The local workerd only supports compatibility dates through 2026-05-22,
   so the disposable test used that date. All three signals returned true.
   Local workerd timings are not production speed evidence.

## Owner's mandatory acceptance gates remain OPEN

The five goals are still live terminal median <=800 ms, gateway pickup <=50 ms,
claim-to-result <=150 ms, local notification <=1 ms, and one cloud request for
coding discovery plus selected file read within <=800 ms. The source-only
optimization proves none of those production gates until the protected new
gateway and matching worker have been deployed, with actual Site version and
rollback readback, and >=30 correct individual live observations per metric.

Use Remote Desktop Commander for authoring and RDC only for live verification.
Preserve all device credentials, D1/R2 history, pending mutations, owner input,
and unrelated TOC work. No scheduled tasks or monitoring.
