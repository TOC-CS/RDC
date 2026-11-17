# Worship Production Skill Pack Design
TOC Ministries | November 16, 2026 | Research and education only

## User goal
Research ProPresenter's useful church and worship service capabilities and develop reusable AI Presentation Agent training skills so the existing owner/builder can implement as many of those capabilities as possible independently of ProPresenter. Support both in-person church services and simultaneous live video streaming. Preserve ProPresenter as an optional future integration when an authorized installation is available.

## Exact scope of this contribution
- Research existing ProPresenter worship tools, including service playlists, song arrangements, lyrics, Scripture, Looks, stage confidence, macros, timers, screen and layer configuration, NDI/SDI and livestream features.
- Research a no-ProPresenter equivalent using the current independent AI Presentation Agent and OBS Studio, while distinguishing features already present from implementation gaps.
- Create structured learning modules, source citations, operator playbooks, audience/stage/broadcast output separation, sample service plan and acceptance criteria for the active builder.
- No native app code, service implementation, integration commands, plugin publication, active output control, OBS activation, camera/microphone recording, or real stream operations as part of this task.

## Existing project boundary
Project: `~/RDC-Development/workspace/AI-Presentation-Agent/`. The root already has `src/director.mjs`, `src/deck.mjs`, `src/adapters.mjs`, integration documentation, an offline HTML renderer, BandMates bridge, managed session and limited OBS/ProPresenter adapters. These belong to an actively maintained owner session and are unchanged here. ProPresenter is not installed on the inspected iMac; OBS and Keynote were observed.

## Chosen approach
A nested `worship/SKILL.md` and supporting references live under the project's existing skills folder. All output examples are plain reference documents and JSON data. No executable or dependency files are part of the final skills-only deliverable. The other agent will connect these skills to the core product after Atlas review, independent tests and operator acceptance.

## What counts as success in this research phase
1. At least one official source for each central feature family and an honest separation of vendor facts versus project implementation.
2. Training for projection, private stage confidence, worship slides, sermon, Bible references, livestream graphics and safe operator controls.
3. Separate audience, stage and OBS public broadcast data boundaries.
4. 26 discoverable training modules with observable learning goals and realistic church use cases.
5. Realistic example Sunday plan, OBS scene suggestions and live rehearsal checklist, with no stream keys or active credentials.
6. Builder-facing requirements and acceptance gates written without touching the active app.
7. Structural verification of all files and example JSON; report any unverified native behaviors without claiming a functioning livestream.

## Safety and privacy
The same song cue may produce a full projector lyric, a private musician chord display, and a transparent public broadcast lower third. Maintain one authoritative cue position but separate output schemas, authentication and physical destination verification. Do not leak stage notes, pastor notes, private Talkback, stream credentials or private prayer needs. Copyrighted song and NKJV text require owner-controlled licensed sources; use reference-only Bible slides when needed.

## Stage after research
The owner builder implements gradually: offline service-planning integration, multi-output stage/broadcast views, dedicated OBS connection and readback, real live lyric following, livestream control and authorized external apps, then real venue acceptance. Those activities are requirements handed to another session, not work accomplished by this research package.
