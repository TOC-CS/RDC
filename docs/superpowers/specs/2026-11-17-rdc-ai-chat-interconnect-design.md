# RDC Cross-Session AI Communication Design
Date: 2026-11-17 CST
Owner: TOC Ministries | scoped RDC continuation
Status: DESIGN ADOPTED FOR AN ISOLATED, SYNTHETIC-FIRST DEVELOPMENT SLICE. The owner specifically directed immediate implementation and three transport methods. Live enrollment and production publication remain separate gates.

## User intent
Enable an AI operator in ChatGPT, Claude, Grok or another compliant browser, desktop or API client to discover permitted chat sessions, create a new session, send a task or question, receive replies and maintain two-way coordination. The same message identity and status must be accessible through a durable bus, a terminal interface and authorized chat session controls. Avoid repetitive copy/paste and blind background execution.

## Brainstormed approaches
1. **Browser-only automation:** attractive for existing tabs, but DOM and host privileges differ per client, current ChatGPT browser access is restricted, and UI submission can become uncertain. Rejected as the sole control plane.
2. **New standalone message server:** could support any provider but duplicates TOC's existing Atlas Build Bus and its state/authorization logic, creates extra credentials and risks split-brain delivery. Rejected as the default.
3. **Atlas Bus core with RDC session adapters (selected):** reuse the established `atlas.bus.message.v1` identity, idempotency, lease/TTL, explicit fetch, action evidence and no-replay contracts. One provider-neutral adapter surface supports bus, CLI and hosted chat, with each path reporting its own verified capabilities. Initial implementation runs only with an injected, isolated, synthetic `BusStore`; no live enrollment.

## Three real integration lanes
**Bus:** an authenticated future coordinator maps enrolled RDC chat identities to Atlas Bus session principals. All outbound envelopes carry one immutable message ID, one source and one destination, correlation/causation ID, bounded text payload, TTL and stable idempotency key. Producer messages, recipient fetch, acknowledgment and verified action are separate phases. The bus never executes instructions contained in a message.

**Terminal:** a local `python -m rdc.chatctl` command uses the *same injected BusStore* and can initialize synthetic ChatGPT/Claude/Grok endpoint fixtures, send messages, poll messages, acknowledge and reply across separate CLI invocations. This is a functional test/owner training lane, not a real provider login. A future production terminal broker must use an owner-private identity/secret broker with per-session authorization, not trust arbitrary `--from` flags.

**Chat/UI/API:** a provider-neutral `ChatSurface` contract describes `open_new`, `submit_once`, `observe` and optional `reconcile`. An adapter may use the verified native chat SDK, a host-approved browser/desktop agent, or a separately authorized provider API. Opening a new **API conversation** does not create a chatgpt.com/claude.ai/grok.com consumer conversation. Existing GUI chat is accessible only when the operator has explicit permission and the actual host/browser allows observe, click and type. Never access browser cookies, bypass an origin/security restriction, take over hidden chats or claim a new session was created without visible readback.

The current ChatGPT Browser plugin has read-only capabilities in regular Chat, and the ChatGPT Sites/Settings origin was explicitly blocked; no alternate driver or shell injection may bypass that denial. New ChatGPT conversation opening remains UNVERIFIED here. Claude browser-use exists for API-operated applications, not authority to control unrelated Claude.ai sessions. Grok/xAI developer inference is billable under the current TOC budget and disabled unless separately approved.

## Session identity and delivery
A bridge client binds its `principal_session` once from a trusted adapter context. A message body cannot change that identity. It may only address an enrolled, explicitly allowed recipient in the same project; default cross-project routing denied. In the synthetic phase, identity is fixture-only and must never be described as independently authenticated.

Message IDs are deterministic UUIDv4-shaped values derived from source + idempotency key; duplicate requests reuse the original exact envelope and return its immutable receipt. A changed payload or destination under the same key conflicts. New messages are limited to 3,000 Unicode characters of nonsecret text, 32 KiB canonical envelope, max 3 hops and 6 replies per conversation under existing Atlas policy. No infinite responder chains or silent broadcasts.

A recipient fetch must confirm the claim holder and revision, record `ADAPTER_FETCHED` before exposing content, and acknowledge receipt only after the specific consuming session sees it. A browser/API side effect is `ACTION_CONFIRMED` only after readback of the actual target chat; missing readback is `OUTCOME_UNKNOWN`, not a re-send. Creating a new chat is also a mutation requiring a stable `request_id`: if a host times out after possibly opening the conversation, the adapter retains an uncertain receipt and forbids blind duplicate session creation. Prototype receipts are only in memory; a production implementation must persist them before any external action. TTL and retry behavior come from Atlas Bus v1.

## Source and integration boundaries
- RDC canonical local source remains in `repair/preview-v8-host` and its scoped `fix/code-context-read-scope-20261117` branch; isolated new worktree is `feat/rdc-chat-interconnect-20261117`.
- Preserve the Atlas Bus owner's uncommitted `atlasbus/`, its tests and review packet. New RDC code may import a compatible BusStore ONLY for synthetic fixture execution; it may not modify or launch the real Atlas Bus.
- No new network service, model inference, extra browser profile, native desktop input, paid API keys, App change, live worker restart, Site migration or GitHub push in this development slice.
- Use Superpowers brainstorming, writing-plans, TDD, systematic-debugging and verification; an independent reviewer must decide merge or live activation.
- First capability release is a reusable skill and testable synthetic direct terminal/bus session bridge. A production ChatGPT/Claude/Grok UI adapter requires per-host controls and live consent evidence.

## Acceptance and negative cases
1. Two-way ChatGPT/Claude/Grok *labeled synthetic* sessions exchange messages and replies through the real Atlas Bus v1 sandbox, across separate processes, with exact causation/readback.
2. Duplicate send returns the original receipt. Changed text or recipient with same key is rejected. Unauthorized principal, wrong recipient, self-send, cross-project, oversize text, invalid kind and fabricated provider acknowledgment fail closed.
3. Fetch, explicit acknowledgment and action confirmation remain distinguishable. An uncertain browser/API submission is never blindly retried. The verified chat UI destination is necessary to mark a chat action complete.
4. A chat surface fake proves opening a new session, submitting once and observing a reply. A missing host capability raises a clear `UNAVAILABLE` without creating a new session or navigating to blocked origins.
5. Real browser consumer sessions, provider API account billing/permissions, Windows/Linux cross-platform behavior, live Atlas enrollment, ChatGPT plugin publication, and whole RDC deployment remain OPEN until independently tested.
