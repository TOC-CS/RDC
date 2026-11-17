# TOC RDC Superpowers repair publication and live verification
November 17, 2026 | Release report | Private existing App

ChatGPT RDC plugin successfully updated in place from 1.0.26 to 1.0.27:
Plugin ID: plugin_asdk_app_sites_94e85cd195b481918f7d5ec232575e9c
Release ID: pluginrel_6afc44255ea08191b587d10894234f83
Release URL: https://chatgpt.com/plugins/plugin_asdk_app_sites_94e85cd195b481918f7d5ec232575e9c
Verified readback: version 1.0.27, private audience, 31 files, new rdc-repair skill + superpowers-swarm reference present; .app.json preserved by overlay.

The update publishes ChatGPT-side *skill guidance only*, not cloud gateway source or the running RDC relay worker.

Independent deterministic low-priority test lanes on an isolated source branch:
- gateway: exit 0, complete Node gateway test suite.
- terminal_relay: exit 0, Python terminal and relay suites.
- coding_safety: exit 0, Python coding context and edit suites.
Evidence: ~/RDC-Development/checkpoints/rdc-gateway-capacity-hotfix-20261117/swarm-test-summary.json plus lane logs. Hosted AI agent count: zero; no real AI swarm claim.

Actual connected @RDC repeat acceptance call after ChatGPT plugin update:
- rdc_connection_status: online=true, pending_operations=0.
- rdc_job_run harmless printf: FAILED BEFORE QUEUE, gateway_busy ("The relay has reached its bounded backlog or retention capacity. No operation was queued.")
- Production gateway source recovery therefore UNVERIFIED. No production Site or worker deployment occurred.
- The already tested source hotfix commit 7145b06 remains isolated. Do not claim plugin skill publication removed the backlog refusal.

GitHub connected repository TOC-CS/RDC reports push=false. Do not bypass connection permission or force-push. Source staging and exact commit are retained locally for authorized publisher; remote GitHub publication needs write-granted path and independent release/rollback gates.


GitHub write attempt: connected GitHub repository reports push=false; an attempted top-level handoff comment to existing draft PR #1 returned 403 FORBIDDEN, Resource not accessible by integration. No GitHub source branch, PR comment, or commit was published by this session. The remote integration branch was read-only verified as b2349b66a1431b4592277b9c43763cf7889a8c3e.
