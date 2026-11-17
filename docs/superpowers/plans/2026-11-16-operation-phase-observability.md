# RDC operation timing observability

## Problem and evidence
The previous 12-pair paired cloud/desktop test showed RDC 3.474 s median and Desktop Commander 1.616 s, while local worker execution was near 60 ms. Gateway records created/claimed/completed timestamps but exposed no owner-safe way to isolate queue time and claim-to-result network overhead. Blindly increasing gateway polls would raise D1 costs without proving the bottleneck.

## Options assessed
1. **Chosen:** optional `diagnostics:true` on existing authenticated `rdc_operation_status`. Query the same operation row already read by normal status, return only relative phase durations and operation state; no extra idle or scheduled calls.
2. New public diagnostics endpoint: rejected, adds attack surface and identity handling.
3. Poll more often: rejected without isolated phase evidence and cost analysis.

## Files and test gate
- `cloud-gateway/lib/rdc-gateway-core.mjs`: schema, timing helper, owner-authenticated optional diagnostic branch.
- `cloud-gateway/tests/gateway.test.mjs`: red/green phase values, privacy, identity rejection, input validation, standard recovery unchanged.
- `cloud-gateway/README.md` and `skills/rdc/references/cloud-operations.md`: document correct interpretation, version/deployment caveat.
- `docs/RDC-SKILL-CROSSBUILD-COORDINATION.md`: track future optional musician/presentation build synchronization; do not deploy BandMates.

## Invariants
No worker or relay restart. Same owner principal, same operation ID, no request or stored-result reads in diagnostics mode, no mutation or automatic replay, no secrets or credentials. All mode changes opt-in. No new paid API dependency.

## Release acceptance
Run the red tests before production code, green tests afterward, complete gateway tests, worker contracts, production build, lint/diff checks, CI on published branch; deploy only through an authenticated existing private Site identity and verify actual live behavior before claiming speed improvement. Keep PR in draft and document unresolved host PiP, cursor and native-device validation accurately.
