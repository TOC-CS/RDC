# Presentation Agent + RDC/DC communications

**Scope:** 2026-11-17 isolated software prototype. This guide integrates the existing **RDC Communications** skill with the Presentation Agent. It does not create a second bus, launch another AI host, or authorize production output.

## Existing three communication routes

Use the already owned RDC communication source at `~/RDC-Development/workspace/rdc-chat-interconnect-20261117/skills/rdc-communications/SKILL.md` and `references/integration.md` for authoritative instructions.

1. **Message bus:** `atlas.bus.message.v1`, shared Atlas Bus `BusStore`, immutable message ID, room correlation ID, reply causation, stable idempotency key, TTL, bounded hops, per-recipient claim/fetch/ack and independent action confirmation. Reuse `rdc.chat_rooms.ChatRoom` for two-way and three-way room fanout. Each intended recipient receives its own durable envelope. The Presentation Agent never starts a new bus or asserts that queuing means the destination observed or responded.
2. **Terminal:** RDC durable `rdc_job_run` or Desktop Commander `start_process` can execute the SAME authorized terminal command on the same device/state. The development CLI is `python -m rdc.chatctl --synthetic-only` with explicit existing Atlas source and isolated fixture database. Its `room-id`, `room-send`, `claim`, `fetch`, `ack` and `reply` commands are **synthetic-only**. Do not run this fixture against live Atlas or RDC state.
3. **Direct chat:** `rdc.chat_surface.ChatSurfaceGateway` requires a real authorized host adapter that can open or bind exactly one approved chat, submit once, observe bounded replies and reconcile uncertainty. `ContinuityGate` prevents direct delivery to busy, interrupted, stale, unverified or unopted-in peers. Never interrupt another generating ChatGPT/Claude/Grok chat to insert a message. A bus message cannot automatically wake a model.

The current RDC/Atlas prototype has no authenticated consumer ChatGPT/Claude/Grok enrollment. Cross-project delivery is **CROSS_PROJECT_DENIED** until Atlas owner independently grants a real presentation/BandMates ACL with source-bound identity. Use pull-only messages by default, and do not treat a browser tab or an API account as proof of a live enrolled chat. An uncertain send remains OUTCOME_UNKNOWN; do not replay it with a new request ID.

## New Presentation Agent interface (isolated source, undeployed)

Software tools:
- `presentation_communication_capabilities`: discover current two-way/three-way support and actual HOLD flags without sending
- `presentation_communication_prepare`: prepare bounded, read-only cue status for 2 or 3 exact intended room participants. It includes slide ID, section/occurrence, hold/armed state and software output-fault metadata only. It never includes private notes, stage scripts, licensed lyrics, raw transcript, owner path, room bearer, app credential, ChatGPT transcript or source device identifier

Operator-authenticated HTTP routes in isolated software:
- `GET /v1/communications/capabilities`
- `POST /v1/communications/prepare` with `{localSessionId,roomMembers,roomKey,requestId}`

These routes return a **draft**, not a message sent, chat opened or a session enrolled. They have no native output authority. The bridge never automatically advances a slide or controls a live output. `src/rdc-communications.mjs` contains `preparePresentationRoomStatus`, `preparePresentationRoomReply` and `PresentationRoomDelivery` for trusted host adapters. Sending through `PresentationRoomDelivery` stays HELD unless a separately authenticated RDC room binding and operator approval are injected by the actual host. In the tested synthetic fixture it reports SYNTHETIC_ENQUEUED, never live recipient observation. Real integration must retain the bus's own IDs and receipts instead of minting another message identity here.

## Coordination examples

A room might contain `presentation-fixture`, `rdc-fixture` and `bandmates-fixture` inside one isolated authorized RDC sandbox. The Presentation Agent supplies only its read-only status draft. RDC's `rdc.chat_rooms.ChatRoom` performs the true per-recipient message fanout on Atlas Bus. Recipients fetch, acknowledge, and reply under the same room correlation with exact causation. The test `tests/presentation-rdc-rooms-terminal.integration.test.mjs` exercises this using the **actual RDC synthetic `rdc.chatctl`** and a disposable bus database, with no live chat or Studio control.

A future real three-way room may link the human leader, Presentation Agent and BandMates/mix engineer via independently enrolled host sessions. The AI musician and mix engineer may use their own independently authorized voice talkback. A chat request for present slide status can produce a reviewable status reply draft. Any request to change projector slides, hold/resume, show stage-private text, change OBS Program, start/stop a stream, change mixer faders, inject AUX tracks or direct MIDI remains a proposal requiring the exact existing app authorization and actual output readback.

The Presentation Agent consumes only confirmed BandMates performed song section events through its separately qualified non-real-time control plane. Planned accompaniment is not evidence of lyrics actually sung. **No AI network or bus call may run inside a real-time audio/MIDI callback.** Preserve all manual hold and emergency stop controls, distinct per-project ownership, existing bus transport, and presentation-private stage permission.

## Production and Atlas gates

This source package and local skill reference are software artifacts, not a published new ChatGPT plugin release. Live Atlas enrollment, CROSS_PROJECT_DENIED grants, authenticated RDC and Desktop Commander dual transport, host ChatGPT/Claude/Grok composer control, verified recipient readback, durable operation recovery, stage/private data privacy and full device/venue acceptance remain OPEN.

Do not claim production 2/3-way communication from a successful synthetic fixture, a saved skill, a GitHub branch or a locally authenticated iMac. Keep the current main AI Presentation Agent plugin and RDC Site/worker unchanged until the independently approved integration and release gate are met. If a host can only read chat tabs, keep direct delivery unavailable; do not bypass that restriction using CDP, cookies or shell UI injection.
