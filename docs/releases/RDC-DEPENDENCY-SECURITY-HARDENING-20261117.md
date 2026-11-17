# RDC dependency security remediation and risk gates
TOC Ministries | November 17, 2026 | isolated source-only candidate

## Why this lane exists
A production-selection npm audit of the existing RDC cloud-gateway lockfile reported six advisories: 1 critical, 3 high and 2 moderate. A complete audit including development/build tools reported 37 advisories: 1 critical, 19 high, 16 moderate and 1 low. The embedded RDC module had zero production-selection advisories in the same initial read-only audit.

## Changes staged and tested
- Upgrade Next to 16.4.6 and Zod to 4.6.7. Keep React runtime and React Server Components package aligned at 19.3.1.
- Upgrade Vinext, Vite, Cloudflare Vite tooling, Wrangler, workers types and related directly pinned build packages within their compatible peer constraints.
- Update Sharp in the existing Miniflare override to 0.35.5, and update vulnerable transitive packages including browser mapping, URI and source-map libraries.
- Apply only npm nonforced compatible lockfile remediation. No force or legacy-peer-deps bypass, no dependency lifecycle scripts. The initial Wrangler update rejected a workers-types peer conflict; upgraded those types explicitly to 5.20261117.1 instead of bypassing peer validation.
- Add isolated connector-preview schema contract tests with Zod 4, checking that model-supplied identities and extra fields are rejected and valid messages remain accepted.
- Drafted a separate GitHub Actions dependency-security workflow locally, with clean lockfile install, production and critical toolchain advisory gates, and connector schema checks. The existing TOC-CS GitHub OAuth session lacks the additional workflow scope, so GitHub correctly rejected publishing that protected workflow file. It remains unpublished in the isolated source candidate. The source-only GitHub branch adds an offline Python lockfile security regression to the existing CI instead. The workflow must be authorized and published separately by an explicitly approved TOC-CS credential with workflow permission.

## Local audit results
- After reproducible lockfile install and nonforced fixes, production-selection npm audit: 0 vulnerabilities at all severities.
- Complete npm audit including development/build tooling: 26 remaining, consisting of 19 high and 7 moderate, with 0 critical.
- These remaining alerts are not silently ignored or forcibly downgraded. Many are in upstream development/build toolchains that recommend incompatible downgrades or have no currently compatible patched release. The whole-toolchain critical severity gate remains enforced; open high/moderate findings require independent triage and accepted mitigation before treating the build toolchain as fully hardened.
- Important: npm's dev versus production classification alone cannot prove that code from a development dependency is unreachable in the bundled server. Compiled artifact and deployment-specific reachability review remain open.

## Verification and release boundaries
- Exact lockfile clean install under Node 24 and npm; all relevant direct dependency versions satisfy npm ls.
- Production Vinext build completed and lint had zero errors, one pre-existing image warning; compiler also emitted source-map/dynamic-import warnings that require follow-up rather than a silent security waiver.
- Node gateway (61 tests), Zod connector (3 tests) and full worker Python suite (478 tests, 17 skipped) passed locally after upgrade. The new offline lockfile security regression demonstrates RED on the original vulnerable manifest and GREEN on the patched versions. Exact hosted CI, installed Site source/rollback readback and actual postdeployment @RDC acceptance are independent release gates.
- No live private Site release, D1/R2 modification, worker restart, owner desktop control, BandMates change, credential access or force-push was performed.

## Source ownership
This candidate is an isolated security branch derived from the published status-hardening source; it is NOT a production deployment. Use only the existing authorized TOC-CS GitHub account for publishing, preserve separate communications source owner work and require review and rollback gates before activation.

## Final isolated qualification checkpoint
- Gateway Node suite: 61 passed, 0 failures.
- Connector-preview patched Zod contract suite: 3 passed, 0 failures.
- Full Python suite: 478 tests, zero failures, 17 skips, with the embedded SDK dependencies installed from lockfile. Earlier source branches skipped 43 tests when the pinned SDK was absent; this lane exercised those additional embedded contracts.
- Production Vinext build: complete. Lint: zero errors, one existing next/no-img-element warning.
- Clean package-lock install, direct peer dependency consistency and git diff --check: pass.
- npm audit --omit=dev --audit-level=low: zero vulnerabilities.
- npm audit --audit-level=critical: passes. Full audit retains 26 high/moderate advisories (19 high, 7 moderate), all requiring separate toolchain/reachability review.
- Source, build and security contract results are local evidence only. No live App/Site deployment or release-gate bypass occurred.

## Source-only GitHub publication qualification
This source-only branch excludes .github/workflows/dependency-security.yml because the existing TOC-CS GitHub OAuth session lacks permission to publish workflow-file changes. The proposed workflow remains preserved in a separate local review branch.

The published-source candidate adds tests/test_dependency_lock_security.py to existing CI. It checks package manifest/lock agreement and minimum patched version floors offline. Test-first evidence: the original 16.3.4 Next entry failed the test against the baseline lock; patched 16.4.6 passed. Two new offline lockfile checks both pass locally. With the pinned embedded SDK installed, the complete worker Python suite completed 480 tests, zero failures and 17 skips. Node gateway 61/61, connector-preview schema 3/3, production build, lint and production npm audit passed. The whole-tree npm audit still reports 26 high/moderate development-toolchain advisories requiring review, with zero critical. The new JavaScript connector tests currently run locally, not under the old hosted workflow; they become CI-enforced once the separately staged audit workflow is approved and published.
