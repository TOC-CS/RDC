# RDC Platform-Wide Development Scope and Roadmap
TOC Ministries | November 17, 2026
Owner direction: All future RDC work must address the full application, not merely chat/three-way communications.

## Continuous development workstreams
1. Performance, latency, and resource efficiency: reduce end-to-end tool-call latency vs authorized Desktop Commander 0.3.1; measure p50/p95, D1 queries, R2 operations, poll/wake delays, job startup, SQLite overhead, CPU/RAM and browser session impact. Establish 30+ matched trials on an identified deployed version.
2. Reliability and recovery: maintain durable job and operation identities, bounded outputs, no unintended replay, protected retries, reconnect survival, cancellation/timeout correctness, restored workers after interruptions and capacity saturation.
3. Security hardening: owner-only access, least privilege, protected credentials, no secret/token logging, isolation by device/project, strict schema/input validation, path and symlink protections, replay prevention, resource bounds, denial-of-service resistance, audited approvals and safe release/rollback.
4. Core functionality and usability: terminal/process tools, file operations, project search and coding edits, browser automation, independent headless sessions, read-only diagnostics, background jobs, optional visual interfaces, and accessibility.
5. Integration and compatibility: authenticated ChatGPT tools, cloud private Site, macOS/Windows/Linux workers, authorized local apps, and source/build consistency.
6. CI and production releases: independent red/green tests, full Python and Node suites, production build, actual hosted platform qualification, exact SHA readback, owner-approved protected rollback Site version, verified live @RDC acceptance, monitored performance after deployment.

## REA and current measured baseline
The ten-pair authorized iMac live test on November 17 completed with 10/10 correct echo calls for both tools. RDC tool boundary median was 3470ms and DC median 1884.5ms. RDC remains slower for this short-command workload; source-only optimization is not evidence of live latency improvement. Full trace and benchmarks in existing private REA checkpoints.

## Current chained source work
- Primary durable gateway journal capacity source repair: PR #3, three-platform hosted CI succeeded; live Site installed SHA remains unverified.
- Single-sweep D1 expiry maintenance source optimization: stacked PR #4, 59 Node and 478 Python tests passed. Ubuntu and Windows hosted CI passed; macOS canceled without runner/test steps. Source not yet deployed.
- Strict read-only status/recovery validation: independent stacked hardening candidate after PR #4. It rejects unexpected model-supplied args before journal cleanup, without weakening authenticated recovery or owner binding.
- Separate communications owner branch: preserve uncommitted ownership. Integrate only after independent review. This is one workstream alongside performance and hardening, not a project-wide gate.
- CI runner reliability: GitHub issue #5. Do not misclassify macOS job cancellation without runner as application test failure.

## Release and ownership
Use only the established TOC-CS GitHub publishing identity on the authorized iMac. Do not create alternative GitHub accounts or invitations. Do not merge, restart workers, mutate owner-private Site, clear D1/R2, expose credentials or interrupt active BandMates/Atlas sessions merely to pass a benchmark. Preserve independent release gates, source ownership and rollback verification. Improve source continuously with independently testable, isolated worktrees while the private Site release tooling is unavailable.
