# AI Presentation Agent runtime

Source for TOC Ministries' standalone AI-neutral Presentation Agent, accompanying the top-level AI Presentation and AI Worship Production ChatGPT skills in this repository.

The runtime uses the existing PresentationDirector with manual, assisted or automatic cues and separate audience, private stage and broadcast views. The source includes content-locked worship catalog loading, verified BandMates performed-song cues, a private speaker/singer teleprompter, and read-only two/three-way RDC/Atlas communication drafting. ProPresenter is optional. Livestream recording, native presentation application control, BandMates MIDI/audio and real three-way browser chat require separately verified operator authorization and end-to-end readback.

## Local setup and testing

Install Node.js 24 or later, then run npm ci and npm test from this directory. A clean checkout deliberately omits owner-private credentials, local speech models, compiled Vision binaries and build/test logs. Optional native/device tests may skip when a local macOS model, connected BandMates source or browser acceptance environment is unavailable. Never run microphone, camera, projector, OBS Program or BandMates audio tests without the owner's separate permission.

Do not enable external writes automatically. The managed server is an owner-only loopback process with distinct operator, viewer, stage and stream tokens kept outside Git. PRESENTATION_ALLOW_EXTERNAL_CONTROL, PRESENTATION_ALLOW_WORSHIP_LOOK_EDIT, PRESENTATION_ALLOW_STAGE_CLOCK and PRESENTATION_ALLOW_TELEPROMPT are separate launch-time approvals. Stop/disarm commands do not physically blank a native projector.

Read skills/ai-presentation-agent/SKILL.md, skills/ai-presentation-agent/references/rdc-communications.md and docs/INTEGRATION.md for software contracts and live acceptance limits. The GitHub release publishes source for review, not a production installation, verified cross-project AI-chat enrollment or automatic access to another person's device.
