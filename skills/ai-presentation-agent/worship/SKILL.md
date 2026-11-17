---
name: worship-production
description: Use when researching, planning, reviewing, or training an AI presentation agent for Christian worship services, church services, ProPresenter-style service workflows, lyrics, Bible references, stage confidence monitors, congregation screens, OBS livestreams, lower thirds, and live cue coordination.
---

# Worship Production and Livestream Director Skills

TOC Ministries | Research and learning pack | November 16, 2026

## Scope and authority
Use this skill to research, design, teach, and document professional church presentation workflows. The goal is to give the existing AI Presentation Agent **ProPresenter-inspired worship production capabilities without requiring ProPresenter**. If ProPresenter is available later, treat its published API as an optional, separately authorized adapter. This package trains an engineer or builder. It does not deploy, modify, or operate the live presentation application.

The AI Presentation Agent project is located at `~/RDC-Development/workspace/AI-Presentation-Agent`. The existing owner is actively building the runtime. Do not alter `src/`, root `scripts/`, root `tests/`, MCP registration, running service, output configuration, credentials, BandMates, OBS, or ProPresenter from this research skill.

## Choose a discipline before giving advice
1. **Church service producer:** read `references/CHURCH_SERVICE_PLAYBOOK.md` for service order, announcements, worship arrangements, sermon, prayer, invitations, transitions, rehearsal, and recovery.
2. **Worship lyric operator:** read `references/LYRICS_AND_SCRIPTURE.md` to structure songs as verse, chorus, bridge, spontaneous repeats, Scripture references, and rights-aware text.
3. **Stage and screen director:** read `references/OUTPUTS_AND_STAGE.md` to distinguish congregation screens, private confidence monitors, operator console, and stream graphics.
4. **Livestream technical director:** read `references/LIVESTREAM_OBS_GUIDE.md` for OBS camera scenes, transparent lower thirds, stream audio, Preview/Program, monitoring, and fault recovery.
5. **BandMates and autonomous-following director:** read `references/AI_CUES_AND_COORDINATION.md` for human-led worship, singer and sermon cue validation, next/hold/resume, repeated sections, and cross-app timing.
6. **ProPresenter feature research:** read `research/PROPRESENTER_OBS_RESEARCH.md` and `research/SOURCES.md` for verified vendor capabilities and realistic independent alternatives.
7. **Service assets and permissions:** read `references/LICENSING_AND_IMPORT.md` for NKJV, CCLI/SongSelect, protected lyrics, video licensing, and safe service content handling.

## Core target capabilities for the builder
- A reusable service library of songs, Scripture references, sermon points, prayers, countdowns, announcements, media, and service plans.
- Per-song Verse 1, Verse 2, Chorus, Bridge, Tag, Instrumental, Ending, and spontaneous-repeat groups, with occurrence identifiers and saved set arrangements.
- Readable congregation lyrics and Scripture, independently controlled stage confidence content, and distinct stream-safe lower-third or title graphics.
- Current slide, next slide, optional user-authorized chords, private leader/pastor notes, stage messages, timers, and confidence monitor status.
- Multi-output Looks or layers so a single service cue can display different layouts on each destination without exposing private stage data.
- OBS livestream integration: program and preview scene awareness, camera-safe lyrics, keyable overlays, source visibility, transition timing, stream audio and recording status, and safe stream controls requiring separate operator permission.
- Automatic or assisted following via confirmed voice, lyrics, Scripture, BandMates song and section state, and trusted stage camera observations.
- Human override at all times with next, previous, hold, resume, clear, blank, scene fallback, and safe recovery.
- Optional third-party systems through actual supported adapters: ProPresenter, Planning Center, CCLI SongSelect, Keynote, PowerPoint, mobile displays, authorized video and livestream platforms.

## Existing project implementation boundary
The current agent already has a PresentationDirector, offline HTML decks, an authenticated local viewer, persistent control service, BandMates cue bridge, and prototype OBS and ProPresenter adapters. These are useful reuse targets for the other development session. This skill contributes **methods, training modules, a feature matrix, example service data, safety and acceptance requirements only**. It does not change the runtime, and the examples are illustrative service plans rather than playable/active shows.

## Decision method for every operator task
Record requested outcome, service segment, allowed output targets, content rights, confirmed source observations, candidate cue, intended timing, confidence, existing application capability, operator approval and verification path. Separate three results: **prepared**, **command accepted**, and **audience or livestream output verified**. Never equate the first two with the third.

When speech or music is ambiguous, retain the last confirmed cue. The singer may repeat a chorus spontaneously. Prefer verified audio/lyric section occurrence and manual operator direction to planned sequence alone. Avoid sending cloud inference, AI vision, speech recognition, or HTTP calls through a real-time BandMates audio/MIDI callback.

## Security and church production boundaries
- Use NKJV references and only owner-supplied, authorized verse bodies. A Scripture reference is sufficient when no rights-cleared text is available.
- Obtain user-supplied or licensed lyrics. Respect the church's licensing/reporting requirements and copyright display policies.
- Keep chords, private pastoral notes, stage-only timers, chat credentials, camera credentials, Talkback, and operator keys out of congregation and livestream outputs.
- Changing an OBS scene, starting a stream, recording, or enabling external ProPresenter control requires separately verified capabilities and operator grants.
- A stream viewer needs separate live output verification. A locally rendered slide or successful network response alone is insufficient.
- Never automatically start microphones, cameras, projection, livestreams, recordings, or software playback from a teaching/research task.

## Training and handoff inventory
`data/modules.json` contains 26 distinct training topics. `data/evaluation-scenarios.json` contains 18 evaluation cases covering worship, private stage information, Scripture, OBS video production and failure handling. `examples/sunday-service.json`, `examples/obs-scene-map.json` and `examples/rehearsal-checklist.md` are design references and fictitious original content. `IMPLEMENTATION_PLAN.md` describes future implementation **for the existing builder**, and `HANDOFF_NOTES.md` records acceptance criteria and unresolved hardware questions.

The research sources are public links, with official Renewed Vision and OBS documentation prioritized. Do not copy proprietary ProPresenter assets, assume a license, or advertise universal feature parity.
