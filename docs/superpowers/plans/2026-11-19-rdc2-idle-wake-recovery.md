# RDC 2.0: bounded WebSocket recovery with single active claim per device socket

Status: isolated development candidate. Production release blocked pending real live speed and rollback acceptance.

## Owner requirements

RDC must beat Desktop Commander in actual ChatGPT-connected terminal, coding, file, and browser workflows. Mandatory thresholds remain terminal median <=800 ms, queue pickup <=50 ms, claim-to-result <=150 ms, notification <=1 ms, and coding search plus selected read <=800 ms in exactly one cloud request. Each dimension needs at least 30 independently correct live operations. No test campaign may run more than 100 checks total across categories.

## Design approaches reviewed with Superpowers brainstorming

1. Periodically query the old cloud D1 queue after lost notifications. Rejected because it reintroduces network hops, cost, and the v1 speed bottleneck.
2. Disconnect and reopen the device WebSocket whenever a hint is missing. Rejected because it adds TLS and handshake latency and cannot safely infer whether the previous claim was delivered.
3. Keep the original authenticated WebSocket and re-register an idempotent `claim_wait` credit on its bounded idle timeout. Chosen because the original SQLite journal decides claims. The refresh never creates a new operation ID or replays a mutation. Legacy V2 servers without the negotiated capability retain the existing claim protocol.

## Bugs and defenses

- **Lost wake/actor hibernation:** The former `V2SocketGateway.poll()` sent a heartbeat after each receive timeout and could remain idle forever when both work-available and actor's ephemeral claim credit were lost. Refreshing the original claim wait after the bounded timeout repairs this while preserving the operation's identity.
- **Repeated claim while first claimed operation is still outstanding:** A timeout refresh could otherwise claim a second queued job on the same WebSocket before completion. One outstanding claim per socket is now enforced. The actor retains its opaque active operation ID in the Cloudflare WebSocket hibernation attachment when supported and in an in-memory map during the current activation. The socket's active state is cleared on completed result and close. The durable journal remains authoritative for actual claims and results. No executable payload is added to any notification.
- **Lost original claim frame:** The server refuses to issue a second claim while the first remains outstanding. The original result must be recovered without new execution identity. It may remain uncertain until the device reconnects; this conservative state is preferred to duplicate execution.

## Evidence and limits

- Source test-first RED: `RDC-2.0-QA/rdc2-idle-wake-RED-20261119.log` (two timeout cases failed before fix).
- Source GREEN: `RDC-2.0-QA/rdc2-idle-wake-GREEN-20261119.log`.
- Adversarial one-socket RED: `RDC-2.0-QA/rdc2-one-credit-per-socket-RED-20261119.log` (two claims granted instead of one).
- Adversarial one-socket/hybrid hibernation GREEN: `RDC-2.0-QA/rdc2-one-credit-per-socket-ATTACHMENT-GREEN-20261119.log`.
- Mandatory budgeted source campaign: `RDC-2.0-QA/rdc2-idle-recovery-socket-guard-100-20261119.json`, **100 executed, all passed**.
- Atlas Bus simulated coordination with 3 actual isolated QA subprocesses and 91 total test cases: `RDC-2.0-QA/atlas-rdc2-idle-recovery-parallel-results-20261119.json`, all passed. This is not authenticated AI swarm dispatch.
- Compiled localhost Workerd + SQLite DO + real Python worker through deliberate fault proxy: `RDC-2.0-QA/rdc2-idle-wake-loss30-results-socket-guard-20261119.json` and `rdc2-idle-wake-loss-proxy-results-socket-guard-20261119.json`: 30/30 original results correct, 30 missed claim registrations, 30 missed work-available hints, 30 correct result acknowledgments, zero replay; median 214.680 ms (includes deliberately forced 200 ms timeout), p95 219.468 ms. Local only.
- Latest source build, TypeScript and scoped ESLint passed. The disposable site uses localhost-only synthetic credentials. Other workers' branches, TOC/BandMates systems, production iMac RDC worker and private Site were not modified.

## Future work

Verify actual private Site/worker deployment compatibility and rollback through owner-authorized Site management. Implement a protected, independently authenticated hosted canary without production changes. Obtain 30 unique **real ChatGPT-connected** timed samples for each target and matched RDC vs Desktop Commander task evidence. Do not mark release complete from localhost measurements or from the synthetic Atlas Bus. The owner separately directed that hourly RDC continuation checks be disabled; continue direct work rather than scheduling a new hourly task.
