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


## Managed crash recovery, live-viewer authority and private talkback

An owner-authorized managed-server.mjs stores a private token-free last-known.json file with the previous deck and local index, and refuses to auto-arm or auto-project it after a process crash. It can replace stale control credentials only when the previous PID is proven dead; it refuses takeover of an active session. presentationctl.mjs sends authenticated local commands using private credentials on disk instead of exposing tokens in AI tool arguments.

The authenticated live viewer uses direct slide-state notifications with polling fallback for older handlers. Unlike the offline HTML player, a live viewer cannot independently advance through keyboard, local button or postMessage inputs. Its status label distinguishes LIVE, HELD, PREVIEW ONLY, RECOVERED PREVIEW, RECONNECTING and OUTPUT UNVERIFIED.

Local speech playback requires an operator-confirmed private output. Query IDs with node scripts/local-microphone.mjs --list-outputs without capture/playback; then select --output-device DEVICE_ID and --confirm-private-monitor alongside --commands --speak, explicit microphone device and local model path. The default system speaker route is forbidden for local AI talkback. Physical house/stream isolation remains an outstanding venue acceptance step.

## Operator stop contract

MCP presentation_stop and authenticated POST /v1/stop stop the local controller without sending native display or projector commands. The privacy-preserving CLI node scripts/presentationctl.mjs stop calls the same path. Physical output blanking is a distinct operation and remains app-specific.


## Finished presentation unload and privacy clearing

After node scripts/presentationctl.mjs stop, use node scripts/presentationctl.mjs unload or the authenticated presentation_unload MCP / POST /v1/unload action. The stopped-only command removes the loaded deck and deletes the owner-only last-known.json recovery checkpoint so finished slides cannot reappear on a process restart. Failure to delete the checkpoint is reported and can be safely retried after storage repair. The already connected live viewer receives loaded:false, clears previous slide content from its DOM, and shows PRESENTATION CLEARED. Unload never blanks a native projector or quits a separate presentation app.

## Worship production outputs and stage-only operator permissions, November 17 2026

The nested worship skill at skills/ai-presentation-agent/worship/ supplies researched church-service practices, 26 modules and 18 acceptance scenarios. The Presentation Agent runtime remains independent of ProPresenter. It uses one authoritative cue state to render independently restricted audience, stage confidence and broadcast outputs. Original and licensed song/NKJV text must be separately authorized for each destination, and stage notes, chords and private speech never appear in public stream payloads.

MCP supports presentation_load_worship, presentation_worship_rundown, presentation_worship_looks, presentation_worship_look_set, presentation_worship_visibility and presentation_worship_visibility_set. Owner-authorized local HTTP provides separate audience/stage/broadcast Look and visibility routes, with public data whitelisted at source. The local audience browser blank is an HTML blackout, not a physical projector write. Broadcast clear hides OBS-compatible transparent lyrics, without changing OBS Program or starting/stopping streaming or recording. Look/visibility edits require a separate owner grant: PRESENTATION_ALLOW_WORSHIP_LOOK_EDIT=1 at server startup.

The private stage countdown is routed exclusively to the stage confidence view. It may show a private label and remaining minutes/seconds but never automatically advances slides. POST /v1/stage/clock requires the operator bearer AND the distinct private stage credential in X-Stage-Credential, with PRESENTATION_ALLOW_STAGE_CLOCK=1 at startup. GET /v1/stage/clock with the independently authorized stage key is private. Ordinary audience and stream viewers, status, operator rundown and general MCP tools never serialize the private timer label.

RDC owner commands include stage-clock --file ABSOLUTE_OWNER_ONLY_JSON, stage-clock-status, stage-clock-start, stage-clock-pause, stage-clock-resume and stage-clock-reset. The configuration file must be owner-owned, owner-only and not a symlink. All CLI responses omit the private timer caption. No native app, camera, microphone, audio, projection, livestream or MIDI is activated by these commands.

The read-only venue-readiness command reports macOS display candidates, and preflight adds separate Presentation Agent, BandMates, display and OBS read-only statuses. OBS production diagnostics are available through obs-production-status with separate Studio Preview/Program, stream/record status and frame metrics; OBS WebSocket may be unavailable if the app is not connected. A connected output or accepted network command cannot qualify a real projector or remote streaming provider. Real stage, broadcast, hardware and Atlas acceptance remain outstanding; a controlled production restart or plugin release requires independent operator approval.
