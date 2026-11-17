---
name: ai-presentation-agent
description: Use when an AI should build, run, follow or control slides, songs, lyrics, Scripture, business presentations, worship services or broadcasts through RDC, BandMates AI Studio, ProPresenter, Keynote, PowerPoint, OBS or other compatible presentation tools. Handles hands-free speech, visual observations, voice chat and performer cues. Uses local AI-neutral MCP or API transport.
---

# AI Presentation Agent

Operate presentations for church worship, sermons, live music, streaming, meetings, business talks and personal workflows. The independent local engine lives in RDC-Development/workspace/AI-Presentation-Agent. RDC can operate a computer for an adapter. BandMates can produce music cues. The engine does not require either app to run.

## Connect and create

1. Detect the current AI host's configured AI Presentation Agent MCP server, or its authenticated loopback API on 127.0.0.1.
2. Inspect presentation_capabilities for actual supported adapters. Presence of an adapter does not prove that native hardware or live control has been validated.
3. Select desired output. Offline HTML can run without third-party apps. External apps need permission and an explicit operator control grant.
4. Create a deck from requested material using presentation_create, or load existing structured cues using presentation_load.
5. Start in assisted mode for a rehearsal. Select automatic mode for hands-free cue following.
6. Observe status and receipts after each action. Report separately the engine state and the actual presentation app's readback.

## Listen and watch

- Send current BandMates song/section/occurrence metadata to presentation_cue. The song title must be supplied from a setlist. BandMates planned song sections alone do not prove that a live vocalist is singing those lyrics.
- Send confirmed live speech to presentation_cue as a final transcript observation. It matches lyrics and references while excluding low-confidence, stale, duplicated, or partial inputs.
- Send trusted interpreted camera observations to presentation_watch with unique frame ID, cameraRole, confidence and timestamp. The stage, speaker and room camera roles can influence slides after repeated confirmation. The presentation-output role is excluded to prevent an output-video feedback loop.
- The active AI host may supply permitted voice and vision streams. Optional macOS local microphone and camera observer scripts have been implemented, but need explicitly selected devices, OS authorization and live calibration. Apple Vision OCR is supported locally. Real-time gesture recognition and device-specific camera control need separate validation. Skill instructions alone cannot activate a physical camera or microphone.
- When confidence is insufficient, retain the current slide. Manual hold, next, previous, goto and resume remain available.

## RDC ChatGPT/Claude bridge

If the user's AI client exposes RDC but does not expose the standalone Presentation Agent tools directly, use RDC's existing worker to check the local installed agent through an authorized durable read-only command. A real ChatGPT RDC job_run smoke has verified MCP discovery and simulated voice/visual cue routing. Do not treat this as proof of a running venue presentation.

For sustained live control, use one persistent presentation session through the separately connected MCP server or an operator-configured authenticated loopback API. Repeated short-lived RDC jobs each create a new isolated presentation state and cannot follow a continuous session. Keep the local API and any read-only viewer credentials out of tool arguments and public transcripts. Never modify RDC gateway bindings or active BandMates native audio/MIDI sessions just to activate the skill.

## Persistent RDC/BandMates session manager

For sustained, separate RDC jobs controlling the same live deck, use the independent managed session server rather than starting a fresh director in every short-lived command. Run the managed server as a durable owner-authorized RDC job. Its locally generated credentials stay in a private 0600 file, and node scripts/presentationctl.mjs reads them without putting credentials into AI tool arguments or responses.

The managed session provides a read-only browser viewer using an independently generated private viewer token. The operator may create an owner-only local HTML launcher using viewer-export; do not print the actual viewer URL in a public answer or activate an owner browser automatically. Follow references/managed-session.md for setup, recovery, safe shutdown, and exact limitations.

## Crash recovery and independent live viewer

The managed server now saves a bounded owner-only last-known.json checkpoint containing the deck and previous slide index, without API tokens, viewer keys or external control grants. If the process crashes, it verifies the previous private control PID is dead before clearing stale control.json. It restores the last slide as a **held RECOVERED PREVIEW**, disarms external outputs, and never auto-projects to a native app. The next operator-owned start begins a deliberate new show. Never infer actual projector position from a recovered checkpoint. A still-running instance cannot be replaced.

