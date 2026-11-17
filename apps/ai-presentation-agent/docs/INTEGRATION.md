# AI Presentation Agent integration guide
Date: November 16, 2026

Human AI voice, BandMates section events, and stage camera observations reach the observation filter, then the PresentationDirector, then an optional external output adapter. Manual, assisted and automatic modes share this route. The BandMates audio/MIDI performance callback remains independent of slide processing.

Main AI provider voice is the default. Submit speech transcripts to presentation_voice; when speakByHost is true, let the user's AI app read the returned reply aloud. The agent never pretends every AI platform can send continuous microphone frames to MCP tools.

Visual following consumes interpreted visual observations through presentation_watch. A local camera or host AI vision engine must produce these observations. Stage, speaker and room observations require two stable confirmed frames to change slides. Never feed presentation output back into visual following. Native camera acquisition and live computer vision have not yet been end-to-end verified.

The passive BandMates bridge in integrations/bandmates.mjs converts current song-dynamics snapshots into presentation cues without modifying the real-time audio path. The caller must supply the actual song title and a cue recipient. Do not call this bridge from a CoreAudio or MIDI callback.

The standard transport is MCP over JSON-RPC stdio using scripts/mcp.mjs. An independent authenticated loopback HTTP API is available using node scripts/serve.mjs, with a strong local PRESENTATION_API_TOKEN environment value. It binds only to 127.0.0.1:8789. HTTP requires Authorization: Bearer token. Supported endpoints include GET /v1/status and /v1/capabilities, and POST /v1/load, /v1/create, /v1/start, /v1/command, /v1/cue, /v1/watch, /v1/voice, /v1/output and /v1/arm.

External presentation app writes require explicit operator permission. The API bearer token alone does not enable them. The local environment must contain PRESENTATION_ALLOW_EXTERNAL_CONTROL=1 and the agent must arm the configured output.

ProPresenter routes confirmed in the published API include GET /v1/presentation/active/next/trigger, previous/trigger, and GET /v1/presentation/{uuid}/{index}/trigger, with zero-based slide indexes. The OBS protocol uses WebSocket 5 Hello, Identify and SetCurrentProgramScene. Each deck slide requires the corresponding existing OBS scene name. Native Keynote and PowerPoint AppleScript command syntax compiled against installed macOS application dictionaries. Full live control and readback were not tested while these apps may be in use.

Real-time tracking must be rehearsed with actual microphones, video sources, software and latency conditions. The engine currently receives external speech and camera observations. Native capture sources, cross-platform APIs and installed application interoperability remain follow-on work.

References:
ProPresenter OpenAPI: https://openapi.propresenter.com/
OBS WebSocket 5 protocol: https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md

## Local live browser viewer

Set optional PRESENTATION_VIEW_TOKEN in the local MCP or API launch environment. Once a deck is loaded, open http://127.0.0.1:8789/v1/viewer?key=YOUR_VIEW_TOKEN on the same computer to see a read-only browser presentation. The viewer receives live slide updates by server-sent events, using separate read-only authorization from the private API control token. No microphone, camera or GUI automation is required for browser output.

The viewer token appears in the local URL and may be stored in browser history. Treat it as a private display credential. In the default configuration without a viewer token, the browser output endpoint remains disabled. Run npm run test:browser for isolated headless-Chrome confirmation. This viewer is loopback only. Streaming to another physical machine requires a separate authenticated deployment that has not been implemented.


## Continuation reliability status, November 16, 2026

Director operations are serialized, the generic command endpoint cannot arm external output, and the standalone MCP output selection rejects an active or busy session. BandMates cue reattempts after a definite non-delivery result use a fresh event ID; ambiguous transport outcome keeps the original ID for safe recovery. OBS scene control now reads GetCurrentProgramScene after SetCurrentProgramScene acknowledgment and rejects a mismatch. These have fixture tests and cannot yet establish live output reliability.

