# RDC 2.0 Direct-Local Codex MCP Connection

Date: November 21, 2026. Status: verified in authorized isolated development; live ChatGPT plugin V1 is preserved.

## Objective

Make the independent RDC open-source worker usable through a direct authenticated local MCP connection in Codex. No VPS, Sites, Cloudflare, external API billing, ChatGPT subscription dependency, or new device/token provisioning is necessary for this local route. The existing owner-private RDC v1 plugin remains connected. This is a separate opt-in configuration on one authorized developer Mac; ordinary users install and pair their own local workers.

## Actual test result

The direct local worker's existing loopback MCP listener answered HTTP 401 without authentication, confirming that a remote unauthenticated request cannot use it. The client used the existing read-secret mechanism for an already-private agent token, with no secret bytes copied into host arguments, source, reports, or chat.

Thirty real authenticated source discovery and two-file reads using the official Python MCP SDK through the direct worker returned 30/30 correct results: p50 7.877ms, p95 10.013ms, p99 11.915ms, tool catalog size 64, initial connect/discovery 358.462ms. The original request schema was used: direct worker tools do not accept the cloud-only _rdc_request_id argument, while the gateway does.

A distinct Codex MCP alias named rdc2-fast-local was added through the standard Codex MCP CLI, without removing the original rdc alias. It launches the same source Python client in stdio mode and connects to the separate authenticated local QA worker. The existing RDC, presentation agent and computer-use entries were verified unchanged. Another pre-existing node_repl CLI configuration entry was observed to differ from the snapshot during the update; its contents were preserved rather than overwritten.

A subsequent MCP SDK test read the exact saved Codex alias command and environment and executed three genuine tool operations with correct original output: system status 234.543ms, two-file coding context 11.963ms, terminal echo 129.255ms. Initial startup and discovery was 485.788ms, and 64 advertised worker tools were confirmed. The command, project scope and working directory were all explicitly verified. Original terminal exit status was zero.

## Scope and precautions

The direct Codex MCP alias points only to the isolated local QA worker and its configured QA workspace root; it does not grant access to the real owner's broader production directories. The old RDC v1 ChatGPT plugin and its production worker were not restarted, replaced or reconfigured. An existing Codex session may need to refresh its tool catalog to discover the new alias; a registration in the CLI is not proof that the currently open ChatGPT conversation changed tools.

An earlier attempt to copy private pairing credentials into a separate persistent relay configuration was blocked by execution safety checks and was not retried. The direct local MCP path uses only an existing, already authorized local agent credential in place. It is also the fastest currently verified vendor-independent path, but the ChatGPT-connected six-part production acceptance and >=2x verified Desktop Commander comparison remain open.

Do not automatically run paid Codex model prompts, make OpenAI Platform API inference calls, purchase credits, enable auto-recharge, or expose any credentials for this setup. Local MCP transport tests used zero OpenAI Platform API calls.

## Verification and recovery

- Codex MCP list/get can show the separate alias without exposing the private local agent key.
- The old RDC alias is retained. Remove only the new alias with codex mcp remove rdc2-fast-local if the user deliberately retires this QA connection.
- Original private configuration backup is retained locally in the QA directory, mode 600. Avoid overwriting other Codex settings from the snapshot because independent app sessions can update them.
- Private evidence is retained in RDC-2.0-QA/rdc2-direct-local-mcp30-20261121.json and RDC-2.0-QA/rdc2-codex-fast-local-smoke-20261121.json.
- Source-only optional relay catalog registration is now filtered to its actual allowed worker tools, to prevent the gateway from advertising actions the relay would later reject.

This document is source and local-host verification, not a production Site version upgrade or completed ChatGPT speed acceptance.

## Repeatable installation on an authorized machine

The source now includes scripts/rdc_setup_codex_local.py. The default is a read-only dry run, and it does not need a ChatGPT or OpenAI Platform token. It checks the existing agent-token and worker config file modes, canonical 127.0.0.1 HTTP MCP URL, worker state identity, Python executable, and source entrypoint. It never reads the token contents and refuses to replace an already configured Codex alias.

Example dry run, using a previously paired local worker:

    python scripts/rdc_setup_codex_local.py \
      --state-dir /path/to/authorized/rdc-state \
      --worker-url http://127.0.0.1:8765/mcp \
      --alias rdc2-fast-local

After checking the output, add --apply to register the separate Codex MCP entry. The installer invokes Codex's supported MCP registration command without shell expansion and verifies the exact saved command, environment and alias. Restore the old configuration by removing only the newly added alias using the Codex MCP CLI, never by overwriting the entire config from a stale backup. Open a fresh Codex session if the active client has not refreshed its MCP tool catalog.

The helper was exercised with a distinct disposable alias against the existing authorized QA worker. The full apply, metadata readback and exact-alias removal all succeeded. Existing rdc and rdc2-fast-local entries were preserved. The five focused source tests passed, including public-host rejection, private token permission checks, malformed state rejection and refusal to overwrite an existing alias.

The setup command does not install or start an RDC worker, grant OS access, refresh ChatGPT's separate Sites plugin, start a Secure MCP Tunnel, purchase credits, or authorize a production migration. It makes an already paired local RDC worker easy to connect to Codex.

## Owner-direct production-worker fast connection

A separate owner-only Codex alias can also point directly to the user's already-running authorized RDC worker. This was configured and tested privately as rdc-owner-direct with no change to its existing permissions. Thirty complete original-output terminal commands achieved p50 104.380ms and p95 112.182ms through the local MCP client. This is a real Codex local route, not hosted ChatGPT production speed qualification. It inherits the original worker's full-host access if that is how the user configured the worker; enable only for the authorized owner, never as a shared or public gateway. Further evidence and recovery instructions: docs/rdc2/RDC2-OWNER-DIRECT-CODEX-SPEED-20261121.md.