The live viewer is an output, not a remote control. When connected, its keyboard navigation, click controls and presentation.goto messages cannot change the slide independently from the controller. Use node scripts/presentationctl.mjs next --request-id STABLE_ID or the corresponding authorized MCP tool for source-of-truth advancement. The offline exported HTML player retains keyboard navigation when it has no live event connection.

Follow references/managed-session.md for the exact private recovery and CLI route. ChatGPT RDC job_run can execute node scripts/presentationctl.mjs through its authorized worker; a newly launched standalone MCP process would have separate state. Always use the linked owner account, the existing authorized device and the project installation actually detected. Do not guess a machine path or expose credentials.

## Voice chat, default host AI

Voice chat uses the user's main AI app or platform by default. Pass confirmed transcripts into presentation_voice, then read reply and speakByHost to allow the host to speak when supported. Wake phrase is "presentation agent", with push-to-talk as an alternative. Sample commands: "Presentation agent next slide", "Presentation agent show slide 3", "Presentation agent hold slides", "Presentation agent what slide are we on".

Optional local voice uses a locally installed Whisper.cpp model and macOS speech after explicit device permission. A free tiny.en model may exist at .tooling/models/ggml-tiny.en.bin in a configured installation; detect it rather than assuming every user has one. The main AI host remains the default voice provider.

For **local spoken talkback**, never use the default speaker output. Before microphone capture, run node scripts/local-microphone.mjs --list-outputs to discover current CoreAudio speech output IDs without playing audio. The operator selects a private headphone/monitor route and confirms it is isolated from the house mix and livestream. Only then allow --commands --speak --output-device DEVICE_ID --confirm-private-monitor with the explicitly selected microphone and local model. Device IDs may change after reconnection. These flags guard routing selection; physical output isolation still requires an actual owner-supervised soundcheck. Without this confirmation, return reply text and leave local audio playback off.

## Software control

- Local HTML deck: working offline browser player and exporter. Optional local authenticated viewer receives real-time slide changes over Server-Sent Events. It uses a separate read-only viewer token.
- Keynote on macOS: AppleScript next, previous and jump; installed scripting dictionary and command compilation verified, live native control pending.
- PowerPoint on macOS: AppleScript slide show commands; installed dictionary and compilation verified, live app control pending.
- ProPresenter: local official REST API paths implemented, no physical ProPresenter available on the checked iMac.
- OBS: obs-websocket 5 scene control implemented, live software output pending qualification.
- Other RDC-supported apps: require application-specific controls, a documented API or a verified RDC visual UI adapter.
- Windows PowerPoint: a conservative Windows PowerShell/COM adapter attaches to an existing running slideshow and performs next, previous, goto and position readback. Its command and simulated parser tests passed; a physical Windows/PowerPoint run is still pending.
- Native iOS/Android and Adobe app adapters need future per-app qualification. Other installed presentation software may integrate with a documented API or an RDC source-bound adapter; do not claim universal coverage.

## Real-time viewer and availability

With a local API token and optional PRESENTATION_VIEW_TOKEN, the operator can open the read-only live viewer at http://127.0.0.1:8789/v1/viewer?key=VIEW_TOKEN. The URL contains a read-only credential and is local to the machine running the agent; never print a real token in AI replies, issue tracker logs or public documentation. The viewer receives authorized presentation updates without a human pressing next. For OBS Browser Sources on another machine, a distinct authenticated network viewer bridge is still required.

The available standalone engine is installed separately from this skill. ChatGPT, Claude, Grok, Muse and other hosts can call its MCP tools only when the host is actually connected to the local agent or a supported trusted gateway. Adding the skill to RDC does not add presentation tools to the existing RDC gateway automatically.

## Authorized livestream comments

The saved desktop master plan also requires reading and responding to live audience comments when the user grants suitable platform access. The presentation agent has an optional, separately permissioned LiveCommentsController and YouTube/Facebook adapters. Check presentation_capabilities.liveComments.connected before claiming a connected broadcast account.

