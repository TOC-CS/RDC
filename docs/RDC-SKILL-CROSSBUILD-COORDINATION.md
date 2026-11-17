# RDC musician and presentation skills coordination
Status: QUEUED. Integration, validation and release are NOT complete.

## Ownership and update locations
RDC core: /Users/brandondawson/RDC-Development/workspace/rdc-v8-host-validation-20261115
RDC primary skill: skills/rdc/SKILL.md and skills/rdc/references/
Musician tool: /Users/brandondawson/RDC-Development/workspace/rdc-musician-tool
Musician tool entry: TOOL.md and scripts/musician.mjs, with playing-knowledge/ resources.
Presentation skill: /Users/brandondawson/RDC-Development/workspace/AI-Presentation-Agent/skills/ai-presentation-agent/SKILL.md
Presentation integration contract: /Users/brandondawson/RDC-Development/workspace/AI-Presentation-Agent/docs/INTEGRATION.md
BandMates in-development presentation skill copy: /Users/brandondawson/RDC-Development/workspace/BandMates/skills/ai-presentation-agent/SKILL.md
BandMates build handoffs: /Users/brandondawson/RDC-Development/workspace/BandMates/project-handoff/

## Required cross-build contract
1. RDC remains an independent, AI-neutral local/offline MCP/API tool. Musician and presentation skills are optional consumers, never mandatory RDC dependencies.
2. Do not duplicate or overwrite either skill's current implementation. Each build owns and updates its original skill code, interfaces and test suite.
3. Coordinate stable capability discovery, versioned API/MCP schemas, distinct session IDs, operation recovery, source-bound previews, adapter availability and diagnostic receipts. Do not advertise unverified capabilities.
4. Musician integration must preserve real-time musical timing, MIDI/audio routing, and GUI-owned MIDI connections. RDC relay jobs are development/management controls, not an assumed deterministic real-time audio scheduler.
5. Presentation integration should use existing independent local MCP/API engine, supported output adapters and optional BandMates cues. Use RDC automation only through authorized supported operations.
6. BandMates AI Studio MUST NOT be published until final complete app functionality and acceptance verification. Do not restart, modify or interrupt active BandMates, MIDIServer, audio, MIDI devices, or sessions from RDC coordination.
7. Each team/build should append a brief versioned change receipt in its own handoff, listing exact files, tests, interface changes and still-unqualified behavior. Only publish an RDC plugin skill update after reviewed cross-project compatibility.
8. Preserve existing ChatGPT App/plugin 1.0.15 identity and audience, existing GitHub PR and the independent worker. Free AI APIs may assist research but credentials must never be exposed or become dependencies.

## Remaining acceptance
Compare musician/presentation/RDC schemas and adapters; implement only necessary compatible bridges in the owning projects; test their local/offline operation; test integration against actual supported hosts. Keep this task OPEN until verified and BandMates publication remains separately blocked.
