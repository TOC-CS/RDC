# Authenticated ChatGPT conversation messaging interface

**RDC/DC development update | not deployed to live Site v16 | public release held**

## What this implementation adds

The offline RDC Cloud Gateway now advertises callable MCP tool schemas for the host-backed live session interface:

| Tool | Purpose | Operation |
| --- | --- | --- |
| `rdc_chat_inbox` | Read bounded new messages addressed to the currently authenticated chat | Read |
| `rdc_chat_send` | Queue one idempotent peer message | Mutation |
| `rdc_chat_reply` | Reply preserving the original message lineage | Mutation |
| `rdc_chat_ack` | Confirm the exact recipient message was observed | Mutation |
| `rdc_chat_create` | Create a new session under an active one-time project grant | Mutation |
| `rdc_chat_wake` | Request an approved host wake signal for a safe target | Mutation |
| `rdc_chat_route_status` | Inspect available independently approved routes | Read |
| `rdc_chat_cross_project_send` | Send only through a separately approved Atlas inter-project dispatcher | Mutation |

The tool schemas are **not deployed** to the existing ChatGPT RDC Site v16. Adding this skill to the installed plugin alone will not create new callable tools. The Site source requires an approved release, a fully implemented and separately qualified host adapter, a private project membership resolver, and a durable no-replay delivery backend. Without that adapter, the candidate returns `chat_bridge_not_enrolled`; it does not contact another ChatGPT session or create a worker job.

The host owns `chatRouter.invoke`, injected into `createGateway`. It must verify the authenticated account, the true source conversation, and session membership in the exact project using independent host-side evidence. Raw `_meta["openai/session"]` and `_meta["openai/subject"]` are useful for correlation but are not independently verified ChatGPT project membership. Tool parameters cannot supply a different source or source project; the gateway rejects those fields.

## Project permissions and intended behavior

One-time project activation grants enrolled, **independently verified** sessions `message`, `create`, and `wake` permissions as approved. It provides no repeated user prompt for each operation within that grant, but it never bypasses ChatGPT or OS-level capabilities. A recipient must independently verify enrollment, permitted project membership, and its current connection state.

Every mutating call requires a stable `_rdc_request_id`. The host adapter is the authoritative durable idempotency and **no replay** source. It must record `OUTCOME_UNKNOWN` before any external side effect, return the original receipt for retries and never replay a possibly delivered operation. A write without verified recipient acknowledgment or reply readback cannot be called complete.

Unverified, busy, interrupted or stale chats remain deferred. The default is safe recipient pull from the bus; no browser takeover, Stop button click, refresh, modal injection, or forced model continuation. New chat creation and wake actions require host-advertised capabilities and verification that the expected actual ChatGPT conversation was created or signaled.

A message or wake signal in a model connector may not result in a running model. Native event subscriptions are provider-managed and distinct from the RDC project grant. Automatic wake of an unsubscribed ChatGPT chat is unverified.

## Validation and activation gates

The development gateway suite checks that all eight tool schemas exist, mutation keys are required, model-supplied source-project spoofing fails, and the unenrolled tool fails closed without touching the worker. An injected synthetic router demonstrates a positive receipt; the cross-project negative fixture demonstrates no routing without independent approval. These are protocol tests, not live ChatGPT sessions exchanging messages.

To activate real chat messaging: an approved private Site candidate must pass protected rollback qualification, the actual host project resolver must be connected, a bound sender and recipient must exchange an actual message in the ChatGPT interface, the recipient must acknowledge and reply, and the sender must read that reply in its original conversation. Independent Atlas management must approve each cross-project route separately. Keep Site v16 and public publication on hold until acceptance.
