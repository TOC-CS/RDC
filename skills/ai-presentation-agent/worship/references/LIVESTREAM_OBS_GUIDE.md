# Livestream Worship Production with OBS Studio
Training for an AI presentation and video director operating with a church livestream team. This document provides production skills and future builder acceptance. It does not launch OBS, access a stream key or start a broadcast.

## Independent output architecture
```
                      Service Plan / human worship leader
                                    |
                    AI PresentationDirector (single cue owner)
                                    |
             +----------------------+----------------------+
             |                      |                      |
        Congregation             Private Stage           Public Cue
        projector lyrics         current + next           stream-safe fields
        full Scripture           notes, chords, timer          |
                                                               v
                                                Transparent lyric overlay
                                                               |
        Cameras / capture cards / media ------------------> OBS scenes
        Broadcast-specific audio --------------------------> OBS mixer
                                                               |
                                                     OBS Preview -> Program
                                                               |
                                                 Streaming / recording only
                                                 after operator authorization
```

## Setup skills
1. Identify the actual OBS version, scene collection, profile and connected cameras. Check which camera inputs exist. USB, capture cards, NDI and SDI have different drivers, bandwidth and device requirements.
2. Choose broadcast canvas size and FPS suitable for actual output and equipment. Do not assume 1920x1080 at 30 fps is correct for every camera, projector or streaming platform.
3. Prepare scenes: pre-service countdown, worship wide camera, worship close-up, worship with lyrics, Scripture, sermon, announcements, prayer, media playback, offering if used, closing, and emergency clean camera. Each suggestion must be mapped to an existing scene name or UUID before live control.
4. Add lower-third lyric and Scripture overlays as **public read-only Browser Sources** over relevant camera scenes. OBS Browser Source supports transparent HTML/CSS when the page itself is transparent. Check Browser Source width/height, refresh settings and text safe areas.
5. If a separate stage confidence output exists, keep its data and token entirely outside OBS. OBS desktop capture or a shared display may accidentally expose pastor notes even when the overlay is safe.
6. Identify the independent stream audio mix. The house FOH and private Talkback can be routed differently. Test vocals, instruments, BandMates output, audio return from prerecorded videos, output sample rate and audio/video sync in a supervised rehearsal.
7. In OBS **Studio Mode**, distinguish Preview from Program. An operator may adjust the next scene in Preview without changing viewers' Program output. Transition with explicit operator permission and inspect Program again.
8. Prepare a local recording if wanted with suitable folder permissions, disk space, bitrate/quality and storage monitoring. Recording and livestream controls are independent.
9. Configure stream destination and any streaming authentication only through the owner's authorized OBS profile or platform connection. Never write a stream key into church service JSON, AI chat, build logs or a browser-source URL.
10. Review accessibility: captions or hearing interpretation if available, title-safe text size and speaker names. Don't put lower thirds over essential faces or official captions.

## Live cue actions, separated by blast radius
- **Read-only:** get scene list, selected Program and Preview, source visibility, audio meter/stream status when exposed.
- **Rehearsal preview:** prepare transparent lower-third, countdown slate, camera composition, overlay position and song appearance. The operator explicitly reviews.
- **Presentation-only write:** advance lyric/Scripture on a verified public overlay that has been separately armed, without changing camera, stream or recording.
- **OBS production write:** change active Program scene or source visibility with exact scene identity, allowed target, explicit operator approval and readback.
- **Critical broadcast action:** StartStreaming, StopStreaming, StartRecord and StopRecord each require separate deliberate owner/operator authorization with confirmation and independent observed status.

## On-air verification and monitoring
Check the actual Program scene and source visibility after any authorized scene change. Watch OBS statistics for dropped frames, rendering lag, encoding lag and output bitrate. Confirm stream platform preview with appropriate account authorization where available, in addition to local Program, because a correct local scene does not prove network transmission. Verify camera audio/video sync and that the correct audio mix is audible to viewers.

Unexpected event handling:
- Wrong Scripture or lyrics: hold the display cue, clear the incorrect public text, correct reference and restore after review.
- Wrong camera scene: show a known clean fallback when approved, ask operator for the verified scene, avoid retrying uncertain actions blindly.
- OBS disconnect: keep the existing auditorium show operational, mark stream automation suspended, preserve the last confirmed public overlay.
- Internet failure: present local worship normally; inform operator that streaming is degraded and do not auto-start another broadcast without authorization.
- Audio absent on stream: isolate stream audio bus separately from FOH, avoid raising house speakers as a blind workaround.
- Private note exposed: remove public capture source, alert operator, preserve evidence only in authorized private diagnostics, review privacy filter before rearming.

## Macros and video transitions
A service transition can involve many steps: finish worship chorus, show pastor camera, clear lyrics, show sermon title, switch confidence notes, start sermon timer. Teach the AI to describe expected states, affected outputs and rollback separately. The production builder can implement a transaction with idempotency keys, readback and manual override; the skill itself supplies no macro executor.

## OBS vendor protocol
OBS Browser Source: https://obsproject.com/kb/Browser-Source
OBS Studio Mode: https://obsproject.com/kb/OBS-Studio-Overview
OBS Virtual Camera: https://obsproject.com/kb/virtual-camera-guide
OBS WebSocket 5: https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md

Published websocket requests include GetSceneList, GetCurrentPreviewScene, GetCurrentProgramScene and SetCurrentProgramScene. Treat response acceptance and output proof as separate stages. Browser overlays and preview sources must not contain owner API credentials.
