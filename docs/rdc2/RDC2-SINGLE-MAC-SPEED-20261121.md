# RDC 2.0 single-Mac gateway speed candidate

November 21, 2026. Source worktree: existing RDC speed owner. This is an isolated, authenticated local candidate, separate from the installed ChatGPT RDC v1 relay.

## Security and architecture

The standalone gateway binds 127.0.0.1. Explicit relay transport standalone-local permits only a canonical HTTP MCP URL of the form http://127.0.0.1:PORT/v2/mcp with a mandatory port. The authenticated device uses loopback ws on /v2/device/socket and loopback HTTP on /v2/device/result for bulk responses. Existing Sites and remote standalone modes still require TLS-verified HTTPS and WSS.

Public hosts, localhost ambiguity, alternate IP addresses, missing ports, credentials embedded in URLs, query strings, fragments, encoded path changes and unexpected paths are rejected. The device pairing key, gateway client bearer and worker credentials remain separate. The local relay must not use the Sites service credential. The original operation ID, retained result, durable claim and no-replay behavior remain unchanged.

Synthetic large-output coverage checks the local HTTP bulk-upload branch using the original operation ID, claim ID, request digest, result digest and X-RDC-Device-Key header. It confirms that the Sites service header is absent for this opt-in local mode, redirects/proxies remain disabled, and an authenticated denial is never automatically retried or re-executed. These are focused security simulations, not an independently verified large live transfer.

This permits an optional future owner-authorized outbound Secure MCP Tunnel on the same Mac without requiring a VPS. It does not provision a tunnel, create a new ChatGPT plugin, or use paid Platform API operations.

## Verified bounded source tests

New test-first regression for local routing and catalog authorization: 7/7 passed. Existing V2 relay compatibility: 26/26 passed. Governed core source suite after final catalog update: 100/100 passed, with 86 Node and 14 Python checks. All campaigns are separate and within the mandatory 100-test maximum.

The isolated local gateway uses its own private state and a dedicated local test worker. It leaves the existing ChatGPT Site v16, production v1 worker, and VPS services untouched. The real full run_relay_v2 process integration was not completed after its task was blocked by execution safety checks. Do not assume that production-runner validation was completed.

## Real official MCP tests with zero paid OpenAI API calls

Thirty actual loopback terminal commands returned the exact original output and exit status 0: p50 105.315ms, p95 135.244ms, queue pickup p50 0.552ms, claim-to-result p50 99.103ms, gateway ASGI send p50 0.087ms.

Thirty actual local coding-context requests each found and read two real source fixture files with one MCP call: 30/30 correct, p50 7.016ms, p95 10.027ms, queue pickup p50 0.180ms, claim-to-result p50 4.610ms and server-side send p50 0.024ms.

A controlled interleaved 60-operation A/B, alternating five-call batches against the same isolated iMac worker, produced:

| Coding metric | Local single-Mac | Encrypted SSH/VPS |
| --- | ---: | ---: |
| Correct original output | 30/30 | 30/30 |
| p50 | 9.282 ms | 89.084 ms |
| p95 | 16.699 ms | 681.310 ms |
| p99 | 18.844 ms | 799.580 ms |
| One-time MCP connect/list p50 | 317.517 ms | 485.925 ms |

The local path was 9.598x faster at p50 on this interleaved test. The two gateways had different prior source revisions, and the result is evidence for the practical transport path, not an isolated proof of network distance as the only causal factor.

All those tests consumed zero OpenAI model/API credits and established no live ChatGPT app connection. The ASGI send timestamp is server-side send only, not actual network receipt.

## Private evidence and release boundary

Evidence remains under RDC-2.0-QA:
- rdc2-local-loopback-mcp-terminal30-20261121.json
- rdc2-local-loopback-mcp-coding30-20261121.json
- rdc2-loopback-vps-coding-ab60-20261121.json

The existing production ChatGPT app still uses the older v1 transport. Real user-facing V2 acceptance requires exact deployed source, owner authentication, protected rollback, 30 or more correct live samples for five absolute targets and an independent 30-pair Desktop Commander comparison with at least 2x RDC advantage. Keep the existing Site and worker intact, and do not activate the held v17 migration.
