# RDC startup and routing performance, isolated candidate

Owner goal: make RDC feel faster and more reliable than Desktop Commander during the first browser action, ordinary cloud dispatch, terminal and file work. Preserve user desktop, authentication, idempotency and current private Site v16.

Observed bottlenecks, Nov 17 2026:
- RDC ChatGPT tools commonly took 2 to 5 seconds, although one 69.6 ms worker job took 4.69 s end to end.
- The gateway cloud dispatch currently calls a connection/status helper requiring both a device heartbeat SELECT and a queued-operation COUNT SELECT; the admission caller uses only the online bit.
- Browser setup is currently three separate cloud tools: browser_start, browser_navigate, browser_observe. A checked-in candidate already combines navigate/observe and click/observe, but the initial setup needs fewer calls.
- Desktop Commander has an active Realtime doorbell while RDC has D1 queue/long poll. No wake-up redesign without release review and transport evidence.

Approved candidate scope:
1. Remove exactly one unnecessary queued-operation COUNT query from each new cloud dispatch without changing the owner-authenticated status API or admission safety.
2. Add one Playwright/WebDriver browser_start_navigate_observe tool. Validate URLs before creating a browser; preserve the new session ID in a bounded error result if post-start navigation or observation fails; never auto-repeat an uncertain navigation. On success return fresh source-bound controls and observation ID.
3. Test correctness, rejection paths, duplicate safety and unaffected legacy operations with full local Python worker and gateway suites.
4. Preserve v16 live Site and worker during build. Prove source correctness via actual connected ChatGPT RDC tools. Live end-to-end speed gain remains unproven until reviewed deployment.

Non-goals: inter-chat communications, new chat sessions, chat enrollment, Atlas Bus edits, native foreground input, stopping other browser sessions, credentials, worker restart, D1 migrations, v17 activation, paid provider APIs.

Acceptance: one fewer D1 COUNT per normal cloud dispatch, unchanged connection-status count; one tool rather than three for browser startup/navigation/observation; malformed URL creates no new browser; navigation failure produces discoverable session ID without automatic replay; all targeted and full suites green; exact local commit and hashes retained.