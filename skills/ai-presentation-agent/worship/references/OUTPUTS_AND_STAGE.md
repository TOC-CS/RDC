# Multi-Screen Outputs, Private Confidence and ProPresenter Looks

## The essential output principle
One verified **service cue** can produce several independently rendered experiences. A church projector, stage confidence monitor, livestream lower third and operator preview require different audiences, assets and disclosure permissions.

| Output | Target | Contents | Privacy |
| --- | --- | --- | --- |
| Congregation | Main sanctuary projector, TV wall or lobby display | Full lyrics, NKJV reference or licensed text, announcements, service countdowns, images | Public |
| Stage confidence | Musician, vocalist and pastor monitor | Current/next lyric, optional chords, setlist, song key, sermon cue, timers, private notes | Restricted |
| Broadcast graphics | OBS browser overlay or dedicated key/fill path | Public lyric lower thirds, Scripture reference, pastor name, sermon title, lower banner, end card | Public, no tokens |
| Operator preview | Authorized engineer UI | Active cue, next cue, target outputs, health/readback, editable rundown, manual overrides | Owner/operator |
| Audio | Stream mix and separate house/monitor channels | Dedicated sound buses and Talkback restrictions | Device and bus specific |

Do not mirror the full stage-confidence page into OBS, a public projector or a screen-shared meeting. Hiding notes with CSS alone still ships them into the browser payload. Apply a privacy filter before preparing per-output content.

## ProPresenter concepts to teach
ProPresenter supports Audience and Stage screens, output Looks, and fixed output layers such as masks, messages, props, announcements, slides, media and live video. The Stage Screen can display current and next slide, song/group names, chord charts, slides, messages, clocks and streaming status. Slides can be explicitly Stage Only. These features suggest two original components for the builder:
- A public-safe **output content model** with destination, intended look, layer ordering and visibility permissions.
- A private stage **confidence schema** with separate authorization, no public serialization, and independent current/next cue readback.

## Example presentation looks
- Worship: congregation sees two lines of large lyrics on a background; stream sees compact transparent lower thirds over the wide worship camera; stage sees next line, song section and optional chords.
- Sermon: congregation sees a clean NKJV reference with licensed text if permitted; stream sees reference and pastor name next to the camera view; stage sees next sermon cue and elapsed time.
- Announcement: congregation sees full announcement and QR or contact details only if reviewed; stream sees concise public-safe event caption; stage sees the upcoming transition.
- Prayer: congregation sees a calm prayer title or blank; stream sees pastor camera with minimal text; stage displays private prayer and next segment instructions.

## Timing and cue integrity
- Treat director current index, sequence, section occurrence and selected scene as separate fields. A scene being suggested says nothing about whether it is active.
- If one output fails, preserve healthy destinations and report the affected output, rather than blindly advancing every screen again.
- On a project crash, restore last-known content only in a held preview with external outputs disarmed. Human reauthorization and actual readback are required before resuming live control.
- Operator manual Clear, Hide Layer and Hold need independent semantics. Clearing a lyric overlay must not blank a camera or stop the stream.

## Hardware differences
- Ordinary HDMI/DisplayPort can drive additional displays subject to the host graphics hardware and available ports.
- Virtual NDI, SDI, Syphon, hardware alpha key/fill and Blackmagic capture require compatible applications, drivers, hardware and acceptance testing.
- Multiple browser windows on one computer are useful for learning, but proof of a real audience projector or livestream needs actual device and broadcast readback.

References:
- https://support.renewedvision.com/hc/en-us/articles/360041879173-Screen-Configuration-in-ProPresenter
- https://support.renewedvision.com/hc/en-us/articles/360041407174-Using-Looks-to-Show-Different-Screen-Content-in-ProPresenter
- https://support.renewedvision.com/hc/en-us/articles/13634000690323-ProPresenter-Output-Layers
- https://support.renewedvision.com/hc/en-us/articles/360041407794-Using-a-Stage-Screen-to-its-Full-Potential
- https://support.renewedvision.com/hc/en-us/articles/47985491763219-Using-Slide-Destination-within-ProPresenter
