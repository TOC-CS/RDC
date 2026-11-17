# AI Presentation Agent integration guide
Date: November 16, 2026

Human AI voice, BandMates section events, and stage camera observations reach the observation filter, then the PresentationDirector, then an optional external output adapter. Manual, assisted and automatic modes share this route. The BandMates audio/MIDI performance callback remains independent of slide processing.

Main AI provider voice is the default. Submit speech transcripts to presentation_voice; when speakByHost is true, let the user's AI app read the returned reply aloud. The agent never pretends every AI platform can send continuous microphone frames to MCP tools.

Visual following consumes interpreted visual observations through presentation_watch. A local camera or host AI vision engine must produce these observations. Stage, speaker and room observations require two stable confirmed frames to change slides. Never feed presentation output back into visual following. Native camera acquisition and live computer vision have not yet been end-to-end verified.

The passive BandMates bridge in integrations/bandmates.mjs converts current song-dynamics snapshots into presentation cues without modifying the real-time audio path. The caller must supply the actual song title and a cue recipient. Do not call this bridge from a CoreAudio or MIDI callback.

The standard transport is MCP over JSON-RPC stdio using scripts/mcp.mjs. An independent authenticated loopback HTTP API is available using node scripts/serve.mjs, with a strong local PRESENTATION_API_TOKEN environment value. It binds only to 127.0.0.1:8789. HTTP requires Authorization: Bearer token. Supported endpoints include GET /v1/status and /v1/capabilities, and POST /v1/load, /v1/create, /v1/start, /v1/command, /v1/cue, /v1/watch, /v1/voice, /v1/output and /v1/arm.

External presentation app writes require explicit operator permission. The API bearer token alone does not enable them. The local environment must contain PRESENTATION_ALLOW_EXTERNAL_CONTROL=1 and the agent must arm the configured output.

ProPresenter routes confirmed in the published API include GET /v1/presentation/active/next/trigger, previous/trigger, and GET /v1/presentation/{uuid}/{index}/trigger, with zero-based slide indexes. The OBS protocol uses WebSocket 5 Hello, Identify and SetCurrentProgramScene. Each deck slide requires the corresponding existing OBS scene name. Native Keynote and PowerPoint AppleScript command syntax compiled against installed macOS application dictionaries. Full live control and readback were not tested while these apps may be in use.

Real-time tracking must be rehearsed with actual microphones, video sources, software and latency conditions. The engine currently receives external speech and camera observations. Native capture sources, cross-platform APIs and installed application interoperability remain follow-on work.

References:
ProPresenter OpenAPI: https://openapi.propresenter.com/
OBS WebSocket 5 protocol: https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md

## Local live browser viewer

Set optional PRESENTATION_VIEW_TOKEN in the local MCP or API launch environment. Once a deck is loaded, open http://127.0.0.1:8789/v1/viewer?key=YOUR_VIEW_TOKEN on the same computer to see a read-only browser presentation. The viewer receives live slide updates by server-sent events, using separate read-only authorization from the private API control token. No microphone, camera or GUI automation is required for browser output.

The viewer token appears in the local URL and may be stored in browser history. Treat it as a private display credential. In the default configuration without a viewer token, the browser output endpoint remains disabled. Run npm run test:browser for isolated headless-Chrome confirmation. This viewer is loopback only. Streaming to another physical machine requires a separate authenticated deployment that has not been implemented.

## Verified additions, November 16, 2026

- The serialized PresentationDirector blocks concurrent command races, disallows arming through ordinary presentation_command calls, and preserves state if native startup fails.
- A repeat-cue guard prevents continuous speech or repeated camera frames from jumping to later instances of the same chorus. BandMates sends an explicit positive occurrence number when provided by its current song-dynamics snapshot. Operators retain manual override.
- ProPresenter readback observes the active cue through GET /v1/presentation/slide_index. MCP tool presentation_readback and authenticated local GET /v1/readback expose whether the actual app cue matches the expected index. Some other adapters cannot independently confirm output.
- Windows PowerPoint uses an existing slideshow COM bridge through Windows PowerShell, with next, previous, goto and CurrentShowPosition readback. Source contract tests pass on macOS, but Windows execution still requires a separate verified host and user approval.
- A local HTTP venue simulator verified a complete BandMates cue, voice command, slide output and readback sequence. No physical ProPresenter instance was controlled.
