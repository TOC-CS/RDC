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
