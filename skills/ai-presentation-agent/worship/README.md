# Worship Production Research and Skills Library
Prepared for the AI Presentation Agent builder | TOC Ministries | November 16, 2026

**Purpose:** teach the AI Presentation Agent ProPresenter-level worship and church production workflows, with particular attention to independent operation **without ProPresenter** and simultaneous livestream setup using OBS Studio.

**Location:** `~/RDC-Development/workspace/AI-Presentation-Agent/skills/ai-presentation-agent/worship/`

Start with `SKILL.md`, then `research/PROPRESENTER_OBS_RESEARCH.md`. Use the references folder for specific skill procedures and `data/modules.json` for 26 machine-readable learning objectives.

## Contents
- `SKILL.md`: trigger and reusable AI engineer operating instruction.
- `research/PROPRESENTER_OBS_RESEARCH.md`: researched ProPresenter feature-to-independent-equivalent matrix.
- `research/SOURCES.md`: official Renewed Vision and OBS documentation.
- `references/CHURCH_SERVICE_PLAYBOOK.md`: church service production and rehearsal.
- `references/LYRICS_AND_SCRIPTURE.md`: song arrangements, NKJV, lyric matching, rights awareness.
- `references/OUTPUTS_AND_STAGE.md`: auditorium, private stage, program preview and broadcast separation.
- `references/LIVESTREAM_OBS_GUIDE.md`: camera scenes, transparent overlays, audio mixing, Studio Mode, stream monitoring.
- `references/AI_CUES_AND_COORDINATION.md`: manual and AI following with BandMates and singer/pastor events.
- `references/LICENSING_AND_IMPORT.md`: SongSelect/CCLI, Bible text, Planning Center and asset import limits.
- `data/modules.json`: 26 training modules.
- `data/evaluation-scenarios.json`: 18 realistic worship, privacy, AI following and livestream evaluation cases.
- `examples/sunday-service.json`: original illustrative worship order and lyrics.
- `examples/obs-scene-map.json`: candidate OBS scene naming and stream permission flags.
- `examples/rehearsal-checklist.md`: church operator rehearsal with streaming.
- `DESIGN.md`: scope, success criteria and boundaries.
- `IMPLEMENTATION_PLAN.md` and `HANDOFF_NOTES.md`: future engineering blueprint and Atlas review notes.

This folder is a **research and skill set**, not an executable ProPresenter alternative. The existing running AI Presentation Agent application, its plugin, OBS, BandMates and RDC remain untouched by the final contribution. Earlier temporary test compiler scripts were discarded to keep the deliverable skills-only.

## Read-only validation
The project owner can validate JSON examples with `node -e` or any safe JSON editor. The documentation is discoverable through its nested SKILL.md. No run/serve/install commands are required or supplied by this research folder.

**Next conversation:** when the user requests it, create a concise prompt for the existing AI Presentation Agent build session pointing at this folder and preserving its current active tasks.
