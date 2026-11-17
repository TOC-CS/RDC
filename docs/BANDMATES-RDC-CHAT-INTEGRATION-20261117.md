# RDC ↔ BandMates AI Studio Chat Communication Integration

TOC Ministries | 2026-11-17
Priority: user-directed compatible endpoint for the RDC cross-chat skill.
State: current scoped RDC prototype verified only on synthetic endpoints. Live cross-project integration held.

## Reuse the BandMates owner’s actual work

A read-only source inspection on the iMac confirmed a BandMates-specific interoperability draft already exists:
- `workspace/BandMates/docs/RDC_MUSICIAN_CHAT_INTERCONNECT_2026-11-17.md`
- `workspace/BandMates/src/rdc-musician-interconnect.js`
- `workspace/BandMates/src/musician-voice-identity.js`
- `workspace/BandMates/src/talkback.js`
- `workspace/BandMates/docs/ai-bus.md`

That existing `RDCMusicianHandoffDrafts` protocol emits inert `atlas.bus.message.v1` proposals, identifies the local musician through a separately verified `MusicianVoiceMailbox` receipt, uses `source_project: bandmates` and `destination_project: rdc`, applies a five-minute TTL, rejects unsafe raw audio/live commands, and labels its delivery `NOT_CONNECTED`. The BandMates owner recorded 6/6 local contract tests and verified the actual Atlas Bus denies unauthorized cross-project messages. RDC must preserve this work and interface rather than replace it.

## Current RDC scope

The new RDC `ChatClient` supports same-project `rdc` synthetic identities only, and `rdc.chatctl` has a `bandmates-fixture` registered as a synthetic RDC project session. That fixture demonstrates how a message can be addressed to a labeled participant across separate terminal processes; it is **not** the real BandMates app or permission to claim a cross-project route.

The new `ChatSurfaceGateway` knows the provider label `bandmates` only when explicitly included in an owner-approved adapter capability list. It has no live Studio handle or UI connection. Direct chat-to-BandMates messages require real application adapter implementations and readback.

## Real end-to-end integration acceptance

1. **Atlas Bus owner** independently qualifies the core, authenticated per-session principals and cross-project ACL for `bandmates ↔ rdc` with explicit enrollment and least-privilege send/receive permissions. Current `CROSS_PROJECT_DENIED` remains authoritative.
2. **BandMates owner** retains all source-speaker identities, talkback conversations, voice mailbox verification and real musical control. Do not edit its active native app or its mixing, MIDI or AI music runtime from RDC development.
3. **RDC owner** provides the actual chat/terminal/API/browser adapters using a bound RDC identity, fresh session verification, stable idempotency and receipt readback. The typed payload maps the existing BandMates synthetic protocol, not a new unversioned transport.
4. **Approved command coordination** respects the actual BandMates session command bus `status`, `section`, `resume-form`, `style`, `levels` and `stop` with its own `bus.sessionId`, `source`, `sequence`, `expiresAtFrame` and `expectedRevision`. This is a **future** gate; no model chat text can directly claim a live actor role or skip the Studio controller's authorizations.
5. **Audio safety** forbids network/SQL/AI waits on any audio, MIDI, stage output, song following, synthesis or live playback callback. Route non-time-critical proposals and status through an independently bounded coordination queue outside the audio path.
6. **Verifiable example**: an authenticated ChatGPT operator requests BandMates status; RDC queues a scoped request; the Atlas Bus grants only this route; BandMates consumes through its approved adapter, verifies its control state and sends an authenticated reply; the original chat receives and displays the reply with source evidence and correlation. Each phase must be demonstrated in the real host, not only a fake browser or synthetic SQLite database.
7. An explicit operator approval is required for live mix/musician changes, recording, audience output, hardware I/O, new speakers, playback or a performance cue. Read-only questions can be separately authorized but still require trusted session enrollment.

## Separate release and work ownership

This document is an FYI integration update to the active RDC communication build. No BandMates files, app processes, hardware settings or presets were modified. The live RDC Site remains v16; v17 and cross-chat production activation remain held pending their independent reviews and protected rollback.
