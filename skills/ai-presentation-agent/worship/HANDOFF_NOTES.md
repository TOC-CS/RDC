# Research-to-Build Handoff Notes (technical, not the user-facing handoff prompt)
TOC Ministries | November 16, 2026

## What to take from this folder
A reusable worship-production SKILL.md, 26 learning modules, official ProPresenter/OBS feature research, six detailed training/reference documents, realistic service and OBS scene examples, and the service rehearsal checklist. It prioritizes audience lyrics, stage private confidence, streamer camera-safe overlays, and cue reliability without a ProPresenter installation.

## Working project state discovered
- Existing project: `RDC-Development/workspace/AI-Presentation-Agent`, actively maintained in another session.
- Existing functionality: structured deck and director, offline HTML presentation, managed local control/viewer, BandMates cue conversion, voice/vision prototypes and ProPresenter/OBS adapters with prior simulated or software-only tests.
- Installed on iMac inventory: OBS and Keynote found; ProPresenter absent.
- External acceptance open: real live auditorium outputs, multiple authenticated viewers, physical stage monitors, OBS live scene/stream, vocal/music following and third-party application readback. A fresh owner status check is required before modifying anything.
- Work queue includes separate livestream comments authorization and publisher qualification. Do not override that work queue from this research session.

## What's specifically new in the skill set
The skill describes a single cue owner driving three purpose-specific video paths:
1. Full-screen projector lyrics/Scripture and public announcements for congregation.
2. Private stage confidence with next lyrics, chords, sermon notes and timers, with distinct identity and permission model.
3. Public stream overlays as transparent lower thirds over OBS cameras, with independent Program/Preview and audio/video sync checks.

Additional requirements: lyric arrangements and spontaneous repeat occurrence identity, NKJV reference-only fallback, SongSelect/CCLI and media licensing records, church volunteer service operation, human override, confident cue recognition, countdowns, macros, stream health, resilient Stop/restart and optional ProPresenter REST integration.

## Implementation guidance, no ownership transfer
The builder should first read the current master plan and ask Atlas to review how these skills fit the current queue. Use `IMPLEMENTATION_PLAN.md` as a technical blueprint, not as a command to abandon the active work. Do not deploy, install, overwrite active files, or modify CoreAudio, BandMates or the broadcasting setup simply to adopt these documents.

## Validation requirements for the builder
- Native deck/rehearsal tests and repeated chorus scenarios.
- Public/private payload and output privacy tests, including every error and cache path.
- Real hardware projector + stage output verification, not merely internal state.
- OBS Browser Source transparency, Preview/Program and provider stream preview, including audio synchronization.
- Automatic follow with verified performer observations and manual override.
- Clock/timer handling, clear/stop and crash recovery with outputs disarmed.
- Permission checks for external camera, service plan API, stream/record and ProPresenter only if installed.
- Licensing review for song lyrics, NKJV body text and media.

## Research acceptance statement
This contribution supplies reference procedures and design requirements only. It makes no claim of production-ready worship displays, working ProPresenter, OBS livestream, synchronized physical screens or new presentation-specific MCP tools.

The user requested that the final handoff **prompt** be written later. Keep these notes available until that instruction arrives.
