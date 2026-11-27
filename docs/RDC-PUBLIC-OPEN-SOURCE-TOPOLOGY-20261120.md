# RDC public open-source deployment topology

Status: architecture contract, November 20, 2026. Public hosted service is NOT deployed or certified by this document.

## Product identity and non-negotiable routing rule

RDC is an MIT-licensed, publicly reusable, open-source application. The maintainer's personal iMac, private ChatGPT RDC Site, personally paired worker, home network, ministry applications, and existing VPS must not be the mandatory or shared execution/relay infrastructure for other RDC users.

A maintainer machine may be used intentionally for local development or as the maintainer's own independently paired *user device*. It cannot act as the intermediary through which other people's commands, file contents, browser sessions, credentials, or results flow.

There are TWO distinct supported deployment concepts, not a silent conversion of one private Site into a public service:

### A. Fully local / self-hosted RDC (existing, distributed)

AI client with locally installed stdio MCP bridge -> local RDC worker on THAT USER'S authorized device.

- Each user downloads and installs RDC on their own device.
- No central RDC account, owner Site, publisher computer, VPS, Cloudflare account or subscription is required.
- Owner grants, file scopes, saved passwords, OS consent, command execution and job history stay with that user's worker.
- Users who choose to host their own relay are responsible for its authenticated HTTPS access; never publish the worker's localhost endpoint directly.
- Optional direct Codex integration is installed using the source-only credential-free setup helper scripts/rdc_setup_codex_local.py against an already paired local worker. The helper never copies private agent tokens or depends on the publisher's workstation, VPS, Platform API credits, or ChatGPT plugin identity. See docs/rdc2/RDC2-DIRECT-LOCAL-CODEX-CONNECTION-20261121.md.
- The existing deploy/compose.yaml runs a *single user's isolated worker*, not a multi-tenant gateway. It binds host loopback only.

### B1. Independently self-hosted single-operator V2 gateway (now implemented and VPS loopback-tested)

Users can run the standalone Python gateway on their own VPS, with an authenticated persistent device WebSocket, private SQLite result journal and vendor-neutral HTTPS client route. It does not require ChatGPT Sites or the publisher workstation. One operator and one paired device per instance are supported in this beta. Real iMac-worker-to-VPS SSH-encrypted tests completed 30/30 correct requests at p50 210.147 ms and p95 280.28 ms. Public TLS ingress and production restart supervision remain unverified. See docs/RDC-STANDALONE-VPS-SETUP-20261120.md.

### B2. Optional public multi-user hosted gateway (NOT YET IMPLEMENTED)

ChatGPT / other authenticated AI client -> independent public RDC gateway under its own hosting and audience -> authenticated, tenant-scoped operation journal / realtime notification -> outbound per-device RDC agent on the REQUESTING USER'S device -> exact result back to that same authenticated user.

This host is an independent server/service. Its process, DNS, credentials and storage must remain available when the maintainer's personal computer is powered off or offline. A hosting service may be independently administered, but no public request may route via the maintainer's own workstation. RDC must remain deployable by independent operators using documented provider-neutral interfaces and open-source code.

Mandatory public gateway requirements before any user onboarding:

1. **Multi-user authentication:** standards-based OAuth/OIDC with provider-verified subject, audience, token expiry, issuer and per-user consent. Never accept a user ID from a caller-writable header or a model argument as identity. A private Sites owner-identity header is only valid behind its existing authenticated owner-private boundary.
2. **Multi-tenancy:** every operation, device registration, queue, result, artifact and recovery ID is scoped to its authenticated user and paired device. Cross-user device discovery, claims, screenshots, file reads or result recovery are denied; no global owner bootstrap.
3. **Private outbound device connection:** every user agent independently opens authenticated persistent TLS WebSocket / comparable realtime transport from their own device. No inbound user-device port or shared publisher desktop is required. Preserve exact original durable operation ID, claim nonce, digest, idempotency and conservative unknown-outcome recovery.
4. **Isolation and consent:** owner permissions remain on the user's device. Provider infrastructure must never receive raw owner tokens, saved passwords, native credential provider locators or maintainer-local keys. Public rate limits, per-user quotas, retention bounds and audit controls protect other users.
5. **Portability:** a provider-neutral deployable gateway implementation and ordinary self-host instructions. Hosting choice is independent of the developer's private Site and TOC VPS. A central service must not be presented as automatically available just because the repository is public.
6. **Speed:** event-driven admission and result notification, one normalized cloud tool request for common coding/terminal workflows where supported, bounded payloads, durable fast journal and no replay. Demonstrate connected terminal p50 <=800ms, queue pickup <=50ms, claim-to-result <=150ms, notification <=1ms and one-request coding p50 <=800ms, >=2x real-world advantage over Desktop Commander, 30 or more correct real connected samples per goal and no more than 100 tests/operations per campaign. Do not substitute localhost timings.

### C. Current owner-private ChatGPT Site (development / personal use ONLY)

The existing cloud-gateway/ is a SINGLE-owner, ONE-device private Site template. It pins one provider-authenticated owner and pairs one device using private credentials. It relies on Sites-provided authentication and runtime bindings. It has NOT been verified for public multi-user onboarding. The installed personal RDC worker v0.1.0a8 and that private Site are examples of the publisher's own usage, not the public SaaS backend. Do not expose this deployment to other users, widen its audience as a shortcut, or equate updating a plugin manifest with launching a public service.

The unactivated V2 transport source currently uses a private Durable Object actor and private Site identity. It is a useful isolated prototype for exact delivery and local speed testing, but cannot claim tenant isolation or provider-independent public hosting.

## Deployment and acceptance checklist

- Current self-host mode: available from source, subject to each operator's real platform/permissions.
- Current private Site mode: single-owner/private; preserve as-is pending a separately verified compatible upgrade.
- New standalone self-hosted mode: single-operator beta, source and VPS localhost live tests passing; TLS public ingress and reboot persistence still OPEN.
- Proposed public multi-tenant hosted mode: OPEN, requires engineering, owner-approved hosting, authenticated security and cross-tenant tests.
- Prohibited: mandatory publisher iMac relay, implicit TOC VPS dependency, shared developer credentials, silent promotion of owner-private Site to public, unsupported OAuth claims, unverified speed claims.
- Required evidence: independent gateway process survives developer-device shutdown; two or more fully independent owner identities and devices remain isolated; real TLS/auth/expiry/revocation; correct retained original results; failed-forward and disconnect recovery; capped threat-model regressions; independently measured 30+ real connected latency receipts per target.

Product work should pursue the fastest secure, publisher-device-independent path, while maintaining the original portable local distribution.
