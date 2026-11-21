# RDC 2.0 direct speed-first workflow

Effective 2026-11-20. Owner directive: remove Atlas Bus development coordination from RDC. Preserve all unrelated Atlas projects and the installed RDC v1 production service. RDC 2.0 changes remain in the original owner speed worktree, not in an autonomous agent swarm, parallel branches, chat interconnect, or queued handoff chain.

## One direct path

1. Inspect existing owner branch and recent diagnostic evidence. `python3 scripts/rdc_speed_first.py status`. One owner edits the measured bottleneck; do not start another worker or implementation lane.
2. Measure actual ChatGPT-connected RDC before and after the change with correct original outputs. Diagnose device execution, cloud admission, queue pickup, claim-to-result, Site/host response, and matched Desktop Commander. Do not mistake sub-10ms localhost output for a live win.
3. Make only the measured speed fix, preserving owner authentication, exact original operation identity, retained results, TTL, no-replay, and protected rollback.
4. Run the combined capped source campaign: `python3 scripts/rdc_speed_first.py test`. This calls the existing governor once, preflights the 100-case cap, and executes 86 V2 Node and 14 Python tests. No unbounded discovery or ad hoc loops. Separate source compilation/lint can run without counted runtime tests.
5. Independently obtain a real, revision-matched live receipt from the authenticated private Site or owner-hosted standalone TLS gateway and connected worker. Run `python3 scripts/rdc_speed_first.py gate --receipt /path/to/live-receipt.json`. The gate requires 30+ correct real samples for every mandatory dimension, plus 30+ correct matched end-to-end RDC/Desktop Commander pairs demonstrating at least 2x speedup, exact release identity, transport-appropriate private Site or standalone TLS/pairing verification, and protected rollback. A missing or incomplete receipt FAILS; local simulations are ineligible.
6. Deploy or publish only when all performance, security and rollback gates pass through the existing authorized protected release path. No bypass, live migration, guessed credentials, or speculative performance claim.

## Mandatory live targets

Connected terminal p50 <=800ms; durable pickup p50 <=50ms; claim-to-result p50 <=150ms; local notification p50 <=1ms; one-request coding discovery/read p50 <=800ms; >=2x advantage over Desktop Commander on 30+ correct matched live samples. All five numerical goals plus the independently verified 2x matched terminal comparison are SIX mandatory release gates. Any unmet target keeps the release BLOCKED. Hard ceiling: **100 tests/operations per campaign total** across all lanes and platforms.

## Scope of Atlas Bus removal

Remove the unused RDC cross-session synthetic chat/Atlas Bus modules, their tests and `rdc-communications` skill. Historic reports and audit records remain as history, never as active workflow requirements. No other Atlas Bus installation, service, project or model is changed. The core RDC worker, authorized terminal/file/browser operations, Site boundaries, and V2 relay remain separate and intact.

The speed script detects an existing RDC Python virtualenv with the test dependencies. It never modifies or installs packages into the live worker. When the system Python lacks dependencies, it uses the existing owner RDC development virtualenv for capped source verification.

## Transport-aware speed acceptance receipts

Use python3 scripts/rdc_test_budget.py --campaign speed-acceptance-contract to run the separate, capped 16-case acceptance-policy regression. The local-core campaign remains capped at 100 checks.

The acceptance gate requires environment.mode=production-live, environment.host=ChatGPT-connected-RDC, exact gitRevision and connected workerVersion. The legacy private Site route (omitted transport or private-sites) requires siteVersion, Cloudflare wake binding verification and protected rollback. The standalone route (owner-standalone) instead requires actual gatewayVersion readback, public TLS/WSS verification, owner/device pairing verification and protected rollback. Standalone never inherits the Cloudflare Site grant.

A comparison object is mandatory: 30-50 unique matched terminal pairs, production-live origin, revision-matched independent evidence, and the same authorized device and original output. Both tools must complete correctly. The Desktop Commander median divided by RDC median must be at least 2.0, and RDC median <=800ms. Each pair consumes two operations, keeping the campaign within the 100-operation cap. No source-only data, SSH-tunnel test or simulated receipt can substitute for actual ChatGPT-connected acceptance.
