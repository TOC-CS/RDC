# RDC and DC Chat Session Continuity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Provide one reusable skill and testable bus/terminal framework for two or three active ChatGPT sessions communicating through either RDC or Desktop Commander, without unsolicited messages interrupting or stranding another chat's work.

**Architecture:** The actual Atlas Bus v1 handles durable message identity, receipts and recipient-specific delivery, while RDC and DC invoke the same synthetic CLI against the same authorized iMac sandbox. `ChatRoom` fans out to peer inboxes. `ContinuityGate` tracks recipient readiness and recovery, and `ChatSurfaceGateway.deliver_peer` refuses unsolicited direct chat submission unless the host has explicit recipient opt-in and fresh evidence.

**Tech Stack:** Existing RDC Python 3.11+ source and tests, Atlas Bus v1 synthetic fixture, SQLite, standard library, existing Cloud Gateway regression tests.

**Spec:** `docs/superpowers/specs/2026-11-17-rdc-dc-chat-continuity-addendum.md`

## Global constraints

- Direct chat delivery to any actual ChatGPT conversation is HELD pending host-origin permission, authenticated session identity, opt-in and real readback.
- Preserve existing RDC private Site v16, v17 activation hold, owner-private ChatGPT plugin identity, Atlas Bus source and BandMates active runtime.
- Use one stable idempotency key per intended operation and never blindly replay an uncertain mutation.
- Message data never grants authority to stop a model, cancel a terminal task, refresh a tab or assume another session has resumed.
- The same shared database is valid only on the same authorized machine in this prototype. Cross-host transport needs separate authenticated configuration.

## Review focus

1. Busy recipient receives an unsolicited direct chat message: prevent the host submit and leave the bus message untouched.
2. Host reply vanishes after a possible send: report DELIVERY_UNCONFIRMED, disable future pushes, preserve the original request identity.
3. Recipient connection stops and never returns: no wake, restart or false recovery; other participants continue.
4. Recipient heartbeat expires or a model restarts: require a new verified epoch and renewed opt-in.
5. RDC and DC use different terminal interfaces on one iMac: verify the exact same room correlation and durable receipts without duplicate sends.

### Task 1: Two- and three-member room fanout

**Files:** `rdc/chat_rooms.py`, `rdc/chatctl.py`, `tests/test_chat_rooms.py`, `tests/test_chatctl.py`.

- [x] Write failing tests for three-member fanout, shared correlation, causation, identical retry, wrong-room denial and cross-process terminal operation.
- [x] Observe RED for absent ChatRoom and CLI `room-id` / `room-send`.
- [x] Implement bounded recipient-specific `atlas.bus.message.v1` envelopes and CLI exposure.
- [x] Run 13 room/CLI focused tests GREEN.
- [x] Execute authorized real RDC and DC terminal calls against one synthetic DB; obtain six directed messages within one room without any real ChatGPT UI interaction.

### Task 2: Prevent peer message interruption and protect recovery

**Files:** `rdc/chat_continuity.py`, `rdc/chat_surface.py`, `tests/test_chat_continuity.py`, `tests/test_chat_surface.py`, `tests/test_chat_atlas_compat.py`.

- [x] Write RED tests for absent continuity gate, no-replay after unknown peer send, and peer spoofing of another session's readiness.
- [x] Require recipient-owned epoch heartbeat, bounded staleness, BUSY/INTERRUPTED/UNCONFIRMED fail-closed state, and explicit verified reconnection.
- [x] Add peer-specific `deliver_peer` route to `ChatSurfaceGateway`; preserve operator-directed `submit`.
- [x] Verify red-to-green interruption, unknown delivery, busy session and fresh-epoch tests.
- [x] Verify a queued Atlas Bus message survives a simulated recipient interruption and a database reopen.
- [ ] Real current ChatGPT model interruption/recovery test requires a separately authorized interactive recipient host and cannot be qualified by synthetic tests.

### Task 3: Publishable skill, evidence and release gates

**Files:** `skills/rdc-communications/SKILL.md`, `skills/rdc-communications/references/integration.md`, `tests/test_chat_skill.py`, review and evidence files.

- [x] Write failing skill contract tests for both RDC and DC, same room and 2-/3-way ChatGPT participants.
- [x] Add pull-only default, no automatic wake, forbid stop/refresh/overwrite, defer when busy, explicit resumed recipient opt-in.
- [x] Execute 40/40 current focused communication tests and read cross-tool room receipts.
- [ ] Record full final Python regression verdict (running), current gateway test verdict, exact source tree/hash and independent source review packet.
- [ ] Independent Atlas acceptance and public GitHub deployment remain separate from scoped local tests.
- [ ] Live private ChatGPT plugin skill installation or App code deployment must preserve its existing binding and be verified separately.

## Completion conditions

Only mark scoped local software READY_FOR_ATLAS_REVIEW after the final same-source test suite passes, the branch is committed and clean, and a versioned source/evidence bundle is verified. Never mark live ChatGPT-to-ChatGPT communication complete solely from synthetic session fixtures or terminal integration.
