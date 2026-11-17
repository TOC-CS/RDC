# Project activation and verified chat create/wake

## Public RDC and Desktop Commander skill

This **public** source is designed for any supported RDC or Desktop Commander (DC) installation. The same module, `rdc.chat_project_actions`, and the Atlas Bus room protocol can serve several ChatGPT conversations inside one project. The `message` grant is separate from `create` and `wake`; callers must be host-authenticated and bound to that project before messaging. It is currently a tested synthetic-host framework. A **real host** connection, authenticated user identity, and independently supported provider actions are still required before creating or waking real consumer ChatGPT conversations.

## One-time project activation

An authorized owner or administrator gives a single **one-time project activation** for explicitly selected `message`, `create`, and `wake` scope. The public skill uses a **project-scoped** persistent grant, a local state journal, and authenticated host capabilities. A trusted owner broker, never the model's text, verifies the approval. `ProjectActionStore.activate(project_id, capabilities, authority, proof)` stores the project grant, its revision, and a digest of the used proof in a private local SQLite state journal. It never stores an API key or the raw approval proof. `ProjectActionStore.revoke` revokes the grant and prevents stale activation evidence from reviving a revoked project. A new owner approval is required for reactivation.

Once active, all **host-authenticated** chat sessions enrolled in that exact **source project** may call `ProjectChatActions.create` or `ProjectChatActions.wake` with **no repeated approval** for each operation. RDC, Desktop Commander and later AI-client adapters use this same grant. It persists across broker restarts. The scope cannot be used by another project, unauthenticated tab, guessed conversation ID, unverified model, or injected chat message. The owner may revoke it once for every member. More sensitive actions need separately defined grants. The grant never overrides provider, browser, account, or operating-system permission checks.

The demo implementation takes trusted `session_verifier`, `host`, and `authority` objects. In a real ChatGPT plugin, `_meta["openai/session"]` and `_meta["openai/subject"]` identify an authenticated tool-call session, but do not reveal its native ChatGPT Project. Use the separate [ChatGPT host integration](chatgpt-host-integration.md) guide and a trusted project membership registry; never rely on a supplied project slug. The included tests use fake host identities. User-supplied flags such as `--from`, untrusted web text and a copied session ID must never be interpreted as proof. This prototype is **without side effects** against real ChatGPT accounts, because it contains no provider credentials, browser driver, or live ChatGPT host.

## Verified create action

`ProjectChatActions.create(session_handle, provider, request_id=stable_key)` first checks that the source chat is authenticated for an active project grant and that the real host advertises `create_in_project` and `inspect_chat`. It records an immutable `OUTCOME_UNKNOWN` entry before calling the host. Only an observed, matching provider, source project and opaque conversation ID can become `CREATED_VERIFIED`. A timeout or mismatched project leaves `OUTCOME_UNKNOWN`, and retries recover the original result without opening another conversation. Independent actors have distinct idempotency namespaces.

An OpenAI API-created conversation is separate from a **consumer ChatGPT** conversation in the ChatGPT web/app interface. The target must be verified through the actual authorized UI/App host when consumer chat is requested.

## Verified wake action

`ProjectChatActions.wake(source_handle, target_reference, request_id=stable_key)` requires the same project grant, an authenticated source, an independently verified target, and the real host's `wake_existing` and `inspect_chat` capabilities. Its preflight accepts only a target the host observes as `suspended` or `waiting_for_message`. **Busy**, generating, **interrupted**, disconnected, stale, unverified, and cross-project sessions are deferred without a host mutation. No message injection, Stop action, page refresh, tab activation or synthetic keyboard shortcut is authorized by a wake request.

A supported host can return `WAKE_SIGNAL_OBSERVED` after verified readback of its signal. The same project scope remains enforced on the receiving session. The receipt explicitly records `model_resumed: false`, meaning the model's task continuity still requires proof. There is **no guaranteed wake** of a ChatGPT model where the provider has not exposed a real host capability to do that. An absent capability fails closed, and any pending work remains pull-only in the Atlas Bus.

An uncertain create or wake produces `OUTCOME_UNKNOWN`; it is never blindly retried even after the broker restarts. Receipts are stored before the possible external side effect and bound to source project, session, request key, action and target. A conflict under the same request key is rejected. Verified readback is necessary to advance an unknown outcome.

## Public publication and real-host qualification

This framework is intended for public GitHub and future public ChatGPT App distribution. GitHub source availability and plugin marketplace discoverability are separately verified. The existing personal plugin can remain private during development. Public release is held until the real ChatGPT host adapter, project verification, and wake handling work end-to-end and pass independent review. Public docs, source archives and tests must exclude private credentials, cookies, chat transcripts, device addresses and personal metadata. The validated source code does not grant real host access on installation alone.

Before enabling a live host, test one-time project enrollment, revoke/reenroll, permission boundaries, crash-safe operation receipts, actual consumer-chat creation, observed wake signals, and the existing continuity safeguards. Require evidence from both sender and receiver conversations that in-progress work was preserved. The app cannot automatically wake or resume a model from a terminal-only bus record.
