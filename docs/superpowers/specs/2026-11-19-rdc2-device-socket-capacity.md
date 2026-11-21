# RDC 2.0 owner private device socket fanout bound

Date: 2026-11-19. Status: implemented and local regression verified, NOT qualified for production.
Base commit: d693391. Isolated branch: local/rdc2-socket-fanout-20261119.

## Observed failure and hypothesis
The Durable Object reserved at most eight outstanding socket claim credits, but the native `/v2/socket` upgrade accepted an unbounded number of authenticated devices. A new owner operation broadcast a wake to every active socket and allocated a WebSocket pair on each connection. A duplicated or abusive paired client could therefore consume runtime resources and increase notification latency.

## Invariant and design
Keep the existing authenticating gateway and actor boundary. Inside the private actor, reject an authenticated WebSocket upgrade with HTTP 429 `device_socket_capacity` when eight live connections are already registered under the device tag. Check before creating or accepting the WebSocket pair. Preserve all eight existing clients, original journal entries, owner binding, claim credits and ability to reconnect once a socket closes. Do not change the public Site configuration or the default-disabled V2 switch.

Eight was selected to match the preexisting bounded claim-credit set. This change does not establish a device-credential revocation system and cannot guarantee that provider-level network teardown completes within any latency target.

## Red, green, and live local acceptance
Two new tests were run before the fix and failed because the ninth upgrade returned HTTP 503 rather than the required 429. After the guard both passed. One sent 96 simulated concurrently authenticated over-capacity upgrades and confirmed no acceptance and continued legitimate owner admission.
JS suite passed 261/261, Python suite passed 510 with 43 skips, TypeScript, ESLint and compiled Vinext Site build passed.
A separate localhost-only Cloudflare Workerd run using the compiled Site and disposable synthetic credentials opened eight live sockets and rejected 32 further WebSocket upgrade attempts with HTTP 429, then closed one and successfully reconnected. Authenticated owner online status remained reachable. No cloud environment was deployed and no production worker was modified.

## Remaining gates
This remains only local evidence. A protected owner-private hosted canary and compatible rollback must be proven before live adoption. At least 30 correct production ChatGPT-connected samples are still needed for terminal p50 <=800 ms, queue pickup p50 <=50 ms, claim-to-result p50 <=150 ms, notification <=1 ms, and one-request coding p50 <=800 ms, plus matched RDC vs Desktop Commander terminal/file/coding/browser flows. Existing tombstone archive remains off by default until rollback compatibility is proven.