The private ChatGPT RDC plugin has been verified at version 1.0.17 with the presentation skill installed. Independent presentation_* tools are not yet verified in the RDC gateway. See PRESENTATION-AGENT-CHECKPOINT-20261116.md for exact release identifiers, current source hashes, access blockers and remaining physical/platform acceptance.

## Windows PowerPoint adapter (source added 2026-11-16)

The optional powerpoint-windows adapter uses a Windows PowerShell COM bridge. The process attaches to an already running PowerPoint.Application object and requires an active SlideShowWindows(1) window. It can go forward/back, jump to a slide, and read back CurrentShowPosition. The script does not create PowerPoint or a presentation. It is available only on Windows; current validation consists of isolated generated-script and simulated COM transport tests. Actual Microsoft PowerPoint on Windows remains unqualified.

Important: Microsoft PowerPoint CurrentShowPosition is the position within the running slide show, which may be different from the original presentation's absolute slide position for custom slide shows. Bind/rehearse the deck and presentation on the target venue computer before enabling live automatic mode.

Microsoft official documentation:
- https://learn.microsoft.com/en-us/office/vba/api/powerpoint.slideshowview.currentshowposition
- https://learn.microsoft.com/en-us/office/vba/api/powerpoint.slideshowview.gotoslide
- https://learn.microsoft.com/en-us/office/vba/api/powerpoint.slideshowview.next
- https://learn.microsoft.com/en-us/dotnet/api/system.runtime.interopservices.marshal.getactiveobject

## External output receipt and readback verification

PresentationDirector now rejects explicit failed output receipts. For adapters that set requiresReadback=true, it requires independent confirmation of the intended slide before updating the internal slide pointer; a failed readback is reported without automatically retrying the native write. ProPresenter binds both the expected slide index and expected presentation UUID, preventing the same slide index from being accepted in a different presentation.

The optional task item 9 for authorized live broadcast comments is tracked separately in docs/WORK_QUEUE.md. It remains queued without changing the present integration priority.

## November 16, 2026 additional control verification

PresentationDirector serializes asynchronous commands and prevents a deck replacement while an output request is outstanding. A failed native show does not mark the presentation started. Normal user commands cannot arm the external-control gate. BandMates cue events carry occurrence metadata; repeated lyric/camera observations stay on the current chorus until a different section or a verified new occurrence is observed.

For verified output, the MCP command presentation_readback or authenticated GET /v1/readback compares the current application state with the expected slide. ProPresenter uses the official /v1/presentation/slide_index endpoint. An accepted trigger alone is not a confirmed projector change. Some third-party adapters can only report an unconfirmed output receipt, and live projector/mixer/venue testing remains mandatory.

Windows PowerPoint support now includes an existing-show COM adapter using Windows PowerShell, next/previous/goto and CurrentShowPosition. It does not create PowerPoint or open the owner's files. Its syntax and command/response tests pass, but a physical Windows host was not used for acceptance.

## Newly staged authoring and social adapters

PowerPoint-compatible offline export is available as presentation_export_pptx through MCP and POST /v1/export/pptx through the authenticated local API. It uses PptxGenJS 4.0.1 and an image-size 2.1.0 dependency override after security audit, generates slide content from supplied deck data and leaves native PowerPoint/Keynote import testing open. Full documentation: docs/RDC-CONTROL-BRIDGE-V1.md and docs/LIVE-COMMENTS-INTEGRATION.md in the project.

The optional source-bound RDC bridge and livestream comment AI adapters are separately staged for Atlas review and are not yet added to the published ChatGPT RDC skill 1.0.17. No authentication scopes, plugin audiences or active app integrations were changed in this stage.

## Persistent local session manager (verified)

Use node scripts/managed-server.mjs to run a private loopback presentation director that remains alive across independent AI and RDC command jobs. It creates separate random control and viewer tokens in a user-owned 0600 control.json, rejects duplicate session creation, and cleans up after SIGTERM. The control CLI at node scripts/presentationctl.mjs provides status, readback, load/create, start, next/previous/goto, hold/resume, cue, voice and watch. It retrieves its private credential locally so the caller does not place secrets in command arguments. An authenticated local HTML viewer can be prepared as an owner-only launcher file using viewer-export. See skills/ai-presentation-agent/references/managed-session.md.

