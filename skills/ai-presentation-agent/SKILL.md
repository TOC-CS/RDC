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

## Voice chat, default host AI

Voice chat uses the user's main AI app or platform by default. Pass confirmed transcripts into presentation_voice, then read reply and speakByHost to allow the host to speak when supported. Wake phrase is "presentation agent", with push-to-talk as an alternative. Sample commands: "Presentation agent next slide", "Presentation agent show slide 3", "Presentation agent hold slides", "Presentation agent what slide are we on".

Optional local voice uses a user-provided Whisper.cpp model for speech recognition and macOS system speech for replies. Capture must be configured separately with permission. Route talkback to monitors or headphones only after testing; avoid audible talkback on house mix or public stream.

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
