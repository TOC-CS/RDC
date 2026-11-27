# RDC 2.0 protected Secure MCP Tunnel staging

November 20, 2026. Scope: separate, owner-private RDC V2 staging only. This procedure leaves the existing ChatGPT RDC plugin, Site v16, connected worker and standalone VPS owner gateway unchanged.

## Objective and sources

Official OpenAI Secure MCP Tunnel supports private outbound HTTPS transport from an MCP server to approved ChatGPT workspaces. It requires a Platform tunnel ID, restricted runtime API key, organization/workspace association, and plugin creation access. References:

- https://developers.openai.com/api/docs/guides/secure-mcp-tunnels
- https://github.com/openai/tunnel-client/blob/master/docs/onboarding.md
- https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt

Tunnel provisioning and full MCP write access depend on actual account and workspace permissions. The current private Site plugin does not become a V2 standalone connector because its skills are updated. The official tunnel does not guarantee latency goals.

## Safe connection stages

1. Preserve the existing owner VPS gateway on 127.0.0.1:18784 and QA gateway on 127.0.0.1:18786. Use a separate, verified V2 candidate with its own paired worker.
2. Install a verified supported tunnel-client only under the authorized staging account on the SAME VPS that can reach its local HTTP MCP route. No publicly reachable port is required.
3. Create/select the Platform tunnel and restricted runtime API key through the approved Platform UI for the correct organization. Associate the intended ChatGPT workspace; verify Tunnels Read + Use permission. Keep admin permissions separate.
4. Store the runtime API key and gateway client token in DISTINCT owner-private mode-600 files. Keep credentials out of Git, chat, shell arguments, screenshots, reports and systemd command lines.
5. Create a mode-600 JSON readiness file with ONLY these fields: tunnel_id, mcp_server_url, runtime_key_file, gateway_client_token_file. The MCP URL must use an authorized local 127.0.0.1 HTTP address ending in /v2/mcp.
6. Run the read-only preflight command:
   python3 scripts/rdc2_tunnel_preflight.py --config /owner/private/tunnel-readiness.json --binary /owner/verified/tunnel-client
   A passing check certifies only local file permissions, executable presence and route and ID shapes. It never validates real Platform credentials, starts a tunnel or certifies a ChatGPT connection.
7. Follow the CLI's actual help: tunnel-client help quickstart, tunnel-client help samples. Create an HTTP MCP profile with the actual tunnel ID and local endpoint, then run tunnel-client doctor --profile rdc2-staging --explain. Only after owner-authorized setup, start tunnel-client run --profile rdc2-staging under a verified supervisor. Provide the runtime key via a private protected environment, not a command argument.
8. In ChatGPT Plugins, select Add custom MCP server, choose Connection: Tunnel, select the actual tunnel and configure the separate gateway authentication through the host UI. Create a NEW private staging connection and preserve existing RDC.
9. Independently verify exact deployed source, worker identity, gateway release, tunnel readiness, owner pairing, authentication and rollback before comparing real ChatGPT speed.

## Release gates

The six mandatory gates remain open until actual ChatGPT-hosted V2 receipts exist: terminal p50 <=800ms, pickup <=50ms, claim-to-result <=150ms, actual notification <=1ms, one-MCP-call coding read p50 <=800ms, and >=2x correct matched end-to-end speed vs Desktop Commander on at least 30 pairs. All measurement campaigns must stay within 100 total operations each. An isolated or synthetic tunnel run cannot stand in for a real ChatGPT client.

The official Secure MCP Tunnel has a 120-second absolute request deadline and a 10 MiB serialized envelope bound. The existing RDC V2 native bulk result limit is larger. Before any real tunnel deployment, verify that serialized MCP results remain within the tunnel bound, that oversized results use original recovery identities, and that long terminal jobs return durable job IDs rather than waiting beyond the hosted deadline. No large-result or long-running tunnel acceptance is claimed from source review alone.

Never treat a successful tunnel-client doctor as proof that ChatGPT is connected. Preserve production until authenticated verified rollback and deployment identity.

## Current blocker

No authorized Platform tunnel ID, restricted runtime API key, confirmed ChatGPT workspace association, full MCP entitlement or running tunnel-client has been verified for this account. None was invented or provisioned by these source templates.
