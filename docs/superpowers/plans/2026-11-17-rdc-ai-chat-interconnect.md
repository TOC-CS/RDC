# RDC AI Chat Interconnect Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a reusable, tested RDC cross-provider chat coordination skill with a durable Atlas Bus sandbox, terminal commands and a capability-gated chat surface contract.
**Architecture:** The new bridge consumes Atlas Bus v1 via injection, never replaces or mutates its owner source. One binding per trusted session principal, with stable idempotent envelope IDs, fetch and acknowledge phases, and explicit response correlation. CLI operates against a clearly labeled isolated synthetic BusStore. ChatSurface tests exercise new-chat opening, submit-once and reply observation without using any real provider login.
**Tech Stack:** Python 3.11+, standard library, existing Atlas BusStore v1 via optional installed checkout for sandbox, unittest, existing RDC project layout.
**Spec:** `docs/superpowers/specs/2026-11-17-rdc-ai-chat-interconnect-design.md`

## Global Constraints
- Preserve live Site v16 and hold v17; no production worker restarts, App/plugin mutation from source tests, or browser security workaround.
- Atlas Bus core remains in a different owner's checkout, with uncommitted work; integration must not mutate its files.
- No actual model inference, paid Grok requests, key reading, live chat enrollment or desktop foreground control.
- Every message is inert data. Sandbox `--synthetic-only` is explicit and never claims authenticated real chat access.
- Author in isolated `feat/rdc-chat-interconnect-20261117`, keep prior RDC worktrees and owner files untouched.

## Review Focus
- Same idempotency key after delayed retry: original receipt, no new message, regardless of time.
- Claimed message fetch without a matching holder/revision: deny and leave it claimable only under approved recovery.
- Reply sent to wrong parent/sender: deny, preserve parent correlation.
- Provider UI send that times out after submit: `OUTCOME_UNKNOWN`, never send again automatically.
- Host browser cannot navigate/click or is blocked: report capability unavailable and do not use alternate browser/shell paths.

### Task 1: Bus-compatible session bridge with TDD
**Files:**
- Create: `rdc/chat_interconnect.py`
- Create: `tests/test_chat_interconnect.py`

**Interfaces:**
- `ChatClient(bus, principal_session: str, *, project='rdc', clock_ms=None)`
- `client.send(destination_session: str, text: str, key: str, reply_to: dict|None=None) -> dict`
- `client.claim(holder: str) -> dict|None`
- `client.mark_fetched(claim: dict, holder: str) -> dict`
- `client.ack(message_id: str) -> dict`
- `client.confirm(message_id: str, evidence_digest: str) -> dict`
- `new_envelope(...) -> dict`, stable UUIDv4-shaped IDs using source/key.
- The bridge imports no global AtlasBus module and accepts an object implementing the actual v1 method signatures.

- [ ] Write positive two-way and negative sender, target, changed-key and no-replay tests with a temporary Atlas BusStore synthetic fixture.
- [ ] Run red tests and save failure receipts.
- [ ] Implement minimal bridge and rerun focused tests to green.
- [ ] Add timeout/expiration/lease, reply-hop budget and evidence-state tests; verify they fail before any new behavior code and pass afterward.
- [ ] Commit the scoped bridge implementation and tests.

### Task 2: Terminal CLI over the same durable bus
**Files:**
- Create: `rdc/chatctl.py`
- Create: `tests/test_chatctl.py`

**Interfaces:**
- `python -m rdc.chatctl --synthetic-only --atlas-source <existing Atlas checkout> --db <private temp path> init --session <id> [--session ...]`
- Subcommands: `send --from <id> --to <id> --key <stable> --text <bounded>`, `claim --as <id> --holder <id>`, `ack --as <id> --message-id <id>`, `reply --as <id> --to <id> --key <stable> --parent-id <id> --text <bounded>`, `status --message-id <id>`.
- CLI is explicit synthetic fixture only. `--from` and `--as` never independently authenticate human/model identity. No production daemon or live enrollment.

- [ ] Write failing subprocess test for two-way send/claim/ack/reply across separate invocations, including restart/dedup.
- [ ] Run red receipt and implement CLI using injected Atlas BusStore synthetic mode.
- [ ] Verify wrong target/oversized/duplicate changed key, failure exits and absence of key/token logs.
- [ ] Commit CLI and tests.

### Task 3: Provider chat surface contract and skill
**Files:**
- Create: `rdc/chat_surface.py`
- Extend: `tests/test_chat_interconnect.py`
- Create: `skills/rdc-communications/SKILL.md`
- Create: `skills/rdc-communications/references/integration.md`
- Create: `tests/test_chat_skill.py`
- Create: `docs/releases/RDC-CHAT-COMMUNICATION-SCOPED-REVIEW-20261117.md`

**Interfaces:**
- `ChatSurface` protocol: `open_new(provider) -> opaque_handle`, `submit_once(handle,text,request_id) -> evidence`, `observe(handle,after) -> list[observed_reply]`. `ChatSurfaceGateway.open_new(provider,request_id=...)` adds no-replay records for uncertain chat creation; future production must make these records durable.
- `ChatSurfaceGateway` requires capability/owner opt-in, preserves opaque handle, and declines unknown/blocked host operations. No explicit ChatGPT/Claude/Grok DOM selectors, browser cookies or token access.
- New skill documents bus, terminal and actual chat routing, plus the verified/synthetic versus live separation.

- [ ] Write failing tests for open/send/observe through one fake adapter, explicit owner authorization, and failed submit with no automatic replay.
- [ ] Implement only the generic gateway and verify tests green.
- [ ] Write skill behavior tests first: one baseline failure simulates claiming browser sessions from mere tab presence, another tests recovery without replay; then author skill and rerun.
- [ ] Run full RDC Python test suite; independent Atlas synthetic core tests separately if nonmutating, optional browser/compiled Node gateway checks.
- [ ] Build an exact commit/bundle/manifest for independent Atlas review, mark production integration OPEN, and preserve existing branch/worker. Do not merge/push/live deploy without a separate gate.

## Evidence and ownership
Write logs, manifests and bundles to `~/RDC-Development/checkpoints/rdc-ai-chat-interconnect-20261117`. No keys, provider conversations or other projects' private content in logs. Independent reviewer and live API/browser adapters remain UNVERIFIED until actually exercised.
