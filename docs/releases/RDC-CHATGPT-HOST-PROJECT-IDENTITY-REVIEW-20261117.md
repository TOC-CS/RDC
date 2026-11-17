# RDC ChatGPT Host Identity and Project Messaging Review

TOC Ministries | November 17, 2026 CST

**Review state:** Scoped source verified on local macOS; independent Atlas/GitHub hosted review pending.
**Release state:** Public release ON HOLD until real ChatGPT-to-ChatGPT communication is fully operational.
**Production:** Existing RDC Site v16, current worker and BandMates runtime unchanged.

## Goal

Make one-time activated RDC and Desktop Commander (DC) project communication work from any authenticated ChatGPT conversation in that project without repeated owner prompts. Preserve the active receiving chat, sender/recipient identity, idempotent receipts and task continuation. Add an approved create/wake path only where the actual host supports it.

## Source changes

- `rdc/chat_project_actions.py`: durable owner-activated `create`, `wake`, and `message` grants. Replay-proof activation/revocation evidence, project-scoped authorization, host capability gate, durable operation receipts and no-replay behavior after uncertainty. All host calls injected/simulated for now.
- `rdc/chatgpt_identity.py`: use trusted ChatGPT plugin tool-call metadata `_meta["openai/session"]` and `_meta["openai/subject"]` to derive private HMAC session pseudonyms. A separate trusted project membership provider is mandatory. Raw metadata and model-filled project fields never grant identity. No real project API assumed.
- `rdc/chat_project_messages.py`: source/recipient project checks and the one-time `message` grant before using the unchanged Atlas Bus v1 `rdc` platform namespace. This layer distinguishes native ChatGPT Project subtenants while Atlas only has four fixed platform project names. Direct access to raw Atlas bus can bypass this subtenant gate and must remain unavailable to model tool inputs.
- `cloud-gateway/lib/rdc-gateway-core.mjs`: new read-only `rdc_chat_session_status` tool. It reads authenticated MCP tool-call metadata, hashes it with optional server-private `RDC_CHAT_IDENTITY_SECRET`, and reports project verification and create/wake/send availability as FALSE. Missing key or metadata fails closed. No worker job, D1 schema or new Site deployment.
- `cloud-gateway/tests/gateway.test.mjs`: positive, negative, owner isolation, spoofed field refusal and no raw identity leak tests.
- `skills/rdc-communications/SKILL.md`, `references/project-activation.md`, and new `references/chatgpt-host-integration.md`: accurate source/host boundaries, public release hold, and documented Work-chat MCP Events potential.

## Verification receipts

- TDD red→green for absent ChatGPT identity broker, missing project-scoped messenger, new gateway tool and missing skill reference.
- Focused identity/project/skill integration: 36/36 pass, no failures. `~/RDC-Development/checkpoints/rdc-chat-cross-tool-20261117/chatgpt-mcp-project-host-GREEN-20261117.log`.
- Full RDC Python suite with Atlas Bus synthetic source: **449 tests run, 0 failures, 26 expected skips**, completed in 137.578 seconds. `chatgpt-host-identity-FULL-20261117.log`.
- Cloud Gateway Node suite: **47/47 pass**, 0 failures, including original 45 gateway regressions. `chatgpt-mcp-gateway-session-GREEN-20261117.log`.
- Source `python -m compileall` and `node --check` passed. Git whitespace and remote branch compatibility to be verified before publication.

## Live feasibility and gating

OpenAI's current plugin documentation provides two anonymized tool-call metadata identifiers for user and chat. It does **not** expose a documented native ChatGPT Project ID in those metadata fields. The gateway's returned opaque session ID therefore establishes only request correlation, never verified project membership. A host-owned project resolver/enrollment service is required before accepting real messaging or project grant activation.

Official MCP Events support user-selected subscriptions in Work chats on web and Cloud desktop, and dots, with signed webhook delivery. This route can notify a subscribed Work conversation, but an unsubscribed ordinary ChatGPT conversation is not guaranteed to wake. One RDC project grant cannot override provider event subscription permissions.

Actual in-model ChatGPT conversations require an approved inbox/outbox MCP tool in both receiving and sending sessions, separate trusted membership, delivery receipt readback and continuity under interruption. The source prototype and existing Chrome tabs do not establish any of those live capabilities. Browser security refusals are not grounds for unapproved CDP, cookie copying or shell-injected chat composer actions.

No private secrets, provider credentials, real chat transcript content, user project metadata, physical MIDI/audio devices, production D1/R2, live worker or Site v16 were changed by this scoped development. Public listing and production activation remain ON HOLD until independent review and operational demonstration.
