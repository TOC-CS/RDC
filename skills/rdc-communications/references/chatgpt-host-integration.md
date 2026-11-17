# ChatGPT in-model communications, host identity and supported wake paths

**RDC/DC development source | 2026-11-17 | Public release on hold**

## Host metadata available today

The official ChatGPT plugin MCP tool-call context may contain
`_meta["openai/session"]`, an anonymized conversation ID, and
`_meta["openai/subject"]`, an anonymized account ID. The official
documentation defines them for correlating tool calls and identifying a
user. They are not supplied as a ChatGPT Project ID and are not, on their
own, a signed authorization grant.

The new `rdc.chatgpt_identity.ChatGPTToolIdentityBroker` accepts these
values only from authenticated, host-provided MCP tool context. It rejects
unverified transport or missing metadata, and derives a stable,
project-scoped opaque actor ID with a server-private HMAC secret. The
original subject/session metadata is not copied to a model-visible result.
Never accept a copied `_meta`, raw conversation URL, browser tab title,
or a self-reported project value from a tool's ordinary arguments.

A **trusted project registry** must separately resolve the verified
subject and session into their true ChatGPT project membership. The
metadata fields above do not provide that membership. If the host or
enrollment service has no such verified mapping, report **unverified project**
and refuse to infer it from a model's prompt. This remains a live
integration gate for automatic enrollment of any chat inside a native
ChatGPT Project.

Reference:
https://developers.openai.com/plugins/reference
https://developers.openai.com/plugins/changelog

## Multiple ChatGPT project sessions and Atlas Bus

The user's desired **one-time project activation** grants explicitly chosen
`message`, `create`, and `wake` scopes to authenticated sessions of one
project without repeated approval prompts for each action. The owner can
revoke the grant. `ProjectActionStore` persists project permissions,
operation receipts, and consumed one-time proof digests.
`ProjectChatActions` models create/wake requests with no-replay and host
readback. All of these run through synthetic hosts today.

The actual Atlas Bus v1 permits platform project IDs `rdc`,
`atlas`, `bandmates`, and `presentation`. A native ChatGPT Project
ID is a **separate subtenant** inside the RDC platform domain. The new
`rdc.chat_project_messages.ProjectScopedChatMessenger` takes opaque
session handles, checks a trusted project resolver, enforces the active
`message` grant, and only then addresses the existing Atlas Bus v1
within its `rdc` domain. Direct use of the raw bus would skip the
ChatGPT subtenant check, potentially permitting cross-project message leakage; a production gateway must keep all sender and
recipient operations behind the authenticated broker, with independent
Atlas source review before enrollment.

Two or three project sessions can then send separate, durable messages
and correlated replies over the same room, whether the existing RDC or
Desktop Commander client initiated the terminal/tool call. A message
read by a synthetic recipient is not a message appearing in an actual
ChatGPT transcript.

## Supported wake and notification path

**MCP Events** supports user-selected subscriptions and webhooks for
**Work chats** on ChatGPT web and Cloud desktop, as well as dots. A
subscribed chat can receive an authorized event such as
`message.created` and follow the user's configured response
instructions. Subscription, expiration, callback verification,
signatures, account access, and server-side filtering must be
implemented and verified. Ordinary Chat mode is not listed as an
MCP Events destination in the current documentation.

Reference:
https://developers.openai.com/plugins/build/mcp-events

There is **no automatic wake** or **cannot guarantee** model resumption
from a normal ChatGPT message bus record. A created ChatGPT developer
API conversation is different from a consumer ChatGPT Project chat.
A terminal or browser tab cannot guarantee model resumption or the
continuation of the recipient's prior work.

Native create or wake actions, where available, require explicit
approved host permissions and **verified readback** of the actual
ChatGPT conversation. `ProjectChatActions.wake` returns
`model_resumed: false` even after an observed host wake signal; the
runtime must separately verify continuation. Model-resumed remains a separate outcome requiring independent evidence. There is **no direct
browser injection** into busy, interrupted, or unverified sessions. No direct browser injection is an authorized fallback for an unavailable host tool.

The default mode for ordinary chats stays **pull-only**, protecting the
recipient from interruption. A hosted event route must honor the
subscription and account's own controls, not pretend that a single RDC
project grant overrides ChatGPT's provider-managed event opt-in.

## Release and security boundaries

The source is intended for future **public release**, but availability
is **on hold** until actual ChatGPT-to-ChatGPT message delivery,
host-verified project membership, authenticated browser/app session
creation and wake, cross-tool continuity, Windows/Linux coverage,
and independent review pass. The existing user-private ChatGPT RDC
plugin can receive development skill updates without publishing the
App or changing its audience.

Do not include credentials, device IDs, private source chat text, HMAC
keys, bearer tokens, or webhook signing secrets in public documentation
or ordinary tool responses. Host authentication and MCP event webhook
verification remain outside the test-only identity module.
