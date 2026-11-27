# RDC testing hard limit: 100 total checks

Effective: November 19, 2026. **Owner directive, applies to every RDC development, build, CI, regression, adversarial, benchmark, recovery, and integration workflow.**

## Hard rule

**Never execute more than 100 RDC test cases or trial operations in any one campaign.** The total combines all categories. This is a maximum of 100 overall, rather than 100 per category, per test file, per worker, or per OS. No tool, test runner, source branch, direct owner workflow, automation, or scheduled continuation can raise the ceiling. Reject excess allocations before starting work. Do not quietly split an oversized single campaign and describe it as having met the 100-test limit.

- A campaign requesting 101 or more checks must fail closed before execution.
- Security/hostile campaigns divide exactly 100 checks across scenarios: unauthenticated 34, wrong owner 33, wrong device key 33.
- The standard local source campaign runs 86 static V2 Node cases plus 14 Python cases. Total: 100.
- The complete three-OS GitHub workflow shares 100 test slots: Ubuntu 34, macOS 33, Windows 33. Total: 100 across all jobs, rather than 100 per job.
- Individual live performance target campaigns may use 30 unique correct samples, which are within the cap. The five distinct mandatory speed targets and matched RDC versus Desktop Commander comparisons remain requirements. Gather them in separately authorized bounded campaigns, with one maximum of 100 test operations per campaign, and label unmeasured dimensions OPEN. Never use prior samples or local simulations as fresh live evidence.
- Do not count static lint, typechecking, compilation, or source review as runtime tests; they can continue separately. Actual test executions, assertion-driven stress operations, and synthetic or live benchmark trial requests count toward their respective campaign budget.
- Keep the existing larger test source library for later rotation and source code review, but do not invoke `python -m unittest discover -s tests`, unbounded `node --test` globbing, or old 300/700/1000/3000-event stress harnesses. Reaching 100 passing selected cases never means the entire library or release is verified.

## Executable enforcement

Canonical cap and allocation: `docs/rdc-test-budget-100.json`.

Governor: `python scripts/rdc_test_budget.py --campaign local-core`.

Preflight: `python scripts/rdc_test_budget.py --campaign local-core --dry-run`.

CI uses the same governor with `ci-ubuntu`, `ci-macos`, and `ci-windows` allocations. These are one shared workflow budget, verified before any job runs. Failed preflight must prevent test execution; do not fall back to unbounded runners.

The hostile localhost harness uses `RDC-2.0-QA/rdc2-built-site-hostile100-20261119.mjs` as its active filename. Historical 300-check reports remain immutable evidence of past runs, not authorization to repeat that test volume.

## Release accounting and consequences

Record budget, planned/actual count, categories, passed/failed/skipped results, source revision, and untested cases for every campaign. If any user-mandated reliability or speed requirement needs additional coverage, leave the release gate OPEN until compliant evidence is gathered. The cap reduces redundant execution; it cannot certify omitted testing.

Scope remains RDC development on the authorized device. Preserve the original RDC worker, private Site, existing backups and rollback; do not change TOC production or unrelated projects. Do not publish or replace live RDC before independent live speed and rollback acceptance.
