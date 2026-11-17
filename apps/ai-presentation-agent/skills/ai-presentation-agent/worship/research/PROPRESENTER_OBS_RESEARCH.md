# ProPresenter Worship Capabilities and Independent Equivalents
TOC Ministries | Research snapshot: November 16, 2026

## Situation
ProPresenter is absent from the owner's inspected iMac. OBS and Keynote were installed. The existing AI Presentation Agent already supports independent HTML decks, a persistent controller, BandMates cue observations and a preliminary OBS adapter. These are the strongest starting points. This document is **research and builder guidance**, not a claim that the new features were implemented, connected, or accepted in a real worship service.

## Priority feature comparison

| ProPresenter feature | Practical church use | Independent target for Presentation Agent | Status |
| --- | --- | --- | --- |
| Libraries, Playlists, Planning Center sequences | Sunday program with service segments and setlists | Local service-plan library, manual import, optional authorized Planning Center connection | Research requirement |
| Slide Groups and Arrangements | Verse 1, Chorus, Bridge, Verse 2, Tag, repeated refrains | Verse/chorus identity, saved arrangement, occurrence-aware live following, custom repeats | Existing cue support, expanded skill requirement |
| Worship lyric display and Reflow editor | Large centered lines, on-the-fly changes | Legible lyric layout and operator-approved changes with undo | Existing slide renderer, design requirement |
| Bible search and theme slides | Sermon references, selected verse ranges | NKJV reference search and licensed owner-supplied verse text, theme templates | Design requirement |
| Stage Screen layouts | Current/next lines, optional chord charts, notes, timers, messages | Authenticated stage confidence output, clear public/private separation | Design requirement |
| Audience Looks | Different appearance across audience/broadcast outputs | One cue clock, output-specific layer rules and themes | Design requirement |
| Output Layers | Masks, messages, props, announcements, slides, media, video inputs | Independent ordered layer compositor, manual clear/hold, stream-safe overlays | Design requirement |
| Slide Destination / Stage Only | Send a prompt only to performers | Explicit destination field with privacy filtering | Design requirement |
| Timers, messages and macros | Pre-service countdown, speaker timing and grouped transitions | Stage clock, countdown, safe action plan with preview and rollback | Design requirement |
| Camera, live video, NDI, SDI, Syphon | Camera switching and keyed lyrics | OBS source/camera integration, optional hardware-specific NDI/SDI bridge | Hardware/adapter dependent |
| Capture, streaming and recording | Distinct stream graphics, capture settings, live stream | OBS Studio for actual live video and audio production, independent stream overlays | Separate production validation |
| Remote and Stream Deck | Volunteer next/previous, blank, look/scene selection | Existing AI host, RDC/mobile controls and operator overrides | Adapter and device acceptance needed |
| Open API | External AI producer controls a licensed application | Optional official ProPresenter adapter when installed and accessible | Existing prototype, no native test |
| SongSelect and Planning Center | Licensed lyric lookup and service import | Optional credentialed import, owner review, offline cache only with permitted rights | Integration research |
| Multitracks and MIDI actions | Song timing, chord and click playback | BandMates cues plus verified real performance observations | Existing separate BandMates workflow |

## What the official documentation actually supports
**Screen architecture:** ProPresenter has Audience and Stage screen types. A venue can configure hardware-connected screens and compatible NDI, SDI and Syphon outputs, with hardware prerequisites. Audience Looks choose which layers and themes appear on distinct audience screens. ProPresenter's fixed output layers include masks, messages, props, announcements, slides, media and live video. This is the strongest conceptual model for a future independent layered renderer. Sources:
- https://support.renewedvision.com/hc/en-us/articles/360041879173-Screen-Configuration-in-ProPresenter
- https://support.renewedvision.com/hc/en-us/articles/13634000690323-ProPresenter-Output-Layers
- https://support.renewedvision.com/hc/en-us/articles/360041407174-Using-Looks-to-Show-Different-Screen-Content-in-ProPresenter