Live ChatGPT RDC worker tool verification completed across multiple independent jobs: the same managed server loaded a demo deck, started automatic mode, processed a BandMates chorus cue, then advanced from a host voice command, and returned the expected slide and spoken reply. After cancellation, the private state file was absent. In a separate headless Chrome test, the local HTML viewer changed slides automatically and Apple Vision OCR recognized the new text. No physical app, stage microphone/camera, or owner desktop was activated.

## Additional control-identity verification

The presentation MCP/HTTP command handler now stores 16,384 bounded receipts per loaded deck for optional idempotencyKey values. Parallel and repeated identical next-slide commands return the same result, and conflicting key reuse is rejected. The local presentationctl accepts --request-id for repeat-safe next/previous/goto/hold/resume actions. VoiceInputRouter independently remembers eventId for a wake-phrase command so that duplicate transcripts do not advance slides or repeat spoken replies. Receipts reset when a new deck is intentionally loaded.

Imported presentation cue mappings are also verified. A deck slide may supply targetIndex as a zero-based cue number within ProPresenter that differs from the slide's position in the local setlist. The controller now triggers that exact target, checks the native cue index on readback, and reports both positions. All such behavior was tested against a simulated ProPresenter API; a physical venue still needs acceptance.

## Local Whisper speech and streaming verification (2026-11-16)

A small optional Whisper.cpp tiny.en model is installed only in this agent's .tooling/models/ggml-tiny.en.bin for offline testing; it is not bundled into the source archive. The original file was hash-verified against the model publisher. The default primary AI-host voice remains unchanged. Microphone capture still requires explicitly selecting an input device, setting a local bearer token, selecting the model, and obtaining operating-system microphone permission.

Run npm run test:voice to generate short local Apple text-to-speech audio files, decode them with installed local Whisper.cpp, and verify five recognized voice controls without accessing the microphone or speakers. Run npm run test:stream-voice to replay one generated command as overlapping 16-kHz PCM windows through the same segmentation, local transcription and two-pass command confirmation gate used by the optional microphone bridge. The streaming test confirms exactly one slide change, suppressing duplicate recognition across windows. Generated rehearsal audio is deleted automatically.

For an actual authorized microphone session, use the existing explicit scripts/local-microphone.mjs --device DEVICE_NUMBER --model /ABSOLUTE/MODEL/PATH --commands route with an operator-configured API token and a live presentation already running. In command mode a bounded 3.2-second audio window advances every 0.4 seconds and requires two agreeing command interpretations before issuing a slide action. The latching gate prevents consecutive overlapping windows from repeating that command. For speech following without voice commands, the original shorter window remains.

The test reports synthetic recognition performance only; physical mic permission, acoustic conditions, instrument/audio isolation, independent stage camera, actual output/projector latency, and livestream behavior have not been accepted.

## Connected running BandMates status and verified event receiver, 2026-11-16

The actual BandMates AI Studio companion service on this iMac was read using only the three existing localhost GET endpoints: /api/state, /api/band/status and /api/live/status. The installed service answered successfully and showed idle/stopped state with no native performed song-section event. The inspection did not start or stop the band, MIDI, audio, camera, screen, or mixer. Use the current CLI commands from RDC durable jobs:

    node scripts/presentationctl.mjs bandmates-status
    node scripts/presentationctl.mjs preflight

These commands print bounded, credential-free status and do not require activating the presentation output. The standalone preflight combines safe local presentation status, native app availability, and actual BandMates companion status. A connected app never automatically means live song following is ready.

The receiver is implemented in integrations/bandmates-verified-relay.mjs and its authenticated local cue sender in integrations/bandmates-cue-transport.mjs. They accept only a fresh, strongly confirmed current song/section occurrence from a particular native session, and reject planned-only or uncertain metadata. A lost response never triggers a blind duplicate native slide command.