Use live_comments_read to observe authorized livestream messages, and live_comments_draft to prepare a response in the user's active AI host. Public posting requires a separate local operator grant, per-stream/per-comment authorization and moderation before live_comments_arm and live_comments_reply can succeed. Automatic mode must use a bounded, rate-limited host loop and a verified account connection. Never infer posting rights from presentation-control access or from a login in another browser.

The current YouTube adapter supports official live chat list/insert APIs when the host supplies OAuth. It posts a new chat message rather than a threaded platform reply. The Facebook Live Graph API adapter supports read-only comments from the documented live-video edge. Other services require separately verified provider-specific adapters. The user's main AI host remains responsible for natural-language replies unless the user enables a tested local model.

See references/live-comments.md for permission, platform and acceptance limits. If no connected comments source is available, explain the missing integration rather than inventing authenticated access.

## Cues, retry safety and native positions

When an AI command may be retried after an uncertain response, preserve its unique idempotencyKey on presentation_command, or pass the same --request-id value to the local presentationctl next/previous/goto/hold/resume commands. The server returns the original receipt instead of advancing again. Reusing a key for a different action is rejected. Voice commands use their original eventId; a duplicate host transcript does not trigger another slide change or spoken response.

A presentation deck slide may declare targetIndex to identify the actual zero-based cue within ProPresenter independently of its local setlist position. Mapped cues use exact triggering instead of blind next/previous operations. Readback reports the expected native cue and the separate deck position. Rehearse the mapping with the real application before public use.

## Stop without losing control

Use node scripts/presentationctl.mjs stop, the presentation_stop MCP tool, or POST /v1/stop to stop the local presentation controller. This disarms external output control and prevents further automatic cues. The native projector screen may remain on its last frame; stop does not blank or close another program. Use the venue's independently verified blanking method or local operator controls when the audience display must go black. After a stop, a deliberate new start begins at the first slide.

After stop, use node scripts/presentationctl.mjs unload to clear a finished local deck, remove its private last-known.json crash checkpoint and return the persistent service to empty idle state. Unload is refused while a presentation is still running or armed. An already connected live viewer shows **PRESENTATION CLEARED** and removes prior private slide content from its DOM. Once the checkpoint is removed, the old deck cannot reappear on a service crash/restart. If local checkpoint storage cannot be cleared, the server returns an error and an owner can safely retry unload after repairing storage.

## Rehearsal and live use

1. Prepare ordered song, verse, chorus, scripture, speaking and scene cues.
2. Verify lyrics, fonts, media licensing, and slide style with the user's desired application.
3. Test in assisted mode with local HTML output.
4. Calibrate live speech, song and camera inputs and verify route timing.
5. If directing a third-party app, the local operator enables external control and arms the selected output.
6. Switch to automatic following and retain explicit hold/manual override.
7. If the session loses audio, camera or control connectivity, hold the last confirmed slide. Do not invent cues or retry uncertain writes.

## Security and quality

- Do not put presentation decisions, model inference or HTTP calls inside the BandMates real-time audio or MIDI callback.
- Keep device inputs/permissions, tokens, credentials, microphone frames, and private screen content out of ordinary logs.
- No cloud subscription is required for the core control engine.
- No owner desktop focus/pointer takeover without verified isolation or explicit foreground approval.
- Operator grant for external writes is separate from an API bearer token.
- A valid AI command is not evidence the actual display showed it. Use available readback or independent stage/output verification.
- Maintain cue identity and idempotent handling across reconnects.
- A repeat of the same chorus or Scripture reference must not advance across duplicated slides. Match verified BandMates song-section occurrence changes or an intervening distinct section before permitting the next repeated cue.
- Use presentation_readback or GET /v1/readback for independent output observation when the chosen adapter supports it. An accepted command alone does not verify a projector or stream.
- Do not describe test simulations as live native hardware verification.

## Developer quick reference

Source: RDC-Development/workspace/AI-Presentation-Agent
Run npm test to verify.
Run node scripts/mcp.mjs for MCP stdio.
Run node scripts/serve.mjs with PRESENTATION_API_TOKEN configured for local API access.
An additional explicit launch environment flag PRESENTATION_ALLOW_EXTERNAL_CONTROL=1 is required before enabling external app writes.
See references/integration.md for API shape, operating limits and development status.

