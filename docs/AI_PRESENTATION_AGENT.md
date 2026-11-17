# AI Presentation Agent skill for RDC

This is an optional skill integration for the existing RDC plugin. The standalone, local and offline Presentation Agent implementation resides in the TOC Ministries AI-Presentation-Agent workspace. Existing RDC worker, gateway, MCP, preview and permission models remain unchanged.

The skill supports AI-based deck creation and operator-approved automatic presentation following with speech, BandMates song-section events, visual stage observations and two-way voice chat. The default voice provider is the user's primary AI app. Optional local Whisper and macOS voice facilities require explicit device permissions and local configuration.

The standalone engine exposes its own MCP stdio tools and an authenticated loopback API. The skill alone does not add tools to RDC's existing server, establish a live microphone stream or guarantee universal presentation app support.

Existing adapter prototypes: local HTML, Keynote and PowerPoint macOS AppleScript, ProPresenter REST, OBS WebSocket. Cross-platform, other software, streaming provider integrations and end-to-end live hardware behavior require separate validation. External output writes require an operator-owned grant. Never run AI inference in the BandMates real-time audio or MIDI thread.

See skills/ai-presentation-agent/SKILL.md and skills/ai-presentation-agent/references/integration.md for details.


## Independent worship-production skills, November 17 2026

The existing AI Presentation Agent skill now includes its full worship skills
research library (skills/ai-presentation-agent/worship/): 26 training modules,
18 evaluation scenarios, ProPresenter/OBS reference research, privacy and
licensing procedures, and implementation/acceptance guidance.

The standalone runtime verified 393 of 393 local software tests at its last
owner checkpoint, with zero known dependency vulnerabilities. In particular,
the independent audience/stage/broadcast Looks and privacy boundaries, private
stage clock, owner-only service rundown, read-only OBS production metrics,
authorized local HTML output curtains and venue preflight passed software
tests. See the skill instructions for supported operator roles, safety gates,
and available local CLI commands.

This GitHub update packages documentation and research only. It does not deploy
or modify the separate Presentation Agent runtime, activate physical cameras,
projectors, private audio, installed OBS/ProPresenter, live streaming, or an
active BandMates session. Real native application, live broadcast and physical
venue acceptance remain outstanding. Speaker/Singer Teleprompt Following
Skills and optional authorized live comments remain independently queued.

The existing RDC GitHub branch, private ChatGPT plugin/App, and native
application services remain separately controlled and are not auto-activated.
