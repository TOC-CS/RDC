# RDC 2.0 REA Trace and Speed Design
Date: November 20, 2026. Owner speed-only directive. Do not use Atlas Bus or a second implementation owner.

## Source comparison
Desktop Commander shipped 0.3.1: ChatGPT hosted service (internals uninspected) -> paired device Realtime new_call doorbell -> guarded conditional claim -> persistent Node remote-device -> persistent local MCP stdio -> terminal manager -> original durable result -> host. REA 6.9.0 successfully inspected seven selected JS files, 16,614 AST nodes and 239 findings. Most shipped files and hosted server remain outside the semantic trace. Master: ~/RDC-Development/checkpoints/rdc-dc-pipeline-rea-20261117/PIPELINE-TRACE-AND-BENCHMARK-MASTER.md.

RDC V1 ChatGPT deployed: Site v16 -> owner-authenticated D1 queue -> idle 500ms claim probes -> outbound relay polling -> Python MCP worker -> durable job -> result D1/R2 -> ChatGPT host. Three correct matched echo pairs showed RDC p50 2,932ms vs DC p50 1,511ms; local RDC job 89-106ms. Too few samples for acceptance.

RDC V2 isolated, current source: official persistent MCP client -> persistent gateway-connect bridge -> authenticated standalone Python/SQLite journal -> event-driven WebSocket claim_wait -> persistent relay -> local MCP -> durable worker job -> exact result ACK -> client. 30 correct code reads p50 96.775ms, 30 correct terminal calls p50 147.338ms. Isolated, not ChatGPT-hosted.

## Root cause and selected approach
Most live V1 delay is outside local execution. V2 already removes the V1 D1 polling and reuses HTTP/MCP client connections. A Python import-startup change saved only ~1ms and was rejected. Post-result claim credit saved wire messages but regressed median and p95 in 60 interleaved operations and was reverted.

Selected Superpowers approach: root-cause tracing, read-only high-resolution same-process monotonic queue/claim/complete timings for V2 gateway, test-first RED/GREEN, bounded 30-operation isolated verification, then only fix confirmed dominant stages. Avoid adding new network frames or telemetry blocking hot code. Do not infer actual device notification delivery from server-send time or clocks on different machines.

## Required invariants
Retain original owner auth, operation ID, claims, result, idempotency, TTL and no-replay. Metrics include only IDs and durations, never arguments, source content, owner identities, device tokens or result bodies. Bounded 512-entry in-memory history, with null when timing is absent across restart and stable first completion on duplicate. Cross-clock and clock-regression behavior is explicit. Each test and benchmark campaign <=100 total operations. V17 Site activation remains blocked. No public/production activation without TLS, exact release identity, compatibility, verified rollback and 30+ real ChatGPT-connected samples. Final acceptance is five absolute latency goals plus 2x matched Desktop Commander superiority.

## Alternatives
1. Local Python micro-optimizations: rejected; barely measurable.
2. Piggyback next claim after result ACK: rejected due measured median slowdown.
3. Add trace and optimize evidenced slow phase: selected.
4. Separate Secure MCP Tunnel/private HTTPS to ChatGPT: staging option subject to verified Platform/ChatGPT permissions and keys; no assumed entitlement or unsafe production switch.
