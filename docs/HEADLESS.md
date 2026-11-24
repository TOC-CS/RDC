# Headless RDC worker

The standalone browser administration UI and its packaged assets have been retired in this candidate. The worker serves MCP on `/mcp`; the root and former UI assets return 404. The hosted entry page is a static connection entry point, without a device/session list or background polling. The embedded AI-host preview remains optional and does not control the worker's lifetime.

New `rdc init` CLI profiles default to trusted execution within the chosen workspace. Shell execution and full-host access remain explicit grants; shared native input, credential authorization, operating-system consent and device pairing retain their existing controls. An explicitly configured review profile remains valid. Existing configurations and stored authorization decisions are not silently changed. To choose trusted execution for an existing authorized dedicated worker, the local owner may update its private configuration while stopped. Preserve rollback and never restart an active worker merely to apply a setting.

## Local owner-only operations

The private CLI uses the existing owner token file and a fixed direct IPv4 loopback HTTP connection. It does not launch a browser, use a proxy, follow redirects, disclose the token, or automatically retry a mutation. Default port 8765; use `--port` and `--state-dir` for the configured worker. Field-bearing commands accept an exact JSON object from standard input.

| Command | Input |
|---|---|
| `rdc owner status` | None |
| `rdc owner pause` / `rdc owner resume` | None |
| `rdc owner decision` | request_id, approve (boolean) |
| `rdc owner credentials` | None |
| `rdc owner enroll` | label, origin, provider, locator |
| `rdc owner credential-decision` | request_id, decision (once, always, deny) |
| `rdc owner remove` | credential_id |
| `rdc owner revoke` | grant_id |

Only the local owner should invoke these commands. Agents cannot make their own authorization decisions. An uncertain result requires status recovery, not replay. These CLI controls preserve legacy review and credential operations without the browser page.

There is no user-facing saved-session manager. Active browser and device handles, durable job receipts, request identities and bounded recovery metadata are operational state, not an administrative UI. Do not delete them while work is active or uncertain. Existing private records are preserved; no new session history feature is introduced.

The old `rdc serve --open` flag is accepted silently for compatibility but does not launch a browser. The supported command is `rdc serve`.

See the separate release acceptance policy. This source change does not establish a deployed worker or a hosted plugin upgrade.