The separate BandMates application development owner still must implement a trusted non-real-time producer of current performed section events. The full producer schema, identity trust requirements and live acceptance sequence are documented in docs/BANDMATES-VERIFIED-LIVE-EVENT-CONTRACT-20261116.md. This integration source does not claim to have live performed-song data from BandMates while the native API is idle and lacks that feed.

Current native software verification: 239 local suite tests passed and 18 dedicated BandMates/preflight tests independently passed through the connected RDC worker. Real display, actual vocal recognition and physical end-to-end cue latency remain unqualified.

## Live worship outputs and operator controls (2026-11-17)

The existing PresentationDirector now drives three independent local HTML outputs: public audience, private stage confidence, and public read-only broadcast graphics. Every output has a separately permissioned token and rights-filtered source data. No stage notes, chords or private Talkback content may enter congregation or stream data. Authorized lyric content requires separate room and livestream rights.

At the NEXT operator-approved managed server startup, PRESENTATION_ALLOW_WORSHIP_LOOK_EDIT=1 may grant local HTML Look, clear and blank editing. This is an explicit local operator choice, separate from external application writes, OBS scene switching, streaming and recording grants. Never restart an active presentation just to enable this flag.

MCP tools: presentation_worship_looks, presentation_worship_look_set, presentation_worship_visibility, presentation_worship_visibility_set, presentation_worship_rundown.

Operator-authenticated POST routes: /v1/worship/looks/audience, /v1/worship/looks/stage, /v1/worship/looks/broadcast, each with JSON property look; and /v1/worship/visibility/audience, /v1/worship/visibility/stage, /v1/worship/visibility/broadcast, each with JSON property mode (visible or clear; audience HTML also supports blank). Independent read-only Look endpoints use the corresponding audience/stage/stream tokens at /v1/look/{destination}. The public audience viewer gets only public-safe Look/visibility metadata over its read-only event stream.

Broadcast clear hides local Browser Source graphics only; it does not change the OBS Program scene or stream/record activity. Audience blank makes the local browser output visibly black; it does not operate native projector hardware. Stage clear hides restricted stage content independently. The original cue remains unchanged. On new service load or unload all state resets. An unverified native output cannot be blindly restored.

The operator rundown is available through the read-only command node scripts/presentationctl.mjs rundown, MCP tool presentation_worship_rundown or GET /v1/worship/rundown with an operator bearer. It includes current/next cue, service item titles and repeated section occurrence, but no full lyric bodies, private notes, chords or credentials.

The optional read-only OBS production report is available with node scripts/presentationctl.mjs obs-production-status. It separately reads Studio Mode, actual Preview, Program, stream/record status, CPU, FPS and drop statistics using OBS WebSocket 5. The original obs-status remains compatible. Neither report makes OBS changes or establishes actual hardware/provider acceptance.

Verification: 371/371 total automated tests, isolated Chromium/WebKit live Look and audience-blackout tests, authenticated WebSocket fixtures, RDC-style managed CLI tests and zero known dependency vulnerabilities. The current managed services were left running and did not load this new source until an operator-approved restart. The queued teleprompter work remains untouched.

## Private stage clock and sanitized real venue preflight, November 17 2026

The previous pure WorshipStageClock is now connected to the existing single-source worship presentation. It is a separate monotonic stage-only countdown. It never advances lyrics, changes slides, sends OBS actions, or touches audio/MIDI or a physical monitor. The stage's authenticated SSE output renders the timer label and countdown once per second while running; it clears on stage clear or unload. A verified stage Look can explicitly hide or show the timer layer. Neither audience nor broadcast Look permits this private layer.

The stage timer has a deliberately separate local operator grant, set only at the next operator-approved managed server launch:

    PRESENTATION_ALLOW_STAGE_CLOCK=1

