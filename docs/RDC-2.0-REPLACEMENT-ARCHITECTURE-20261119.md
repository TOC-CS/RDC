# RDC 2.0: clean replacement architecture and regression gates

Date: 2026-11-19
Owner: TOC Ministries
Status: CLEAN V2 PROTOCOL AND BOUNDED EVENT BROKER IMPLEMENTED; replacement NOT deployed.
Source worktree: feature/rdc-2.0-rebuild-20261119
Baseline: 3371045

## Product contract

Build a significantly faster replacement for current Remote Desktop Commander (RDC), preserving authorized iMac worker capabilities, existing private ChatGPT App identity, ownership checks, user permissions, durable jobs, no-replay behavior, browser support, coding tools, preview isolation, and cross-platform Windows/macOS/Linux compatibility. Terminal, file, coding, and browser operations are equally important; speed is priority 1, security and reliability priority 2, expanded tools priority 3, floating preview priority 4.

## Replace components rather than stack patches

1. **Transport v2:** one authenticated, low-latency, long-lived event channel for device wake and result notification. The server-side journal retains the original operation ID and same-owner authorization; event messages are hints containing no payloads, secrets or arguments. On lost events, reconcile by original ID from authoritative storage. No duplicate mutations.
2. **Gateway v2:** minimize request hops; one authorization-bound durable admission, indexed queue claim, atomic short-result commits, and one authenticated connection-state read. Bound concurrency and reject overload predictably. Separate the control plane from payload transport.
3. **Worker v2:** persistent authenticated agent session, warm process/control connections, bounded concurrent read-only lane, and strictly serialized or idempotency-controlled mutation lane. Do not weaken approval or sandbox rules for speed.
4. **Coding/browser v2:** atomic source-discovery plus selected-file read in one cloud call; bulk safe file updates; persistent browser sessions with observation-scoped handles and controlled batch interactions. Reject stale handles and unauthorized paths.
5. **Release v2:** explicit version compatibility handshake for App, Site, worker, journal, and wake channel. Stage a protected dual-format rollback before introducing inline-only results. Atomic activation via the EXISTING private Site route only after readback confirms user binding and rollback.

## Mandatory performance gates

Require 30+ unique correct live samples and no gateway_busy per metric:
- Terminal median <=800 ms from connected ChatGPT tool invocation to correct output.
- Queue pickup median <=50 ms.
- Claim-to-result median <=150 ms.
- Local notification median <=1 ms.
- Source discovery plus selected-file read <=800 ms with exactly one cloud request.

Compare terminal, files, coding, browser and batch workflows against Desktop Commander using 30 matched pairs with alternating order; report p50, p95, p99, errors, data correctness and CPU/RAM usage.

## Isolated hostile regression environment

Test-only directory: ../RDC-2.0-QA (SIBLING of source worktree, never included in packages).
- Burst fanout, concurrent result hints and cancellation.
- Malformed inputs, invalid operation IDs and cross-owner denial.
- Journal saturation, lost acknowledgments, stale/duplicate responses and no-replay.
- Simulated network disruption, timeouts, process death, reconnect, partial writes and rollback mismatch.
- Permission escape attempts only in disposable synthetic fixtures.
- 3-platform CI, full gateway contracts, full worker contracts, default and wake-enabled builds.
- Verify no test harness files, synthetic credentials, hostile payloads or diagnostic fault injection are bundled in the release.

Hostile tests may exercise clean production interfaces. Fault injection must be owned exclusively by isolated QA and never shipped as a runtime flag or production dependency.

## Coordination and scope

Superpowers 7.0.1 available on the authorized iMac: brainstorming, writing-plans, TDD, systematic debugging, worktrees and verification-before-completion. Atlas Build Bus currently implements a synthetic local SQLite coordination core. Its docs explicitly say there are NO authenticated ChatGPT session adapters, no independent Atlas reviewer identity and no running live communications daemon. Do not claim real AI swarm dispatch or Dot approval from this local library. Autonomous AI workers may be used only if actual supported authenticated dispatch and isolated ownership are verified; deterministic concurrent test processes are not AI agents.

Scope independent work: Transport and notifications; Gateway authorization/queue; Worker process and coding tools; QA benchmarks/security; integration and release. One owner per file and final sequential integration. Keep BandMates, TOC site, presentation agents, live worker, existing App/Site and old RDC branch untouched.

## Rollout sequence

- Phase A: preserve v1 live system; snapshot source/deployed versions; independent hostile regression and root-cause benchmarks. OPEN.
- Phase B: implement new transport and gateway behind an opt-in v2 protocol in isolated source, with red-green unit tests. OPEN.
- Phase C: implement worker/coding/browser adapters and compatibility bridge with full regression suite. OPEN.
- Phase D: stage on isolated local service and validate against Desktop Commander, including adversarial tests. OPEN.
- Phase E: protected private Site deployment/rollback proof, exact worker version readback, 30+ live samples for all five targets, then controlled replacement. BLOCKED until release authority and real evidence.

Release is incomplete until every safety and speed gate passes. Existing RDC keeps running.

## Current clean 2.0 implementation checkpoint

- cloud-gateway/lib/rdc-v2-protocol.mjs: strict ID-only versioned event protocol.
- cloud-gateway/lib/rdc-v2-broker.mjs: bounded per-device notification sequencer with listener cancellation, overload rejection, short-lived event records and explicit gap reporting for durable reconciliation.
- 122/122 Node gateway and V2 regression tests passed.
- External QA: 12,000 invalid frames rejected, 1,000 valid frames round-tripped, 1,000 simultaneous broker listeners, 700 listener cancellations and 3,000 burst events, with no failed scenarios.
- No v2 component is connected to the deployed Site or the running worker. No production swap has taken place.

## Required floating preview acceptance: job-bound auto-clear

- RDC 2.0 must support compact host-owned floating/PiP views inside the AI workflow when the exact host advertises and returns that mode. Do not create a separate OS-wide window, steal window focus or claim host support from a simulated request.
- The existing rdc_preview_open accepts an optional exact durable job_id with required session_id to explicitly bind one job to one visual source. The worker verifies its job record and returns only minimal state; no command, arguments, output or hidden path is included.
- rdc_preview_frame with the same optional job ID returns current job status inside the existing frame response, avoiding a second cloud status request. On a confirmed completed, failed, cancelled or timed_out job, it skips another screenshot and returns task.complete=true with exact job, device and session IDs.
- The renderer verifies all three identifiers before clearing the selected view. It hides its presentation, stops its timer, then sends the MCP Apps ui/notifications/request-teardown only if the host confirmed PiP. A host may ignore teardown, so hidden presentation is the fallback.
- interrupted is uncertain and never automatically clears the viewer. Wrong-job or wrong-source completion cannot dismiss the selected view. Late old results cannot override a new explicit job.
- Hiding, closing or detaching a viewer never cancels the job or closes the visual source. Host-specific movement, drag behavior and actual teardown require live acceptance.

**Limit:** Current auto-clear applies only to explicitly bound RDC durable jobs. Browser or other visual workflows lack a proven generic task-completion signal. Generic completion lifecycle, multiple host floating views and real ChatGPT/Codex window behavior remain OPEN requirements.

**Source QA:** 16 worker preview tests, 33 MCP Apps host contracts, 111 gateway tests, and 407 external hostile lifecycle cases passed. Source and embedded UI have been synchronized into gateway assets. A complete exact-revision regression rerun remains required. Live speed targets are OPEN pending authenticated measurements.
