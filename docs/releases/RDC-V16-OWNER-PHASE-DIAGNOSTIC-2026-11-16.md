# RDC live v16 owner-only terminal timing diagnostic

**Date:** November 16, 2026, America/Chicago
**Environment:** Existing owner-private live RDC Site v16. Read-only diagnostic and connection calls, plus three user-authorized, harmless terminal markers. No Site release, D1 migration, worker restart, BandMates interaction, or replay of an uncertain command.

## Approach and sample qualification
- Used the existing authenticated RDC App connection for owner-only `rdc_operation_status({diagnostics:true})`. The selected owner account and device were retained across all calls.
- Read the existing local worker relay journal SQLite in **read-only mode**, querying only previously delivered terminal result markers. Retrieved matching operation IDs internally to ask the authenticated gateway for its timing fields. Full IDs, worker request arguments, credentials and result bodies were excluded from this report.
- Used the **12 most recent owner-accessible completed `rdc_job_run`** operations, with 12 candidates examined, 12 confirmed and zero access denials or incomplete records.
- The gateway returned elapsed queue-to-claim and claim-to-completion intervals. Total service is their sum. p50 is the median of sorted values; p95 is the nearest-rank 95th percentile, computed on the 12 samples. This does not measure the full ChatGPT host/connector round trip.

## Results

| Phase | p50 (ms) | p95 (ms) | Min (ms) | Max (ms) |
|:--|--:|--:|--:|--:|
| Gateway queued to worker claim | 311 | 596 | 0 | 596 |
| Claimed to stored gateway result completion | 678 | 1078 | 592 | 1078 |
| Total gateway service, created to completed | 982.5 | 1391 | 734 | 1391 |

The claim-to-completion interval exceeds the pickup interval at the median and p95, so pickup does not dominate the measured gateway phase time for this sample. Claim-to-completion includes worker execution, durable result upload, gateway round-trip and database completion. No data in this sample separates those contributions for every operation.

## Two fresh terminal measurements
Two additional fresh commands were observed from the ChatGPT host to the existing live v16 RDC connection. Both returned exact markers and numeric exit 0.

| Fresh call | Host round trip (ms) | Gateway queue (ms) | Gateway claim to result (ms) | Gateway service total (ms) | Local worker job start delay (ms) | Command execution (ms) | Relay receipt to delivered acknowledgement (ms) |
|:--|--:|--:|--:|--:|--:|--:|--:|
| A | 3897 | 407 | 738 | 1145 | 44 | 4 | 828 |
| B | 3223 | 304 | 651 | 955 | 58 | 5 | 598 |

The first earlier marker was also verified with exit 0; its local relay receipt-to-acknowledgement interval was 1088 ms, gateway queue 313 ms and claim-to-result 1078 ms. A ChatGPT roundtrip time was not retained for that first marker.

These two newer observations leave approximately 2.3 to 2.8 seconds outside the gateway's created-to-completed interval, including host connector handling, requests and responses between host and gateway and any postcompletion delivery. That residual cannot be assigned to one provider without instrumenting the full transport path.

Three separate read-only `rdc_connection_status` calls on the same connection returned in **847, 1069 and 887 ms**, with the device online and no pending operations. These calls use a different request path and are a context baseline, not a decomposition of the terminal roundtrip.

## Findings and safe follow-up
The source includes unactivated v17 optimizations for faster claimed-completion polling and small-result inline storage, which can reduce some R2 traffic. They have passed local regression tests but have **no authorized postdeployment comparative measurements**. Preserve existing v16 and the fixed rollback release gate.

Before claiming an RDC speed advantage over Desktop Commander, complete the protected inactive compatible rollback version, hosted CI on the exact source, Atlas review, explicitly authorized deployment, then collect an alternating A/B benchmark under matched test and time conditions. Instrument host connector durations separately from authenticated gateway queue and claim intervals. Avoid unbounded D1 polling or speculative replays to chase latency.

## Evidence and privacy
Machine-readable numeric-only summary:
`/Users/brandondawson/RDC-Development/checkpoints/rdc-v17-gateway-review-20261116/owner-v16-last12-terminal-phase-summary.json`

The logged report omits full operation IDs, stored commands, results, account principals, tokens and unrelated worker metadata. Only request status and timings were read for the selected operations. The local journal itself was not modified by the timing analysis.