## Independent worship production, without requiring ProPresenter

The original worship and livestream skills library is installed at skills/ai-presentation-agent/worship/. It contains 26 research/training modules, 18 evaluation scenarios, stage and audience procedures, official OBS/ProPresenter references and original service examples. Use its SKILL.md and IMPLEMENTATION_PLAN.md alongside the current source before planning a service. The existing PresentationDirector remains the single cue authority. Teleprompt following is queued for a later verified phase; do not assume it is implemented.

Use presentation_load_worship for an owner-supplied service plan. The compiler filters original or licensed lyric and NKJV reference content independently for local audience and public livestream. The private stage monitor gets notes/chords only through its distinct stage authorization; public service status, PPTX/HTML exports and broadcast overlays receive allowlisted content only. Never silently supply protected song lyrics or a full NKJV Bible body without documented display and streaming permissions.

Use presentation_worship_rundown or the local read-only node scripts/presentationctl.mjs rundown to inspect service item order, current and next cue, repeated chorus occurrence, output looks and visibility without exposing private stage instructions or song text.

Independent audience, stage and broadcast Looks can be read through presentation_worship_looks. Changing one with presentation_worship_look_set or node scripts/presentationctl.mjs look-set --file OWNER_SELECTED_JSON requires an explicit local operator grant at managed-server startup via PRESENTATION_ALLOW_WORSHIP_LOOK_EDIT=1. Output visibility uses presentation_worship_visibility_set or node scripts/presentationctl.mjs visibility-set --file OWNER_SELECTED_JSON, guarded by the same separate operator grant. Audience HTML blank displays a local black page; broadcast clear removes only graphics from the OBS-compatible Browser Source; stage clear hides private stage text. None of these operations changes a real OBS scene, native projector or broadcast stream/record status. Do not mistake local browser blackout for verified projector blackout.

## Private stage clock and rehearsals

The existing private confidence display supports an independently timed stage-only countdown. It is separate from song-section following and cannot advance a slide. The stage clock needs PRESENTATION_ALLOW_STAGE_CLOCK=1 at a new operator-approved managed-server startup. The private HTTP stage-clock POST requires both owner API authorization and a separately verified X-Stage-Credential. Its GET requires the distinct private stage token.

For RDC, create an owner-only 0600 JSON configuration file with {"action":"configure","label":"PRIVATE CAPTION","durationMs":90000}; do not share that file or title in public logs. Use node scripts/presentationctl.mjs stage-clock --file ABSOLUTE_OWNER_ONLY_JSON, then stage-clock-start, stage-clock-pause, stage-clock-resume, stage-clock-reset or stage-clock-status. Command replies redact the private timer label. The stage confidence viewer updates about once per second, respects private stage Look visibility, pauses on presentation stop and clears on service unload. Running and installed services do not inherit new launch permissions unless the owner explicitly authorizes a controlled restart.

## Production and venue verification

Use node scripts/presentationctl.mjs venue-readiness to inspect connected macOS displays without changing routing or publishing serial numbers. Use node scripts/presentationctl.mjs preflight to independently inspect the live Presentation Agent, BandMates companion, venue display candidates and OBS read-only production status. Use obs-production-status to inspect OBS Studio Mode, Preview versus Program and stream/record health when the documented local WebSocket service is actually connected. These diagnostics never issue broadcast scene or stream/record writes.

The software output Look, timer and local viewer tests passed, including isolated Chromium and WebKit rendering with Content Security Policy enforced. Physical projector, stage monitor, local OBS Program, stream provider delivery, audio/visual sync, active microphone/camera and performed BandMates event feed each require separate operator-approved real acceptance. At this checkpoint the iMac inventory listed only one internal display and OBS WebSocket was unavailable. Preserve the existing RDC and BandMates project ownership and do not mark the entire Presentation Agent production-ready on the basis of a simulated rehearsal.

Current developer evidence, implementation permissions and Atlas review notes are in docs/INTEGRATION.md and docs/ATLAS-WORSHIP-LIVE-OUTPUT-REVIEW-20261117.md.
