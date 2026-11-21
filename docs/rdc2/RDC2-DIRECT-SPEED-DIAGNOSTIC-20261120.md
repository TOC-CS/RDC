# RDC 2.0 direct speed baseline (diagnostic only)

Source branch: `local/rdc2-owner-hot-path-20261119`. Existing connected RDC remains the v1 production relay. No Site/worker deployment was authorized or performed.

- Fresh connected original-output `/bin/echo` RDC call: **2,850 ms end-to-end** measured at host, 1 correct/1. Local job record: created at 1795159097.206333, completed at 1795159097.323298, approximately **117 ms**. The remaining observed delay is outside that local execution record.
- Fresh matched Desktop Commander `/bin/echo` call: **1,633 ms** end-to-end, 1 correct/1. RDC diagnostic call took 1.75 times as long, rather than meeting the required >=2x speed advantage.
- Source-only preceding V2 30-correct local test recorded p50 5.992 ms on a disposable Site. It is not evidence of connected production speed.
- Direct Atlas-free cleanup and regression run: **86 Node + 14 Python = 100/100 passed**, 0 failures, 0 skips; `test-results/rdc-speed-first-local100.json`. Dependency-aware selection used the existing RDC development virtualenv.
- Mandatory release requirements remain OPEN: 30 correct live samples for each dimension, connected terminal p50 <=800ms, pickup <=50ms, claim-to-result <=150ms, notification <=1ms, one-call coding <=800ms, >=2x advantage over matched Desktop Commander, exact authenticated private Site/worker release readback and verified rollback.

The measured bottleneck is host/cloud path rather than local command execution. Optimize authenticated Site, worker transport and host return path next. Do not present these single-sample diagnostics as a passed performance campaign.

## Source-only idle wake correction

The V2 Durable Object previously stored a `claim_wait` credit only in actor memory. After hibernation, a newly admitted operation sent an ordinary wake hint and depended on another worker claim request or the 15-second fallback. The V2 actor now persists one payload-free `pendingClaim` credit in the authenticated WebSocket attachment and restores that exact waiting credit when actor memory starts empty. On first durable claim the attachment is replaced by the original operation ID. Busy sockets suppress redundant work hints, credits remain capped at eight, and failed sends never replay a claimed original.

Regression was changed first and failed as intended in a bounded 86-executed-check local campaign (1 failing Node assertion, Python tests not started). After the actor fix, the full owner-capped 100/100 local regression passed, with no failures or skips. Exact source static TypeScript noEmit, focused lint and private Site production build also passed. This proves removal of one extra worker claim roundtrip in the simulated hibernation path, not a millisecond improvement on the deployed private Site. Live activation remains blocked pending authenticated release identity, protected rollback and 30+ connected speed samples.
