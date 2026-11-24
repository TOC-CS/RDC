# RDC development owner test budget and speed-first directive

**Owner speed-only directive, November 19, 2026:** Focus ALL active RDC development and test efforts on eliminating measured end-to-end latency until the replacement meets or exceeds every mandatory connected-ChatGPT threshold. Defer feature expansion, presentation, preview changes, cosmetics, unrelated maintenance and extra test campaigns. Only perform functional and security regression checks needed to protect a speed change or its safe deployment. Optimize the complete authenticated Site, Durable Object, persistent relay, device execution and ChatGPT response path, not merely fast localhost code. Maintain real >=30 correct live measurements for terminal p50 <=800ms, gateway pickup <=50ms, claim-to-result <=150ms, local notification <=1ms, one-request coding read <=800ms, and >=2x matched end-to-end advantage over Desktop Commander. Surpass the limits whenever independently measured and reproducible. Local milliseconds DO NOT qualify as cloud live speed; retain full original output and rollback safety. Do not release a version whose deployed identity, source, bindings and protected rollback have not been verified.

**Mandatory latest owner rule, November 19, 2026:** All and any RDC testing is capped at 100 total checks per campaign. The number is a hard maximum across all categories, OS jobs, workers, test scripts, and agent lanes combined. Never run 101 or more cases in a single campaign, or launch 100 per category and call it one 100-check run.

Before testing, read `docs/RDC-TEST-100-EXECUTION-POLICY.md` and run `python scripts/rdc_test_budget.py --campaign local-core --dry-run`. Use the governor and the manifest `docs/rdc-test-budget-100.json` for source regression tests. CI splits one shared 100 slots across three operating systems: 34 / 33 / 33. Adversarial checks split 34 / 33 / 33 across three security categories. Bounded live benchmark campaigns must preserve all speed and correctness requirements. Do not report omitted tests as passed or decrease release requirements.

Preserve the repository's original architecture, private production Site and worker, existing owner grants, project source branches and uncommitted worktrees. All enhancements require test-first evidence with a capped execution campaign. RDC speed work uses one direct owner branch and one measured critical path; Atlas Bus, swarm handoffs and cross-session chat orchestration are retired from this build. No external publication, production deployment, or unverified completion claim.

## Mobile command-engine Superpowers workflow

Use the installed Superpowers skills when available: writing-plans and
using-git-worktrees for scoped changes; test-driven-development before
behavior changes; systematic-debugging for measured failures; executing-plans
for inline implementation; requesting-code-review and
verification-before-completion before release decisions. Do not add a
Superpowers runtime dependency, background swarm, or duplicate execution lane.

Maintain a persistent private evidence ledger. Prefer direct device APIs,
structured controls and finally verified visual gestures; distinguish local
sandbox, host-terminal and remote execution. Benchmark correct live operations
rather than enqueue times. The 100-operation campaign limit overrides any
generic instruction to run an unbounded suite. Public materials must contain
only generic reproducible fixtures, source and sanitized measurements.
Owner application usage, private screenshots, device IDs, credentials, local
paths and device-specific signing material never enter release assets.

Explicitly authorized public development previews may be published on a
separate branch without merging or deploying. Label incomplete device and
speed gates. Existing production release holds remain in effect.
