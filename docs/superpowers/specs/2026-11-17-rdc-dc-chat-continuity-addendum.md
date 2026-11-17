# RDC + Desktop Commander Two- and Three-Session Chat Continuity Addendum

Date: November 17, 2026 CST
Scope: Existing `feat/rdc-chat-interconnect-20261117` source
Approval source: User's explicit follow-up to focus on active ChatGPT session-to-session messaging, reuse the same skill through RDC and Desktop Commander (DC), and protect against chat messages interrupting a target connection that fails to resume.
Review: Isolated source development only. Live enrollment and production activation remain held.

## Primary scenario

One active ChatGPT session sends a message to one or two other active ChatGPT sessions. Each receiving session continues its existing task until a safe moment, then reads the message from an inbox and responds. Either RDC or DC can operate the same local session transport without creating competing queues. All messages in a three-party exchange use the same room correlation ID, with separately addressed, idempotent envelopes and replies.

This requires three distinct identities: tool/connector identity (RDC or DC), the model/provider identity (e.g. ChatGPT), and the current conversation/session identity. The first two do not establish the third. A tab title, browser URL, local terminal process, or arbitrary `--as` flag does not authenticate an actual chat session.

## Interruption failure to defend

A chat UI message delivered while another ChatGPT turn is generating can interrupt, replace or displace that turn. Loss of the browser/host connection afterward may prevent automatic continuation. A return value saying `submitted` or `online` alone cannot prove the recipient continued. A sender cannot issue `stop`, `pause`, `cancel`, `refresh`, keyboard input, or a new chat creation to wake or recover another peer merely by writing a message.

Use one of two explicit delivery paths:

**Pull-only (default, preferred):** The sender queues durable, recipient-addressed data through Atlas Bus. The receiving chat's own authorized, active assistant or tool checks the inbox at a safe moment and acknowledges delivery. Busy, disconnected, stale or interrupted participants stay unconfirmed. Their messages remain durable while subject to the bus's existing lifecycle/TTL policy. No browser compositor is touched and no model is forced to continue.

**Direct chat (optional, explicitly opted in):** Only an approved adapter and exact bound conversation may submit. Before posting, require proof that the recipient has an active session, is idle, has opted in to receive peer chat and exposes writable/observable host controls. The `ContinuityGate` checks a current heartbeat and session epoch, with a 90-second default stale threshold. If unverified, busy, paused, interrupted or not opted in, return DEFERRED without writing to the composer. DEFERRED is not itself durable queue admission; always queue first.

## Recovery state and authority

- `SESSION_BUSY`: recipient is working; no unsolicited chat submission; no inference that task is idle.
- `SESSION_STALE`: last verified heartbeat expired; no direct push.
- `SESSION_INTERRUPTED`: recipient/verified adapter observed an actual connection interruption; preserve the original task and delivery receipt without artificial resume.
- `DELIVERY_UNCONFIRMED`: a potentially applied host submission lost confirmation. The target may remain healthy; do not claim it stopped. Suspend all further direct peer pushes and no-replay the original request key until independently reconciled.
- After confirmed interruption or uncertain delivery, a same-epoch heartbeat cannot silently resume; require a newer connection epoch and verified recipient recovery. Even then, renewed direct-chat opt-in is separate.
- A peer never gains authority to report or clear another session's presence. An interruption to B must not cancel A or C.
- Session continuity state in this phase is volatile and deliberately fails closed after process restart. Production needs authenticated enrollment, durable receipt records and actual host readback before enabling direct pushes.

## Current validation boundary

The local prototype can demonstrate the above with synthetic ChatGPT identities, real Atlas Bus v1 SQLite fixtures and both terminal connectors. It cannot demonstrate actual ChatGPT to ChatGPT transcript delivery, model wake, browser chat recovery or protection against ChatGPT platform-specific interruption without an approved live host adapter in both recipient conversations.

Keep private RDC Site v16, existing plugin identity, Atlas Bus owner source, BandMates, and current client sessions unchanged until independent review. The previous v17 activation hold remains.
