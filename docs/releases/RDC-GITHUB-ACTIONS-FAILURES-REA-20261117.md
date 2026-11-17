# RDC GitHub Actions failures, REA repair triage
TOC Ministries | November 17, 2026 | source-only, no live deployment

## Input and scope
A read-only review of GitHub Actions notifications identified 28 failure notifications across 22 distinct TOC-CS/RDC workflow runs dated November 14-17, 2026. The notifications were deduplicated by GitHub Actions run ID; actual job conclusions and failed-step logs were checked against the repository. No email addresses, authentication links, tokens or account-security message bodies are included in this public note.

## Classification based on actual jobs
- Fifteen macOS job cancellations lacked a runner assignment and executed no test steps. These reflect incomplete qualification; they provide no evidence that macOS source tests failed.
- Ten failed Windows jobs and one failed Ubuntu job ran test steps. They represent historical code/test regressions requiring source comparison before any rework.
- One historical GitHub run returned HTTP 404 to the authorized repository account. Its outcome remains unverified.

## Confirmed test failure patterns
1. [Run 44069200154](https://github.com/TOC-CS/RDC/actions/runs/44069200154): Windows test_coding_edit_many rejected expected SHA-256 file versions. Later integration source commit b2349b6 uses binary LF fixtures with regression coverage, and primary [PR #3 CI run 44082041503](https://github.com/TOC-CS/RDC/actions/runs/44082041503) passed macOS, Ubuntu and Windows.
2. [Runs 44059675581](https://github.com/TOC-CS/RDC/actions/runs/44059675581) and [44054420243](https://github.com/TOC-CS/RDC/actions/runs/44054420243): Windows code-context and workflow tests expected LF but observed CRLF. Later chat-interconnect source af322be1 passed the full hosted matrix in [run 44064852591](https://github.com/TOC-CS/RDC/actions/runs/44064852591). Do not reapply old failing-commit changes over that owner branch.
3. [Run 44024685929](https://github.com/TOC-CS/RDC/actions/runs/44024685929): Windows preview generated-asset/pinned-fixture comparison was affected by CRLF checkout; a later .gitattributes LF fix was published at 0e30582, with the separate current primary PR passing all three platforms.
4. Earlier preview/terminal and mobile test failures include Windows output CRLF, preview recovery assertions, and module-load behavior. Newer passing source trees supersede those historical failing commits, but individual unmerged branches still require their own SHA-specific qualification.
5. macOS no-run examples: [fallback run 44160066275](https://github.com/TOC-CS/RDC/actions/runs/44160066275) and [Presentation Agent run 44060175054](https://github.com/TOC-CS/RDC/actions/runs/44060175054). Cancellation with no assigned runner must not be marked a code-test failure or green CI. Record scheduling blocker rather than blindly retrying.

## Repair workflow integrated
- Classify every new failure email by repository, branch, exact SHA, workflow run ID and whether test steps actually executed.
- Inspect failed steps and compare failing SHA with newer passing successors before changing code.
- Reproduce still-relevant defects with a focused RED test; repair only in isolated authorized worktrees, then require focused GREEN, full Python/Node suites, production build/lint, and hosted CI on the exact published SHA.
- Keep durable operation identities and protected rollback restrictions. Do not reset live worker, clear D1/R2 or bypass authorization to make CI green.
- Use the established TOC-CS GitHub publishing identity. Do not create another account or send collaborator invitations.
- Report source progress independently from private Site deployment and real @RDC acceptance. The private Site's installed gateway SHA and protected inactive rollback still require readback.

## The accompanying single-sweep optimization
The gateway historically issued two sequential expiry UPDATE statements every ordinary cleanup invocation, introducing an avoidable D1 round trip. This isolated branch substitutes one conditional CASE-based UPDATE while preserving queue TTL expiration, unknown claimed identity, queued request-body removal and mutation no-replay protection. RED test showed two UPDATEs; GREEN test proves one while preserving state. This is a source-level query reduction, not an observed live end-to-end speed improvement. The last connected 10-pair RDC/DC short-command benchmark still found RDC slower by median at the tool boundary.
