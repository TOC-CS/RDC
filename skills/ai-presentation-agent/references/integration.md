# AI Presentation Agent integration reference

Source directory on the authorized iMac: `RDC-Development/workspace/AI-Presentation-Agent`. The agent operates independently from the RDC gateway and BandMates real-time music engine.

**MCP:** `node scripts/mcp.mjs`, exposing `presentation_capabilities`, `presentation_status`, `presentation_create`, `presentation_load`, `presentation_start`, `presentation_command`, `presentation_cue`, `presentation_watch`, `presentation_voice`, `presentation_select_output`, `presentation_arm`, and deck export tools. Check the host's actual tool discovery first. A newly packaged skill does not automatically register the separate MCP process in ChatGPT.

**Local API:** `node scripts/serve.mjs` with operator-supplied `PRESENTATION_API_TOKEN` (16+ bytes). Default bind is `127.0.0.1:8789`. Authenticated HTTP endpoints are `/v1/status`, `/v1/capabilities`, `/v1/load`, `/v1/create`, `/v1/start`, `/v1/command`, `/v1/cue`, `/v1/watch`, `/v1/voice`, `/v1/output`, `/v1/arm`. Do not place credentials in public URLs. External control separately requires `PRESENTATION_ALLOW_EXTERNAL_CONTROL=1` at launch and an explicit `presentation_arm` call.

**BandMates:** `integrations/bandmates.mjs` converts current song section snapshots into independent cue events. Call from a non-real-time control thread, using an actual current song name and a scoped session identifier. The installed native BandMates app remains a separate qualification item.

**Voice:** Host-AI voice transcripts and spoken replies by default; optional local Whisper and macOS speech after configured microphone permission. **Vision:** permissioned camera observations are processed separately, with repeated confirmations, a cooldown, and presentation-output rejection. Apple Vision local OCR exists but its physical-device behavior needs testing.

**Presentation apps:** Keynote and PowerPoint AppleScript; ProPresenter REST; OBS WebSocket 5; offline HTML. Actual app state/readback is needed before asserting live success. Streaming providers operate through configured presentation/broadcast adapters. OS-specific Windows, iOS, Android, Adobe and arbitrary app coverage is unqualified.

**Compatibility:** Preserve RDC identity, app bindings, default prompts, on-boarding skill, permission boundaries and source preview. Build or publish further application integrations only after device/host tests, without touching active mixer or streaming sessions.

## Durable controller and operator stop

The owner-authenticated managed server runs on a private loopback port, with separate random viewer/control credentials held only in an owner-only control file. `node scripts/presentationctl.mjs status` and `capabilities` safely discover the active source. `load --file` takes a structured deck, `start assisted` begins rehearsal, and `next --request-id ...` advances with idempotent receipts. `stop` disarms and ends local following without blanking or quitting the native screen. The viewer is read-only; use `viewer-check` or private `viewer-export` for owner-authorized display, never print the actual viewer token URL.

A crash preserves a 0600 token-free `last-known.json` deck/index file. Restart refuses takeover of an active PID and replaces a stale control file only after independent dead-process verification. Restored state is held RECOVERED PREVIEW, never live or armed. Physical projector and native app resynchronization require separate verified operator controls. See `references/managed-session.md`.

## Private voice output

The main AI host voice remains default. Local Whisper.cpp speech is optional and must have an explicit model/input device and OS permission. An owner-supervised private output must be selected from `node scripts/local-microphone.mjs --list-outputs` before local spoken replies; `--output-device DEVICE_ID --confirm-private-monitor` is required. Default macOS speech output is forbidden because it may reach a public mixer. Audio routing is not certified without a live soundcheck.

## Source verification limits

Software integration tests cover MCP/HTTP commands, native protocol mocks, offline FFmpeg/Apple Vision OCR fixtures, actual local Whisper model transcription, source-bound viewer, managed server crash recovery and local durability measurements. The above tests do not certify physical projector output, live microphone/camera, third-party application native control, Windows/mobile hardware, production RDC forwarding, or live comment OAuth/posting.

## Completed presentation cleanup

Use `presentation_stop`, then `presentation_unload` to return the persistent service to an empty state. The optional CLI equivalents are `node scripts/presentationctl.mjs stop` and `node scripts/presentationctl.mjs unload`. The latter deletes the owner-only crash checkpoint; a finished deck cannot reappear after restarting the service. If checkpoint deletion fails, the unload request reports an error that can be safely retried after storage repair. A connected live viewer clears its old slide DOM and displays `PRESENTATION CLEARED` without physically blanking any projector output.
## Advanced owner-source contract, November 17 2026

The current isolated development branch contains the verified `presentation_load_worship_library`, `presentation_communication_capabilities`, `presentation_communication_prepare` MCP methods. Their corresponding local routes are `POST /v1/worship/library/load`, `GET /v1/communications/capabilities`, and `POST /v1/communications/prepare`, all requiring the existing operator bearer. Catalog source refs require matching content SHA/revision and independent local/stream rights. Communication endpoints return only metadata drafts; no bus delivery or third-party chat control occurs.

The independent stage teleprompter uses a distinct stage credential for readback and a second operator bearer for changes. GET `/v1/stage/teleprompt?key=STAGE_TOKEN` is stage-only. POST `/v1/stage/teleprompt` requires operator bearer and `X-Stage-Credential`, with explicit `PRESENTATION_ALLOW_TELEPROMPT=1` on an owner-approved restart. Source-bound current/next speaker/reader/singer content is never part of audience or stream packets. The `presentationctl.mjs teleprompt-` commands redact private bodies, notes and tokens.

Read `rdc-communications.md` for the existing Atlas Bus three-way communications path and its synthetic-only limitations. There is no active live chat enrollment, provider session wake, or automatic control of another AI chat through this published skill. Continue to distinguish installed instructions from an actually connected MCP server and independently qualified venue hardware.
## Existing local worship looks, stage timer and independently authorized outputs

MCP supports `presentation_load_worship`, `presentation_worship_rundown`, `presentation_worship_looks`, `presentation_worship_visibility_set` and `presentation_worship_look_set`. The audience local browser blank is a visible HTML blackout, not a physical projector write; the broadcast clear is only a local graphics layer, not OBS Program. Look and visibility changes require a separate operator launch grant `PRESENTATION_ALLOW_WORSHIP_LOOK_EDIT=1`. OBS Studio Mode and Preview/Program status are available through separate read-only diagnostics when OBS is actually connected.

The private stage timer keeps its private caption or label out of public audience and stream packets. It needs `PRESENTATION_ALLOW_STAGE_CLOCK=1` at server startup, plus both the operator bearer and the distinct private stage credential (`X-Stage-Credential`) for `POST /v1/stage/clock`. A separately authorized stage-only GET and `node scripts/presentationctl.mjs stage-clock-status` never expose the label in general logs. Operator authorization for timer, Looks, external output and teleprompter are separate and must not be inferred from an API bearer or a skill release.
