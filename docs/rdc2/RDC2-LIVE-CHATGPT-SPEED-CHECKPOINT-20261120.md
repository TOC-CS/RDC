# RDC 2.0 speed-first continuation and current deployment block

Date: November 20, 2026, afternoon Central. Source branch: local/rdc2-owner-hot-path-20261119. This report is a live diagnostic, not a claim that any performance acceptance target has been certified in production.

## Current real ChatGPT-connected app

- Connected RDC worker identity on the iMac: 0.1.0a8, device ID [owner-private device ID redacted].
- Private ChatGPT plugin: version 1.0.29, current release pluginrel_6afd3ab85ea481919a1af034187c9f4c; plugin manifest points to existing owner-private Site rdc-toc-cs.tribeofchristians.chatgpt.site.
- The plugin archive and its skills do not deploy the private Site transport. Changing skills alone does not switch the connected worker to the new standalone gateway.
- Three fresh, correct matched terminal echo pairs exercised the same authorized iMac. RDC tool wall times: [3582, 2700, 2932] ms, median 2932 ms. Desktop Commander tool wall times: [1567, 1423, 1511] ms, median 1511 ms. Both outputs correct for every pair.
- The RDC local durable job itself took [106, 104, 89] ms from creation to completion. Therefore the dominant observed delay remains outside local command execution. This small diagnostic set does not satisfy the mandatory >=30 real matched pairs.
- RDC is 1.94 times SLOWER than Desktop Commander at the measured median. The measured Desktop Commander/RDC speed ratio is only 0.515, against a required >=2.0 advantage for RDC.

## Independently verified RDC 2.0 standalone transport

- New owner-hosted standalone V2 gateway connects official MCP client over encrypted SSH to an isolated VPS loopback service and an actual isolated iMac worker. No public TLS, ChatGPT Sites binding or shared production gateway was changed.
- 30/30 correct real coding discovery/file reads in one MCP call: p50 96.775 ms.
- 30/30 correct terminal echo commands: p50 147.338 ms, p95 241.374 ms.
- Measured gateway queue pickup p50 6 ms and claim-to-result p50 105 ms for the 30 terminal calls.
- Interleaved A/B showed opt-in post-result credit was slower at p50 and p95 despite reducing claim_wait frames. The optimization was rolled back. Read RDC2-POSTACK-A-B-REJECTED-20261120.md.
- Existing old QA gateway, owner gateway, worker and private production Site have been preserved.

## Enforced safety and acceptance

The mandatory gate now checks five absolute production-live speed ceilings and SIXTH independent, exact-output matched >=2x advantage over Desktop Commander. It supports a private Site or verified owner-hosted standalone TLS transport, each with separate rollout identity, owner pairing and protected rollback requirements. Test-only candidate receipts cannot pass as actual live release evidence.

- Latest source regression after A/B rollback: 86 Node + 14 Python = 100/100 passed, 0 failures, 0 skips.
- Latest separate release-gate regression: 16/16 passed, 0 failures, 0 skips.
- Direct single-owner speed workflow, no Atlas Bus coordination. All campaigns capped at 100 operations.
- Release gate remains BLOCKED. No authenticated ChatGPT-to-V2 connector, independent actual network notification telemetry, exact live gateway revision and protected rollback acceptance, or 30 matched connected measurements. Do not change private production Site, install alternate public unauthenticated endpoint, or assume deployment from a plugin-archive update.

## Correct next engineering target

Stop modifying the local echo execution path for 1 ms improvements. Prioritize protected, owner-authenticated V2 connector staging and ChatGPT host observation on real original outputs. Verify exact V2 Site/standalone release identity, owner binding, TLS/WSS, rollback; then 30+ correct and matched live calls within the 100-operation budget. Optimize the longest phase of the real ChatGPT-connected request return path. Do not claim all targets have been met until this is independently verified.
