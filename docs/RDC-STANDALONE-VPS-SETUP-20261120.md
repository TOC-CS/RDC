# RDC V2 standalone gateway: self-hosted without ChatGPT Sites

Date: November 20, 2026. Status: **single-operator self-hosted beta**, not a public multi-user OAuth deployment. MIT-licensed source. Tested on macOS and Linux.

## Deployment choices

**Direct local mode (already distributed):** each user runs RDC on their own device and connects a compatible AI/MCP client through `rdc stdio`, or to an already running worker through `rdc connect`. No Site, VPS, ChatGPT account, cloud API, subscription, or publisher computer is required.

**Optional remote standalone mode (new):** a user runs the Python standalone gateway on a personally controlled server. The client accesses its authenticated `/v2/mcp` route; a separately paired user RDC agent connects outbound to its `/v2/device/socket` WebSocket. No other person's workstation is used as a relay. The current V2 gateway is ONE owner and ONE paired device per instance, isolated from other operators. It does not implement public user sign-up or multi-tenant OAuth.

## Install on a standalone Linux server

Use a dedicated unprivileged OS account or VM, not an existing production website's execution account when serving untrusted users. Require Python 3.11+.

```sh
python3 -m venv /opt/rdc-gateway/.venv
cd /path/to/your/RDC/source-checkout
/opt/rdc-gateway/.venv/bin/pip install '.[v2]'
/opt/rdc-gateway/.venv/bin/python -m rdc.gateway_standalone init \
  --state-dir /var/lib/rdc-gateway/state --device-id YOUR_EXISTING_WORKER_DEVICE_UUID
/opt/rdc-gateway/.venv/bin/python -m rdc.gateway_standalone serve \
  --state-dir /var/lib/rdc-gateway/state --port 18782
```

An operator must choose privately writable `/var/lib/rdc-gateway/state` and grant the service account ownership. Replace the sample locations and device UUID with values from their own deployment. Initial setup writes two distinct random bearer tokens and the selected device ID using private file permissions, never printing tokens. Existing state refuses reinitialization. Use one process per journal, and protect its SQLite database and result directory.

The server **always binds 127.0.0.1**, not a public interface. Expose remote access only through a verified HTTPS/WSS reverse proxy with a real server certificate, controlled DNS, correct WebSocket upgrades, request-size limits and operator access restrictions. An SSH tunnel can provide temporary encrypted testing without a public port. Never expose `http://127.0.0.1:18782` directly or turn off its bearer checks.

## Device agent pairing

An operator obtains the real `device_id` from `rdc_system_status` on their own authorized RDC worker. The `device-token` file is copied through a separately approved secure device-enrollment workflow and placed in their private relay configuration (mode 600 on Unix). Do not paste credentials into ChatGPT or shell command arguments. Example JSON structure with **placeholders only**:

```json
{
  "gateway_url": "https://YOUR-RDC-DOMAIN.example/v2/mcp",
  "device_id": "YOUR-EXISTING-WORKER-UUID",
  "device_key": "YOUR-PRIVATE-DEVICE-PAIRING-SECRET",
  "transport": "standalone",
  "worker_url": "http://127.0.0.1:8765/mcp",
  "tool_timeout": 60
}
```

The paired user runs `rdc serve` using their own state profile, then `rdc relay-v2 --config /private/relay.json --state-dir /private/worker-state`. The relay continues to require a certificate-verified HTTPS URL. It intentionally omits `OAI-Sites-Authorization` and any Sites credential in standalone mode. A v1 relay and v2 relay must not consume the **same worker's relay state concurrently**. Preserve active jobs and original identities during any owner-approved cutover.

For direct client calls to the standalone `/v2/mcp` endpoint, a separately authorized MCP client must send `Authorization: Bearer <client-token>`. The client-token and device-token are different. A generic standalone service is not automatically integrated into ChatGPT's plugin directory. Local MCP clients may connect with no ChatGPT dependency; adding publicly hosted ChatGPT requires its separate provider onboarding requirements.

**Portable stdio client bridge:** Configure a compatible local MCP host to start `rdc gateway-connect`, which uses an explicit mode-600 client credential file rather than the local worker's device/agent token:

```sh
rdc gateway-connect --url https://rdc.example.org/v2/mcp --token-file /private/rdc-client-token
```

When the VPS service is intentionally loopback-only, an operator can use an authenticated SSH tunnel instead of exposing a public endpoint. After opening `ssh -N -L 127.0.0.1:18783:127.0.0.1:18782 your-vps-ssh-alias` in a separate session, connect with `rdc gateway-connect --url http://127.0.0.1:18783/v2/mcp --token-file /private/rdc-client-token`. Verify the SSH host key and private owner pairing. No secrets belong on the command line.

The paired device registers its own bounded worker tool catalog after reconnect, rather than relying on three hard-coded device tools. The gateway rejects reserved administrative tool names and cannot override local permissions. Official MCP SDK initialization and real one-call source discovery were independently verified in a 30/30 bounded two-machine campaign (p50 95.508 ms, p95 114.446 ms), with 67 tools discovered. The tunnel test does not establish public HTTPS acceptance.

## Verified bounded speed data (not public Internet measurements)

| Route | Correct | Median | 95th percentile |
| --- | ---: | ---: | ---: |
| iMac direct local MCP, real 30 commands | 30/30 | 95.473 ms | 121.305 ms |
| Standalone VPS gateway to local synthetic device, real Linux commands | 30/30 | 47.739 ms | 70.137 ms |
| iMac actual RDC worker through SSH tunnel to VPS standalone gateway, 30 real commands | 30/30 | 210.147 ms | 280.28 ms |

These results demonstrate independent local and encrypted two-machine speed with exact output and no replay in the tested runs. They **do not** demonstrate live ChatGPT-hosted latency, publicly accessible TLS authentication, multi-user isolation or final advertised 2x better-than-Desktop-Commander performance. All 30-sample runs complied with the 100-test maximum.

## Security and release gates

The existing owner-private ChatGPT Site and v1 iMac relay are untouched. The isolated VPS gateway has its own process, private filesystem, independent journal and two operator credentials. No developer computer is a shared public router. The initial VPS process is an isolated loopback deployment; set up and verify your chosen supervisor for reboot persistence before relying on it for production.

**Do not invite public users into this single-operator gateway.** A shared RDC service needs verified OAuth/OIDC, independent account/device pairing, tenant-specific queues and storage, abuse limits, TLS, revocation, multi-user isolation and separate operator-controlled rollback. Its future hosting provider is an implementation choice, never a requirement of the open-source local worker. Keep the existing fail-closed live speed gates and maximum 100 checks per campaign.
