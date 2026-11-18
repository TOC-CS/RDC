# RDC current live Site v16 speed and capacity diagnostic

Date: 2026-11-18, Chicago
Status: historic live v16 evidence only; new source release has NOT been deployed
Connected worker: 0.1.0a8
Branch source candidate (NOT deployed): 5ff9a68, draft PR #12

## Measured from the actual ChatGPT-connected RDC link

- 12 authenticated rdc_connection_status calls: median 673.5 ms, nearest-rank
  p95 749 ms, 12 of 12 successful. Status does not dispatch a terminal job.
- 14 independent authenticated rdc_job_run terminal echoes: median **2,726 ms**,
  nearest-rank p95 **3,256 ms**, 14 of 14 completed with exact correct output
  and zero command exit errors. Local job start to finish 17 to 22 ms.
- Full host call durations (ms): 3219, 2723, 2670, 2791, 2501, 2729, 2422,
  3134, 2739, 2438, 3256, 3088, 2710, 2579. Values were measured by host
  around real tool calls, excluding model deliberation.
- Attempts numbered 15 through 18 each rejected with gateway_busy and the
  explicit response "No operation was queued." No alternate idempotency keys
  were used to replay those requests. The next connection_status showed
  online=true and pending_operations=0, consistent with retained capacity.
- An independent set of 30 sequential unauthenticated GETs of the owner's
  private Site root from iMac returned HTTP 401 all 30 times, with network
  response p50 94.3 ms and nearest-rank p95 107.0 ms. Authentication denial
  responses DO NOT measure authorized gateway dispatch, nor do they prove the
  origin of host latency.

## Interpretation and next controlled engineering actions

The user's locked **800 ms** terminal median target remains OPEN. The current
14-valid-call median exceeds it by **1,926 ms**, or 70.7% of this sample's
median. The previous longer 30-pair baseline measured 3,178 ms live RDC p50
versus DC 1,820 ms; the owner's accepted rounded baseline is ~3,400 ms.
These runs have different dates/sample sizes and cannot be conflated.

The current v16 gateway uses bounded retention (maxOperations=2000) and
independent 500ms long polling. The integrated source candidate adds optional
DO hints and a narrow capacity retry that reclaims only expired nonmutating
payload-free records. It is NOT established that this patch alone recovers a
journal whose retained entries are recent or protected mutating results.
Do not delete mutating/unknown request IDs, clear worker state, raise limits
without measured D1 cost, or attempt unsafe legacy rollback just to free slots.

Next: independently verify a protected compatible rollback, provision supported
private DO binding, stage/activate source through the owner Site release route,
then collect >=30 fresh successful live samples for every owner-locked metric.
Instrument host connector, D1 enqueue, queue pickup, job execution, result
upload and response phases individually. The branch's executable acceptance
gate stays red until ALL five live metrics are independently verified.

No scheduled monitoring was activated as part of this diagnostic. A separate
hourly task was disabled; connector actions do not expose permanent deletion.
