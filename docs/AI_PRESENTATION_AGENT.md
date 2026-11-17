# AI Presentation Agent skill for RDC

This is an optional skill integration for the existing RDC plugin. The standalone, local and offline Presentation Agent implementation resides in the TOC Ministries AI-Presentation-Agent workspace. Existing RDC worker, gateway, MCP, preview and permission models remain unchanged.

The skill supports AI-based deck creation and operator-approved automatic presentation following with speech, BandMates song-section events, visual stage observations and two-way voice chat. The default voice provider is the user's primary AI app. Optional local Whisper and macOS voice facilities require explicit device permissions and local configuration.

The standalone engine exposes its own MCP stdio tools and an authenticated loopback API. The skill alone does not add tools to RDC's existing server, establish a live microphone stream or guarantee universal presentation app support.

Existing adapter prototypes: local HTML, Keynote and PowerPoint macOS AppleScript, ProPresenter REST, OBS WebSocket. Cross-platform, other software, streaming provider integrations and end-to-end live hardware behavior require separate validation. External output writes require an operator-owned grant. Never run AI inference in the BandMates real-time audio or MIDI thread.

See skills/ai-presentation-agent/SKILL.md and skills/ai-presentation-agent/references/integration.md for details.
