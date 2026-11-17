# RDC communications: adapter and integration reference

**Version:** scoped prototype 2026-11-17 | **Status:** local software verification, no live provider enrollment.

## Three data planes, one identity

1. **Bus**: `atlas.bus.message.v1` existing `BusStore` carries message/correlation/causation IDs, sender/destination, stable idempotency key, TTL and delivery state. No production queue duplicates.
2. **Terminal**: `rdc.chatctl` invokes the same core across independent subprocesses. The supported prototype uses `--synthetic-only`; terminal flags do not authenticate a real chat owner.
3. **Direct chat surface**: `rdc.chat_surface.ChatSurfaceGateway` accepts a caller-injected, host-authorized `ChatSurface`. The adapter must implement capabilities `open_new`, `attach_existing`, `submit_once`, `observe`, optionally `reconcile`. A simulated host satisfies tests but creates no real chat on a provider site.

`rdc.chat_interconnect.ChatClient(bus, principal_session, project='rdc', clock_ms=...)` sends, claims, marks fetched, acknowledges, confirms and reads status. The principal must come from trusted enrollment in a future production implementation, never a user-controlled `--from` or a natural-language claim inside a bus payload. Atlas Bus synthetic fixture registration is currently the only supported mode.

## Verified terminal sandbox walkthrough

Choose a disposable directory the current user owns. The example uses test identities only and sends no network requests.

```bash
cd ~/RDC-Development/workspace/rdc-chat-interconnect-20261117
ATLAS=~/RDC-Development/workspace/Atlas-Build-Bus
DB="$(mktemp -d)/chat-fixture.sqlite3"
PYTHONPATH=. python -m rdc.chatctl --synthetic-only --atlas-source "$ATLAS" --db "$DB" init --session chatgpt-fixture --session claude-fixture --session bandmates-fixture
PYTHONPATH=. python -m rdc.chatctl --synthetic-only --atlas-source "$ATLAS" --db "$DB" sessions
PYTHONPATH=. python -m rdc.chatctl --synthetic-only --atlas-source "$ATLAS" --db "$DB" send --from chatgpt-fixture --to claude-fixture --key task-1 --text "Please review the synthetic task"
PYTHONPATH=. python -m rdc.chatctl --synthetic-only --atlas-source "$ATLAS" --db "$DB" claim --as claude-fixture --holder claude-fixture-operator
```

Read the claim's `message_id` and `revision`; `fetch --as claude-fixture --holder claude-fixture-operator --message-id ID --revision N` verifies that exact lease. Then `ack --as claude-fixture --message-id ID`, `reply --as claude-fixture --to chatgpt-fixture --parent-id ID --key reply-1 --text "Review completed"`, and `claim --as chatgpt-fixture --holder chatgpt-fixture-operator`. Use `status --as chatgpt-fixture --message-id ID` and `confirm --as ... --evidence-sha256 ...` only with actual synthetic evidence.

Each command is one process; the test database is persistent within that disposable directory. Identical duplicate sends reuse the immutable receipt, and changed text or destination with a reused key fails. Host enrollment and real production authorization remain disabled. Real Atlas runtime database paths are expressly rejected.

## Real chat session adapter contract

A **real chat** integration requires explicit operator approval for the exact provider, authorized session binding, and a host-verified new-chat or existing-chat handle. A provider adapter manages any confidential handle details internally and returns only an opaque ID, provider, mode and observed status to the gateway. Supported modes are `browser`, `desktop`, `studio` and `api`, each with independent verification.

