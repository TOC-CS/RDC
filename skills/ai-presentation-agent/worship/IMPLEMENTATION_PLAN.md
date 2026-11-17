# Builder Implementation Blueprint from the Worship Skill Research
**Audience:** The existing AI Presentation Agent development owner and Atlas reviewer.
**Status:** Design guidance only; no implementation authorized by this skill session.
**Required reading:** `SKILL.md`, `research/PROPRESENTER_OBS_RESEARCH.md`, and `HANDOFF_NOTES.md`.

## Prioritized engineering phases for the active owner
1. **Preserve the existing director:** Read current `src/deck.mjs`, `src/director.mjs`, `src/adapters.mjs`, managed service and Atlas acceptance status. Preserve single-owner live cue state, event IDs, safe hold and recovery. Avoid parallel presentation runtimes.
2. **Service content and library:** Design a service model containing setlists, song groups, repeated arrangement occurrences, sermon, NKJV reference-only fallback, prayers, timers and original/authorized media. Add content rights/provenance validation.
3. **Output and access partition:** Produce separate public auditorium, private stage and public stream views from one cue state. Private stage notes/chords/timers must never be serialized to public viewer or OBS Browser Source.
4. **ProPresenter-inspired layouts:** Implement a source-layer graph for public lyrics, media, Scripture, countdown, announcements, lower-thirds, titles, messages and optional masks. Provide audience and broadcast Looks independent of stage.
5. **OBS integration:** Reuse existing OBS adapter and verify actual scene-list discovery, live scene readback, transparent browser overlays, camera sources, audio sync, stream/record status, manual Preview/Program production and operator-granted scene changes.
6. **Voice and BandMates live following:** Reuse current cue filters. Validate repeated choruses, spontaneous repeats, sermon references, final transcripts, stable camera observations and manual operator commands at low latency. Keep AI inference away from MIDI/audio callbacks.
7. **Extended production:** Add authorized planning/song imports, confidence timers, mobile control, per-scene persistent overlays, projector/NDI/SDI adapters, reporting/copyright labels and separate public livestream comments moderation when the queued integration is ready.
8. **Optional ProPresenter adapter:** Retain official REST only as an optional route when the app, network permissions, target presentation ID and external readback have been verified on real software.
9. **Physical acceptance:** Rehearse on real stage display and audience projector, run OBS local recording and provider-specific stream preview under operator control, verify text, transitions, camera, audio latency, stream health, private data isolation, Stop and crash recovery.

## Acceptance test set for the builder
- One service item advances three destination views to their correct content while preserving distinct audience, stage and stream layouts.
- Stage notes and chords never appear in the public deck, broadcast overlay, screenshots/thumbnail caches or public API event payload.
- A worship leader repeats Chorus a third time and the agent locates the correct occurrence without skipping the next song.
- Pastor asks for an unplanned NKJV Scripture reference. Agent displays reference without inventing verse text; authorized text is added only through approved content source.
- OBS Studio Mode Preview remains separate from Program. Only a permitted Program scene action changes what the live viewers receive; readback catches mismatch.
- Correct scene and lower third remain consistent after a disconnect and reconnect; uncertain writes do not replay with a fresh operation ID.
- Livestream stream/record Start and Stop remain separate, high-privilege actions from ordinary slide cues.
- Dropouts, missing stream source, CPU spikes, video/audio sync and private monitor leakage produce bounded, understandable operator alerts, not unattended recovery actions.
- A failed song/asset import reports rights and availability explicitly and cannot silently substitute unlicensed material.
- After stop or crash, recovered deck begins held and output disarmed, with one deliberate operator reactivation.
- Test end-to-end using the actual supported hardware/software, with Atlas review, without claiming multi-screen reliability from a headless HTML test.

## Source files for future integration
Current active source entrypoints, owned by another session:
- `src/director.mjs`: authoritative event and slide cursor
- `src/deck.mjs`: existing deck contract and HTML renderer
- `src/adapters.mjs`: existing ProPresenter and OBS integration boundary
- `src/mcp.mjs` and `src/http.mjs`: AI host/control-plane integration
- `integrations/bandmates.mjs`: external musician cue metadata
- `docs/WORK_QUEUE.md`: active priorities and owner review gates

The skill pack leaves all of those files unchanged. Apply Superpowers brainstorming, test-driven development, troubleshooting and verification in the owner's build session, after reviewing the latest master plan.
