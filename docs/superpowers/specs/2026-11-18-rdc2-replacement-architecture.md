# RDC 2.0 Replacement Architecture

Owner: TOC Ministries. Date: 2026-11-18.
Branch: rewrite/rdc-2-transport-20261118.
Status: AUTHORISED ISOLATED REBUILD. LIVE PRODUCTION NOT APPROVED.

## Objective
RDC actual 30-pair terminal baseline p50 3,178 ms against Desktop Commander p50 1,820 ms. Later 14-call RDC p50 2,726 ms. Cloud D1 polling and remote network hops dominate local command time. Rebuild an independent replacement transport, rather than adding another v1 D1 patch.

## Proposed architecture
1. V2 per-device SQLite-backed Durable Object stores a single authoritative request journal and owner pin. Local synchronous SQL replaces multiple D1 network round trips. Strict duplicate-key hashing, one original operation identity, ordered claims, claim tokens, bounded capacity, expiry and durable recoverability.
2. V2 internal device actor receives strictly authenticated requests from a separate private gateway. Hibernation WebSockets notify the online worker without polling and never carry secret operation payloads as unsolicited notifications. Durable queue remains the authority.
3. Later V2 gateway and host worker adapter use separate version negotiation, explicit opt-in private Site binding, no access to v1 writable D1 or v1 protected R2 data. User's existing private Site and worker remain running until replacement release gates all pass.
4. Explicit release freeze/drain, protected compatible rollback, readback, plus minimum 30 independent REAL production samples per owner metric before cutover. No fabricated or local simulated speed wins.

## Strict adversarial test isolation
Malformations, unauthorized identities, result forgery, duplicate requests, random concurrent arrival, crashes, timeouts, blackhole network, expired queue, saturation, forged claim, and untrusted payload cases are tested using ONLY disposable synthetic data. Attack drivers and fault injection exist solely in isolated checkpoint folder RDC-Development/checkpoints/rdc2-hostile-regression-20261118, never under production package, release artifacts, or installed plugin. Source packages contain normal validations, no sabotage hooks.

Test contracts: terminal p50 <=800 ms, gateway pickup p50 <=50 ms, claim to result p50 <=150 ms, notification <=1 ms, one-request coding discover+read p50 <=800 ms. All require p95/p99 evidence, 30+ live samples, 100 percent correct output and no gateway_busy. Current metrics remain OPEN.

## Safety
Bind to original owner identity; validate credentials at the authenticated gateway boundary before entering actor. Per-device actor endpoint remains unexposed to public ingress. Durability before action; never retry uncertain mutation; duplicate result uses exact original claim identity and SHA. No deletion of unknown or nonexpired protected mutations. Fail closed on missing internal credential. Do not deploy without real Site control and protected rollback.

## Coordination truth
Superpowers skill documents 7.0.1 located on authorized iMac. Atlas Bus code is currently an isolated SQLite coordination core without live ChatGPT session adapters; no independent AI swarm can be truthfully claimed merely from its presence. Separate scoped test processes may run in parallel but are not AI agents. Record actual evidence and provider model usage only if verified.

Cloudflare 2026 docs: SQLite-backed Durable Object storage supports co-located sync SQL and transactionSync; Durable Objects WebSocket Hibernation supports persistent sockets while idle.
