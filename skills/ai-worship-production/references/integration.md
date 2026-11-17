# Worship production safety and integration

This companion skill is part of the existing RDC plugin. It must not replace the RDC App or presentation runtime. Use the original AI Presentation Agent skill for host-specific connection and managed-session setup.

## Current engine features

Single director for audience, stage, stream; independent Looks and visibility; authorized NKJV reference-only when Bible text rights are unspecified; repeated verse/chorus occurrences; operator-only current/next rundown; stage-only monotonic timer; transparent OBS-compatible browser layer; read-only OBS Studio Mode, Preview/Program, stream/record and dropped frame status; allowed source-bound cue following; manual hold.

## Permissions

`PRESENTATION_ALLOW_WORSHIP_LOOK_EDIT=1` for look/visibility edits. `PRESENTATION_ALLOW_STAGE_CLOCK=1` for timer writes, plus independent stage token. Private stage timer file must be a regular owner-owned 0600 file, no symlink. External app control, OBS scenes, streaming, recording, live comments and provider publishing are separately scoped. A successful command receipt never proves physical display output.

## Rehearsal checklist

Check source rights independently for congregation and public livestream; validate full song arrangement, repetition IDs and Scripture reference; inspect all output Looks; ensure public packets exclude private speaker notes, chords and tokens at source; test audience blank, stage clear and stream overlay clear separately; verify output recovery and manual override; use independent OBS Program and physical screen readback; record actual end-to-end latency with user-authorized devices; do not mark system complete from software fixtures.

## Platform and completion boundaries

Local synthetic browser tests passed in Chromium and WebKit. OBS read-only tests used authenticated local WebSocket fixtures. The actual iMac inventory showed one internal monitor, without a separately qualified audience or confidence display. Real live microphone/video and native OBS/ProPresenter/PowerPoint/Keynote acceptance remain future work, as do mobile device qualification and true BandMates performed-section event delivery. Plugin skill publication does not register new MCP tools on the existing RDC gateway or deploy source changes to the owner machine.
## Advanced owner-source contract, November 17 2026

The current isolated development branch contains the verified `presentation_load_worship_library`, `presentation_communication_capabilities`, `presentation_communication_prepare` MCP methods. Their corresponding local routes are `POST /v1/worship/library/load`, `GET /v1/communications/capabilities`, and `POST /v1/communications/prepare`, all requiring the existing operator bearer. Catalog source refs require matching content SHA/revision and independent local/stream rights. Communication endpoints return only metadata drafts; no bus delivery or third-party chat control occurs.

The independent stage teleprompter uses a distinct stage credential for readback and a second operator bearer for changes. GET `/v1/stage/teleprompt?key=STAGE_TOKEN` is stage-only. POST `/v1/stage/teleprompt` requires operator bearer and `X-Stage-Credential`, with explicit `PRESENTATION_ALLOW_TELEPROMPT=1` on an owner-approved restart. Source-bound current/next speaker/reader/singer content is never part of audience or stream packets. The `presentationctl.mjs teleprompt-` commands redact private bodies, notes and tokens.

Read `rdc-communications.md` for the existing Atlas Bus three-way communications path and its synthetic-only limitations. There is no active live chat enrollment, provider session wake, or automatic control of another AI chat through this published skill. Continue to distinguish installed instructions from an actually connected MCP server and independently qualified venue hardware.