**Stage Screen:** A distinct confidence monitor may show current/next slide text and image, slide notes, chord charts, stage messages, group names, timers, clocks and capture status. The builder should model output privacy at the data/schema level, not merely hide private data with CSS. Sources:
- https://support.renewedvision.com/hc/en-us/articles/360041407794-Using-a-Stage-Screen-to-its-Full-Potential
- https://support.renewedvision.com/hc/en-us/articles/47985491763219-Using-Slide-Destination-within-ProPresenter

**Worship sequences:** Planning Center Song Sequences correspond to ProPresenter Arrangements composed of matched Slide Groups. Distinct identity for each verse/chorus and each repeated occurrence matters when a worship leader repeats or skips sections. Source:
- https://support.renewedvision.com/hc/en-us/articles/360062444614-Converting-a-Planning-Center-Song-Sequence-Into-a-ProPresenter-Arrangement

**Macros and operator controls:** Published Stream Deck integration supports next, previous, clear, slide groups, macros, props, cameras and capture controls. That suggests training in explicit action grouping, human priority, fault-safe retries and per-action permissions. Source:
- https://support.renewedvision.com/hc/en-us/articles/5284750340371-Setting-Up-The-ProPresenter-Stream-Deck-Plugin

**Bible and lyrics:** ProPresenter supports reference, passage and keyword Bible search and themes. Licensed Bibles require separate entitlements. SongSelect uses separate CCLI and advanced subscription credentials; public projection and livestream licensing should be assessed per church and song, not inferred from imported files. Sources:
- https://support.renewedvision.com/hc/en-us/articles/360041347594-Using-Bibles-in-ProPresenter
- https://support.renewedvision.com/hc/en-us/articles/360041814913-Installing-Bibles-in-ProPresenter
- https://support.renewedvision.com/hc/en-us/articles/360041815033-SongSelect-and-ProPresenter
- https://support.renewedvision.com/hc/en-us/articles/53940538326419-How-to-Display-Copyright-Information-in-ProPresenter

**Livestream and alpha keys:** ProPresenter can key graphics over live video using compatible video hardware, including NDI or SDI on supported systems. Our independent plan uses an HTML overlay inside OBS Browser Source before considering a hardware-specific key/fill implementation. ProPresenter's native capture or video infrastructure is an optional external system, not a required dependency. Source:
- https://support.renewedvision.com/hc/en-us/articles/18435523006739-Alpha-Keying-in-ProPresenter

## OBS as the independent live-streaming compositor
OBS Browser Source can place a web page over video and supports transparent backgrounds. Studio Mode distinguishes the Preview scene from the public Program scene. The obs-websocket protocol defines GetSceneList, GetCurrentProgramScene and SetCurrentProgramScene, among other requests, but actual scene switching must be permissioned and independently read back. An OBS scene change is distinct from starting the livestream or local recording. Sources:
- https://obsproject.com/kb/Browser-Source
- https://obsproject.com/kb/OBS-Studio-Overview
- https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md

## Production architecture recommendation for the builder
One authoritative service cue model drives **separate destinations**:
- Congregation screens: large fullscreen lyrics, Scriptures and announcements with suitable contrast.
- Private stage screens: current/next lyrics, chords, message and timer with separate authentication.
- Stream overlay: public-safe transparent lower thirds, references, names and titles over video from OBS.
- Operator console: service playlist, timing, live cue position, confidence/readback, next/hold/clear controls.

Never use a stage-confidence DOM as an OBS Browser Source. The Stage Screen might contain pastor notes and private instructions. Maintain separate schemas and access policies for each output.

## No-ProPresenter roadmap
Phase 1: training and reusable service data, lyric arrangements, reference-only Scripture, templates and rehearsal guide.
Phase 2: the owner builder incorporates service plan, output-specific cue schemas and read-only OBS preview using the existing director.
Phase 3: the builder qualifies synchronized multi-output live rendering, scene readback, manual override and cue state recovery with real cameras and displays.
Phase 4: optional external app adapters, service-plan import, copyright reporting, advanced audio/video routing, SDI/NDI and remote mobile controls.

Actual service planning, software interoperability, public broadcast and hardware output need separate acceptance. This skill's presence proves only that the **procedures and references exist**.
