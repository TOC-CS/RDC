---
name: ai-worship-production
description: Use when preparing, presenting, following, or operating church worship services, sermons, licensed song lyrics, Scripture slides, stage confidence screens, independent audience output, or OBS livestream graphics with the existing AI Presentation Agent.
---

# Worship Production for the AI Presentation Agent

This skill extends the established AI Presentation Agent and RDC workflow. Use the existing Presentation Agent installation on the authorized user's machine, with one authoritative presentation cue state. ProPresenter is OPTIONAL. Do not create a duplicate runtime or a new parallel service, change another project's work ownership, or restart existing RDC, BandMates, OBS, or presentation services without an explicit operator-approved restart.

## Available local software functions

- Compile a structured worship service containing announcements, song arrangements, verses, choruses, bridges, Scripture references, prayers, sermon cues, and closing segments. Preserve occurrence numbers for repeated sections. Use only original or authorized lyric content and separately respect room and broadcast rights. NKJV reference-only slides are appropriate if verse-display permissions have not been established.
- Select independent audience, private stage, and broadcast Looks, with isolated layers. A single confirmed presentation cue drives all three outputs. Stage-only chords, sermon notes, speaker instructions, teleprompt drafts, and talkback must never be serialized to public audience or livestream output.
- Use an independent read-only local viewer for congregation output, a separate authenticated stage confidence viewer, and a transparent browser graphic source for OBS. Browser audience blank, broadcast graphics clear, and private stage clear are independent LOCAL PRESENTATION operations. They do not operate a physical projector, change OBS Program or Preview, or start/stop streaming or recording.
- Inspect the source-bound current and next service cue through the operator-only rundown. It includes safe metadata and repeated section occurrence, never full licensed lyric bodies or private stage notes.
- Use the private stage countdown with a distinct timer permission and independent stage credential. Start, pause, resume, reset and stage-clear operations cannot advance slides or expose the timer label to public viewers.
- Preview service transition macros in a non-executing mode before live operation. Do not execute stream/record controls, physical blanking, camera changes, or OBS scene writes from a preview.
- Read OBS Studio Mode, Preview, Program, stream/record state and frame/drop statistics through verified read-only obs-websocket 5 APIs when OBS is actually connected. Independent native scene control requires its own grant and readback.
- Reuse host AI speech transcripts, optional approved local Whisper audio, visual observations, and verified current BandMates performed section events. Planned song form alone never proves the vocalist's performed lyric. Preserve manual hold/override and reject ambiguous or duplicate cues.

## RDC operator commands

Use the existing connected RDC worker to run the locally installed script, after verifying that path and managed-session health. Never put the private control token, separate stage token, password or stream key in chat or command arguments.

- `node scripts/presentationctl.mjs preflight`: read-only combined agent, BandMates, OBS and venue readiness
- `node scripts/presentationctl.mjs venue-readiness`: read-only physical display inventory; does not certify a projector
- `node scripts/presentationctl.mjs rundown`: private operator service order and current/next cues, without stage notes or full lyrics
- `node scripts/presentationctl.mjs obs-production-status`: read-only OBS Studio Mode, Preview/Program and production diagnostics
- `node scripts/presentationctl.mjs look-set --file /ABSOLUTE/FILE.json`: change ONE configured presentation Look only after local operator grant
- `node scripts/presentationctl.mjs visibility-set --file /ABSOLUTE/FILE.json`: local audience HTML blank, stage clear, or broadcast graphic clear, with operator grant
- `node scripts/presentationctl.mjs stage-clock --file /ABSOLUTE/OWNER_ONLY.json`: configure private countdown from a 0600 owner-only regular file, never a symlink
- `node scripts/presentationctl.mjs stage-clock-start`, `stage-clock-pause`, `stage-clock-resume`, `stage-clock-reset`, or `stage-clock-status`: redacted private countdown operations

Before using any command, check that it exists in the actual connected local installation. Source files updated after a persistent server started are not automatically loaded. Do not restart the running service or grant new privileges merely to demonstrate a skill.

## Authorization boundaries

The existing managed-server operator must explicitly enable `PRESENTATION_ALLOW_WORSHIP_LOOK_EDIT=1` on an approved startup before Look/visibility editing. A separate `PRESENTATION_ALLOW_STAGE_CLOCK=1` permits timer mutation, and stage write requires BOTH the operator bearer and independent stage credential; ordinary RDC timer replies redact private labels. External native-app output uses a different operator authorization. OBS Program, start/stop streaming, recording, critical scene transitions, live comment replies and third-party publishing each require their own supported integration and user authorization. Do not infer these from the presentation-control token or a connected browser login.

The stage-only speaker/singer teleprompt following capability is queued for future development, including pace-aware scrolling, live lyric/sermon recognition, spontaneous repeats and operator fallback. The separate live-comment API integrations also remain subject to provider OAuth and posting acceptance. Do not describe queued features as operational.

## Verification and honest release scope

The standalone Presentation Agent source had 393 of 393 local automated tests passing at the November 17, 2026 owner checkpoint. Browser visuals, stage privacy, local timer, read-only OBS protocol fixtures, and source-bounded control operations were software-verified. These are not proof that a real auditorium projector, external stage monitor, native ProPresenter/OBS/PowerPoint/Keynote application, physical microphone/camera, hardware stream capture, provider livestream delivery, or BandMates performed-event producer was tested. At that checkpoint, read-only host inventory found only the iMac internal screen, OBS WebSocket was unavailable, and BandMates was reachable but idle. Keep live hardware and service testing open for a later user-authorized session.

Further local research and acceptance source: `~/RDC-Development/workspace/AI-Presentation-Agent/skills/ai-presentation-agent/worship/`. It contains 26 training modules, 18 evaluation scenarios, official-source research, licensing notes, service procedures and OBS guidelines. This skill provides the current operational contract; the external source library is available only when that authorized filesystem is connected.