This is independent of PRESENTATION_ALLOW_WORSHIP_LOOK_EDIT and PRESENTATION_ALLOW_EXTERNAL_CONTROL. The currently running managed processes are left untouched by source updates, and a new grant must never be assumed to be active on existing processes.

Owner-only POST /v1/stage/clock requires both the owner control bearer AND the distinct private stage credential in X-Stage-Credential. A private GET /v1/stage/clock?key=STAGE_CREDENTIAL requires only the private stage credential. The server does not expose the private stage timer as an ordinary public MCP tool, and public status, rundown, audience and OBS overlays do not include its label. Actions: configure {label,durationMs}, start, pause, resume and reset. A stopped presentation pauses the timer; a new/unloaded worship service clears its old label and duration.

For RDC jobs, the existing managed CLI reads credentials privately and never prints the timer label:

    node scripts/presentationctl.mjs stage-clock --file /ABSOLUTE/OWNER_ONLY/timer.json
    node scripts/presentationctl.mjs stage-clock-status
    node scripts/presentationctl.mjs stage-clock-start
    node scripts/presentationctl.mjs stage-clock-pause
    node scripts/presentationctl.mjs stage-clock-resume
    node scripts/presentationctl.mjs stage-clock-reset

Only an owner-owned 0600 regular JSON file with no symlink is accepted for the label and configuration. The CLI emits redacted timing state without the private caption, stream keys or stage credential. Do not activate a physical microphone, speaker, projector or stream as a side effect of timer changes. Software verification includes authorized/unauthorized HTTP and RDC CLI tests, monotonic progress, private SSE refresh, title suppression in public data, automatic service reset and browser visual checks on Chromium/WebKit with the page Content Security Policy enforced.

Read-only venue inventory is now included in presentationctl venue-readiness and in the combined presentationctl preflight. It uses the installed existing venue-output-readiness source, filters display serials and hardware IDs, reports connected displays and NDI/SDI driver candidates without qualifying physical output. The combined preflight now checks the OBS WebSocket 5 production status separately from the Presentation Agent, BandMates and display inventory. A locally connected OBS Program scene is not provider-delivery proof. On the inspected iMac the actual read-only inventory showed one internal display; no audience projector or stage confidence monitor was physically qualified, OBS WebSocket was unreachable, and BandMates was reachable but idle.

Current entire software regression: 391/391 pass; dependency audit: zero known vulnerabilities; private stage visual proof: evidence/worship-stage-clock-browser-20261117.json. Actual projector, external stage display, real OBS Program/provider stream and native BandMates performed-song data remain open.

## RDC/DC three-way communication integration, November 17 2026

The Presentation Agent now includes **read-only status** preparation for existing RDC/DC two- and three-way communications in an isolated development worktree. It reuses the Atlas Bus v1 and `rdc.chat_rooms.ChatRoom`, not a new bus. The current implementation exposes MCP tools `presentation_communication_capabilities` and `presentation_communication_prepare` plus operator-authenticated `GET /v1/communications/capabilities` and `POST /v1/communications/prepare`. These return privacy-limited drafts and never deliver a real chat message or control slides. A separately injected authenticated RDC host transport may execute the draft after its existing operator approval and bus ACL; the Presentation Agent itself does not push directly into a chat.

An actual existing **synthetic** RDC three-member room was exercised through separate terminal processes with Atlas Bus v1: two separate recipient claims/acknowledgments and one causally linked reply shared an exact room ID. The RDC communications source remains synthetic-only, and real ChatGPT/Claude/Grok/BandMates chat enrollment is **unverified**. Cross-project transport remains **blocked** pending an approved Atlas ACL and recipient identity. No actual chat session was interrupted, awakened or controlled. All voice, instrument, livestream, stage-private and production-output permissions remain separate. The newly added `skills/ai-presentation-agent/references/rdc-communications.md` is the Presentation side integration contract; the independently owned RDC communications skill is authoritative for its own tools. Never automatically advance a slide from a peer message.