`gateway.open_new(provider, request_id=stable_key)` requests a newly created session from the *actual* host and requires visible proof before saving its opaque handle. A failed/uncertain new-chat request remains `OUTCOME_UNKNOWN` under the same key; callers may not open a second conversation on a blind retry. The current gateway's in-memory receipts are synthetic only; a production adapter must persist them across restarts. `gateway.attach_existing(provider, reference)` binds only an owner-approved existing chat; it cannot crawl other tabs. `gateway.submit(handle, text, request_id=...)` uses exactly one mutating call. If response confirmation is lost, it returns `OUTCOME_UNKNOWN` and does not replay the operation. `gateway.reconcile(handle, request_id=...)` may advance state only after host-reported observed delivery. `gateway.observe(handle, after=cursor)` reads at most ten bounded visible messages from that exact conversation, with role and message ID.

Browser ChatGPT, Claude and Grok use app-specific host permission, a verified writable composer and a bounded observation **cursor**. The user’s open browser tab proves only a tab exists; it does not prove direct interactive access or consent to unrelated transcripts. In regular Chat mode, Browser may only expose read-only tab operations; unavailable write actions remain unavailable. A browser host security block must be honored and never bypassed by direct CDP, injected commands, cookie copying, or another account/tool surface.

**API distinction:** OpenAI developer `POST /v1/conversations` can create API conversations, but does not create consumer ChatGPT chat threads. Claude `POST /v1/messages` is stateless multi-turn: its authenticated caller supplies prior history. xAI exposes a Responses API and legacy chat completions; account access and charges must be independently checked. Each provider must implement its own certified transport and retain its API/session-specific history without claiming to control a browser chat. Official references:
- https://developers.openai.com/api/reference/resources/conversations/methods/create
- https://platform.claude.com/docs/en/api/messages/create
- https://docs.x.ai/developers/rest-api-reference/inference/chat-completions
- https://developers.openai.com/plugins/build/chatgpt-ui

## Planned live registration and ownership

Before enabling live delivery, add an authenticated server-side session adapter to RDC that binds source identities independently of user prompts and supplies per-project routing grants. Use Atlas Bus transactional idempotency, not a new SQLite state service. ChatGPT/Claude/Grok sessions must opt into receipt and polling in their own permitted UI/tool path. One session’s API client authentication cannot be borrowed to impersonate another session. A real sender must observe that the destination got the message and verify its response before marking an action confirmed.

`OUTCOME_UNKNOWN` from an uncertain browser or terminal send is an operator reconciliation state, never permission to dispatch a duplicate. Replies must preserve the root correlation and point at the exact originating causation message. A destination that is idle, offline or unenrolled remains stale/unknown; a session is not running solely because the bus contains a message.

## BandMates AI Studio connection

**BandMates** requires a first-class authorized adapter, supporting the same ChatSurface/bus protocol while reusing the Studio’s own application control/command bus. The current CLI `bandmates-fixture` is an RDC-project synthetic endpoint only. Atlas Bus currently denies cross-project send by default; production BandMates integration needs independent enrollment and explicit cross-project ACL design and acceptance.

Prioritize non-real-time operations such as status requests, channel and preset inspection, studio session cues and verified mixer-control proposals. A future Studio response must originate from its own authenticated app command interface, return source identity and operation receipt, and be observable through the chat/bus response path. An AI chat's text cannot directly change the live audio encoder, MIDI routing, musician transport, stage output, talkback, active mix or playback without the existing Studio permissions and operator approval.

**Never block an audio or MIDI callback while waiting for AI chat, network or SQLite bus delivery.** Relay control and status events asynchronously outside the real-time path with bounded queues and explicit prioritization. Keep live BandMates, Presentation Agent, Atlas Bus and existing RDC workers unchanged until each owning session accepts and tests its adapter.

## Verification

Prototype evidence in `~/RDC-Development/checkpoints/rdc-ai-chat-interconnect-20261117`. Focused suites include `tests.test_chat_interconnect`, `tests.test_chat_atlas_compat`, `tests.test_chatctl`, `tests.test_chat_surface` and `tests.test_chat_skill`. Run full RDC Python and gateway suites before any scoped review. A synthetic test verdict does not qualify consumer ChatGPT/Claude/Grok live messaging, app-install publication, or autonomous BandMates integration.
