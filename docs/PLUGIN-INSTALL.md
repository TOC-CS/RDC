# RDC plugin package

The repository root is a portable Agent Plugins package for local development. `plugin.json` defines RDC's identity and original logo. `mcp.json` starts the installed `rdc` command as a stdio bridge to a shared worker:

```sh
rdc connect --url http://127.0.0.1:8765/mcp
```

This package does not start or install the worker. It contains no credentials, owner-specific paths, fabricated hosted endpoint, or public directory registration. Package creation and schema validation are separate from installation and real-host rendering.

## Files and identity

| File | Purpose |
| --- | --- |
| `plugin.json` | Portable package manifest and OpenAI presentation metadata |
| `mcp.json` | Local stdio bridge configuration |
| `rdc/assets/rdc-logo.png` | Original square RDC logo, used for composer and listing identity |

The portable plugin version `0.1.0-alpha.5` is the semantic-version form of the Python package's `0.1.0a5` prerelease. Its frozen macOS gate passed 256 tests with no skips, and the installed runtime's 52 source inputs were independently verified. The matching private gateway and separately managed App-backed plugin **1.0.6** were subsequently verified. The public a5 release matched all 226 reviewed files exactly. Its [hosted workflow](https://github.com/TOC-CS/RDC/actions/runs/43707243784) passed Linux and macOS with 256 tests each, and Windows with 239 executed tests plus 17 explicit platform skips. This does not establish a public ChatGPT directory listing, production embedded rendering, or physical mobile qualification.

A portable operating skill is included under `skills/rdc`, with references for cloud recovery, credentials and compatibility. It contains no personal deployment identity and relies on the installed RDC tools and their current schemas. The concurrent public follow-up records the earlier **1.0.5** guidance update; the current coordinator separately verified all nine files of **1.0.6**, including five changed files. The App binding, existing description and presentation, credential/mobile/diagnostic guidance and private audience were preserved. The portable package declares TOC Ministries, while the requested private App icon and publisher changes remain unresolved. A manifest declaration alone does not prove that presentation changed.

OpenAI's current packaging format uses the root manifest, fixed `mcp.json` path, and `extensions.com.openai.interface` for display metadata. The manifests refer to the official [plugin schema](https://agent-plugins.org/schemas/1.0.0/plugin.schema.json) and [MCP configuration schema](https://agent-plugins.org/schemas/1.0.0/mcp.schema.json). See [OpenAI's packaging documentation](https://developers.openai.com/plugins/build/plugins).

## Install the worker from this checkout

Use Python 3.11 or newer. From the repository root, on macOS or Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install '.[browser]'
.venv/bin/python -m playwright install chromium
.venv/bin/rdc init --root /absolute/path/to/allowed/workspace
.venv/bin/rdc serve
```

On Windows, use `.venv\Scripts\python.exe` and `.venv\Scripts\rdc.exe`, with a Windows path for the working root. Use `python` instead of `python3` when appropriate.

Initialize only a new profile. Existing state is preserved by `rdc init`, which refuses to overwrite it. Initialization defaults to review mode, workspace file roots, shell execution disabled, and native desktop input disabled. Configure the grants your workflow needs deliberately; see the repository [README](../README.md) and [security notes](../SECURITY.md).

Keep `rdc serve` running while AI clients connect. It owns the browser sessions. `rdc connect` attaches to it and reads the private agent token locally. Closing an AI connection or preview does not close that worker. Browser sessions still end if the worker itself exits.

The primary preview opens inside a compatible AI host. `rdc serve --open` optionally opens the separate owner administration dashboard for approvals and diagnosis.

### macOS permission walkthrough

For native-window previews, run `rdc setup-macos` with the worker's existing state directory. Setup prepares **RDC Window Preview**, checks Screen Recording and Accessibility separately, and explains how to add the exact helper in System Settings. The older **RDC** entry is separate. The owner must complete macOS consent/authentication; RDC cannot silently grant it. See the [step-by-step setup](MACOS-SETUP.md). Headless browsers need neither permission. Recheck after updating the helper.

Shared native mouse and keyboard actions require individual owner decisions even in trusted mode. This does not place an approval queue in the preview. Headless browser input and exact-window capture/resizing remain separate background routes.

## Make the command resolvable by the AI host

The portable manifest intentionally uses the executable name `rdc`. It must be on the `PATH` of the process launching the MCP server. Activating a virtual environment in one terminal does not automatically change the environment of an already running desktop app.

For a desktop app whose environment cannot find `rdc`, use a private local copy of `mcp.json` and replace `command` with the absolute path to your installation's executable. For example, use the actual `.venv/bin/rdc` on macOS/Linux or `.venv\Scripts\rdc.exe` on Windows. Keep machine-specific paths out of the shared package. Do not add token values to either manifest.

If the worker uses a custom state directory, append `--state-dir` and that directory to the bridge's `args`. It must select the same private state as `rdc serve`. Run `rdc doctor` with that profile to check dependencies without printing credentials.

## Load in a compatible host

Use the host's documented local-plugin or development-package workflow to load this repository root. Support for Agent Plugins packaging, MCP transport, and MCP Apps rendering are separate capabilities. If a host only accepts direct MCP configuration, configure the same command and arguments using its format; the repository contains [Codex](../examples/client-codex.toml) and [Claude Desktop](../examples/client-claude-desktop.json) examples.

After installing or refreshing the connection:

1. Call `rdc_system_status` and confirm the intended device and grants.
2. Retain this chat's actual browser/device/native-window session ID and pass it explicitly to `rdc_preview_open`. Native Mac windows use `rdc_window_list` then `rdc_window_open`. Never substitute the global desktop or another chat's source.
3. Confirm a live view actually renders inside the AI application before claiming embedded support.
4. Expand, restore, and close the viewer while a synthetic task runs. Reopen and verify the same job/session identity.
5. Confirm the host displays the RDC logo for the installed plugin. An image in the preview alone does not verify tool-identity branding.

The [host contracts](EMBEDDED-HOSTS.md) document supported modes and verification limits. In particular, the official OpenAI quickstart establishes tools in ChatGPT and Codex and optional UI in ChatGPT. Codex's built-in browser preview does not establish third-party RDC rendering. Claude Desktop supports MCP Apps, while Claude Code's documented quickstart is text-only.

## ChatGPT web and remote clients

This local stdio package depends on access to the machine running RDC. A hosted AI client cannot execute this command on a user's computer merely by reading the manifest, and its own `127.0.0.1` address does not point to the user's worker.

The companion [RDC ChatGPT gateway](../cloud-gateway/README.md) provides an owner-private Sites MCP route with an outbound device relay. The deployed gateway carries the actual RDC tool catalog, embedded resource and original logo. The private Site authenticates its owner; the gateway pins that principal and accepts work only for its configured device. A separate local `rdc relay` process polls the gateway over HTTPS, invokes the loopback worker using its agent token, and returns the retained result. It never uses the worker's owner token.

This private deployment route and public multiuser OAuth onboarding have different requirements. The alpha does not implement a general public ChatGPT OAuth service. A deployed private Site and supported ChatGPT connection can supply the private route, subject to the account's access and host capabilities. Hosted authentication, actual preview rendering and RDC tool branding each require a live acceptance check.

The **0.1.0a5** runtime has been installed with independent verification of all 52 live source hashes, the complete previous runtime backup and protected-state preservation. The matching owner-private gateway passed nine tests with no skips, TypeScript checking and its production build, then deployed successfully with MCP enabled. Private plugin **1.0.6** passed exact nine-file readback. Native worker status reported a5, diagnostics returned an available/ready report with `incomplete: false`, and mobile listing returned no configured profiles or sessions. Embedded rendering, display-mode behavior, the requested branding changes and an explicitly approved live cloud browser workflow remain separate checks. The independent guardian remains undeployed. See [verification](VERIFICATION.md).

### Pair a private gateway

Keep `rdc serve` running. Deploy the companion gateway with its documented MCP capability, D1 migration and R2 binding. Configure its owner-private authentication and paired device identity through the deployment's private settings. Obtain the Site service credential and generate an independent device credential. These values belong in private runtime configuration, never the source repository or an AI conversation.

Create a private local JSON file with these fields:

| Field | Value |
|---|---|
| `gateway_url` | Your actual private gateway's HTTPS origin |
| `device_id` | The worker identity being paired |
| `device_key` | Independent device credential matching the gateway configuration |
| `sites_service_token` | Site service credential for its private edge |
| `worker_url` | Local worker MCP URL, normally `http://127.0.0.1:8765/mcp` |
| `allowed_tools` | Optional explicit list of worker tools that this relay may invoke |
| `tool_timeout` | Optional local tool timeout from 0.1 to 120 seconds |

Use a regular owner-only file, mode `600` on macOS/Linux, and an appropriate account-restricted ACL on Windows. The device and Site credentials must be distinct. Then run:

```sh
rdc relay --config /absolute/path/to/private/relay-config.json
```

Add the same `--state-dir` used by the worker if it has a custom profile. The relay reads that profile's `agent-token` locally and journals operation state beneath it. No inbound network connection to the device is needed. Keep the owner administration endpoint local, and preserve the private Site access boundary. Gateway hosting and AI access have their own terms and costs.

### Tool catalog and pending operations

The alpha5 source preserves the **52 core tools** from alpha4, including the three credential request tools, native mobile tools and read-only `rdc_diagnostics_status`. The gateway adds **`rdc_connection_status`** and **`rdc_operation_status`**, producing **54 tools** when its bundled catalog matches the worker. When updating RDC, refresh the gateway's copied catalog, embedded HTML and logo with its `scripts/sync-rdc-assets.py` helper before deploying it. A stale catalog can omit new tools or preserve old schemas.

A host can retain an older tool inventory after a server and plugin update. The initial 41-tool snapshot is historical: the concurrent a4 follow-up recorded 53 model-visible tools, and the current coordinated a5 check separately confirmed 53, including mobile and diagnostics. The server exposes 54 tools because `rdc_preview_frame` is app-only. Use the tools and schemas actually exposed by the connected host; these observations do not establish a guaranteed refresh procedure for every host.

When the host requires account routing such as `link_id`, select an exact advertised account using the user's request and established context. Retain that account with the original operation, job, approval, credential and session identities throughout recovery. Resolve an ambiguous write target before dispatch. Local clients need no host account field unless their schema requires it.

Cloud mutations require a stable `_rdc_request_id`. Retry only with that same ID and identical original arguments. When a call returns pending, retain the returned `operation_id` and recover it with `rdc_operation_status`. This status tool does not execute the command again. Local command `idempotency_key` and credential request `idempotency_key` values remain part of the original arguments and serve a different layer of duplicate prevention.

The embedded viewer also recovers pending open, refresh and frame operations by their existing IDs. Hiding stops polling; reopening resumes the same session or pending recovery. It never converts a possibly executed mutation into a new request. A recovery deadline or expired observation asks for an explicit fresh observation.

The relay verifies the hash of the exact queued request, records admission before execution, persists results before upload, and resends only identical recorded results. A crash with an uncertain execution outcome does not automatically replay the action. These rules reduce duplicate side effects; they do not make arbitrary external workflows transactional.

The core `rdc_diagnostics_status` argument is an optional integer `limit` from 1 to 50; hosted schemas may also require account routing such as `link_id`. The tool reports predefined worker/relay incident categories and remains read-only during pause or review. It accepts no repair action or free-text payload. The local equivalent is `rdc diagnostics --state-dir /path/to/private/rdc-state --limit 20`. Check availability and incomplete-capture fields: Windows capture is unavailable, and a local history read cannot inspect another process's pending queue or liveness. The recorder adds no repair execution or update permission. [Diagnostic behavior and limits](DIAGNOSTICS.md).

Empty polls use adaptive backoff: 250 ms, 500 ms, one second, two seconds, four seconds, then five seconds. The gateway's bounded minimum poll delay also applies. The local delay resets immediately when an operation arrives, and there is no extra idle wait between queued operations. At steady idle this saves repeated requests, with up to five seconds of additional first-task pickup time after a quiet period, plus network latency. Execution heartbeats and conservative expiry checks continue unchanged.

### Credential permission prompts

The broker's aliases come from the private worker `credential-locators.json`, not the gateway. Use the owner administration page's credential configuration form to enroll a safe label, HTTPS origin, native provider and item locator. It generates the opaque ID and writes the private mapping atomically. The form has no password field, performs no vault enumeration or secret read, and does not itself authorize input. The agent can list opaque aliases, request a password fill and inspect status. Enrollment, alias removal, Allow Once / Always Allow / Deny and grant revocation stay in authenticated local owner administration. General `trusted` mode does not bypass these credential decisions.

The owner page presents a pending permission modal automatically. Dismissing it leaves browser sessions and jobs running. Operating-system authentication can still require its own native window. The initial providers target classic macOS Keychain internet passwords and Windows generic Credential Manager entries; Apple Passwords/iCloud, browser vaults and mobile providers are not universally accessible through these APIs. See [credential configuration and limitations](CREDENTIALS.md).

Other remote clients can connect through a secured authenticated HTTPS endpoint when their transport supports the worker's bearer header. The worker itself remains loopback-bound. A public multiuser connector needs additional onboarding, authentication and deployment work.

The shared package deliberately has no remote placeholder URL in its active `mcp.json`. Keep that portable local configuration intact and create deployment-specific settings only for a real endpoint with its private authentication ready.

## Distribution status

This repository supplies a local development package; package validation alone does not establish embedded rendering. The separately managed private App-backed plugin is saved and connected as recorded above. Public directory review and listing are not claimed. At the audit checkpoint, [TOC-CS/RDC](https://github.com/TOC-CS/RDC) contained `LICENSE` only; full source publication is verified separately after upload. GitHub source distribution and publication in an AI provider's plugin directory are different steps.

OpenAI's [submission documentation](https://developers.openai.com/plugins/deploy/submission) describes required listing URLs and icon requirements. Both icon fields point to the included original RDC image. Registering RDC separately is required for its identity to replace use of the existing Desktop Commander connector in a workflow.
