# Church and Worship Service Production Playbook
Skill instructions for AI service director, worship leader, pastor, volunteer operator and livestream producer.

## Roles and authority
The service leader controls the real service. An assigned presentation operator can intervene immediately. The AI assists, prepares, listens and makes confirmed cue decisions. The existing PresentationDirector is the single controller of presentation cue state. OBS is the video compositor, with its own Program and stream controls. BandMates is an optional musician cue source, with separate real-time timing.

### Service preparation
1. Confirm service date, church, location, event type, approximate duration and intended audiences. Establish whether the event is in-person, livestreamed, recorded or hybrid.
2. Build a structured order with pre-service countdown, welcome, worship sets, announcements, prayer, Scripture reading, sermon, altar invitation or response, closing, and optional post-service announcements. Services vary; keep the order editable during rehearsal.
3. Import original or permitted song text, the selected key, number of verses, chorus/bridge/tag, arrangement, repeated sections and cue notes. Store lyrics separately from the displayed slide layout so arrangements can change without editing source text.
4. Collect NKJV Scripture references. Add verse text only from verified authorized material, preserve exact book/chapter/verse boundaries and display translation credit where required.
5. Document for each item: estimated time, lead person, optional BandMates song ID, section IDs, reference, intended slide style, stage notes, broadcast overlay, camera-scene suggestion and safe fallbacks.
6. Prepare projection, stage confidence and stream looks independently. Never derive stage privacy from CSS hiding alone. A public output receives only public-safe fields.
7. Inventory assets: logo, backgrounds, videos, Scriptures, music, licensing, connected screens, camera inputs, OBS scene names and operator permissions. Missing content produces a visible unresolved item, not invented media.
8. Save a rehearsable service copy, a protected baseline and last authorized edits. Clearly distinguish prepared from saved, activated and publicly visible.

### Rehearsal flow
- Run pre-service countdown and service intro with an operator present.
- Check song slide divisions: one or two short lyric lines per cue when appropriate, consistent readability, high contrast and comfortable pacing. Check a planned repeat of the chorus plus an unexpected live repeat.
- Check the pastor's Scripture reference and sermon title; allow a manual cue to an unplanned verse only after the actual passage is confirmed.
- Verify stage cue next/current, private notes, countdown and musicians' sightlines independently of audience video.
- Verify each OBS Preview scene, then Program separately, checking lyric placement, camera framing, audio, and unexpected overlays. Match broadcast safe areas to real output aspect ratio.
- Test the lead user saying next, previous, hold, resume, clear, and a specific song or Scripture reference. Stage and livestream outputs must not race or diverge.
- Simulate unclear sung lyrics, internet interruption, camera dropout, computer restart, accidental note or chord exposure, OBS disconnect and overloaded CPU. Hold or fall back to an operator-safe scene as appropriate.

### During service
- **Before automatic advance:** compare current song, section, occurrence, speaker, elapsed time, finalized speech, BandMates metadata and optional camera observations. Never advance on inferred music timing alone.
- Honor manual operator cues first. A worship leader may repeat, skip or extend a chorus; mark section occurrence and retain a stable cue identity.
- Use audience song lyric slides during worship, title or Scripture overlays for the livestream when appropriate, and private current/next text on stage.
- For sermon teaching, let the speaker supply requested references; avoid guessing a Scripture solely from similar phrases.
- Keep camera transitions within the verified OBS scene map. Use an explicit approval and readback gate for any external scene write.
- If the presentation or stream readback disagrees with the intended state, stop automatic changes, report uncertainty, preserve manual control and verify the real output.

### After service
- Stop and clear the presentation only through the owner's confirmed workflow; presentation Stop and OBS stream Stop are independent.
- Preserve authorized service notes and correction history without copying private captions or accounts.
- Confirm stream and local recording status, output archives if authorized, and any rights reports the organization must submit.
- Save reusable song arrangements and approved stage/stream layouts independently of this one performance.

## Assistant behavior training cases
1. The worship leader sings the chorus again after an instrumental. Expected: select the correct repeated chorus after corroboration, never advance to the planned verse just because elapsed time suggests it.
2. The singer skips verse two. Expected: skip to verified next content using an explicit cue or repeated high-confidence evidence.
3. The pastor requests an unplanned NKJV reference. Expected: show reference only until authorized exact text is provided, then proceed with verified verse text.
4. Camera operator changes OBS Program independently. Expected: respect actual Program scene readback and avoid forcing a stale scene.
5. Stage confidence has private notes. Expected: no note text in congregation slide deck, stream Browser Source, screen-sharing capture or unrestricted logs.
6. OBS stream disconnects while projection continues. Expected: congregation display remains independently operable and the AI reports the broadcast fault without automatically re-starting broadcast.
7. Service ends. Expected: verify intentional stream stop, then presentation stop and secure cleanup as distinct decisions.

Sources: `../research/PROPRESENTER_OBS_RESEARCH.md` and `../research/SOURCES.md`.
