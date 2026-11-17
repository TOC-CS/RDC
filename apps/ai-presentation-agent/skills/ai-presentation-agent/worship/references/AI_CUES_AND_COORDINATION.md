# AI Worship Cue Recognition, BandMates and Operator Coordination
Learning skill for a director who can follow live musicians, pastors and readers in a church service.

## Source of truth
The main service plan stores authorized content, but **actual live performance determines timing**. The worship leader may sing a chorus twice or skip a verse; a pastor may pause or address an unplanned passage. The PresentationDirector owns the current slide. BandMates owns music events. OBS owns camera/stream state. The presentation agent uses evidence to propose a cue and a verified adapter to move the output.

## Recognition evidence categories
1. **Explicit human instruction:** "Presentation agent, hold slides", "show next chorus", "show John 3:16", or manual operator selection. Commands need reliable wake phrase or push-to-talk in noisy environments.
2. **BandMates musical metadata:** song ID/title, section, occurrence, bar or chord event. These are useful when verified, but an accompaniment schedule is not proof that a singer actually performed the planned words.
3. **Finalized speech/singing transcript:** recognized words, timestamp, audio source and confidence. Unstable partial transcriptions cannot independently advance slides.
4. **Stage/leader camera observation:** trusted physical camera role and stable repeated detection. Never feed the presentation output screen back into recognition, which could create an error loop.
5. **Service timers:** elapsed time and known schedule may suggest an expected next item, but do not replace observed evidence.

## Autonomous-following training policy
- For every new cue, capture prior slide, candidate slide, evidence type, timestamp, source confidence, song/section/occurrence, reason and operator override state.
- Disambiguate duplicate slide contents and repeated choruses using occurrence identity or intervening distinct evidence.
- When evidence is stale, contradictory or insufficient, **hold** the currently verified slide. Report what is missing rather than guessing the next Scripture.
- Never autoplay or send output writes from an unsupported AI host, a plain text prompt, or a live BandMates audio/MIDI callback.
- Manual Next, Previous, Hold, Resume, Goto, Clear and emergency blank must be available independently of voice or vision processing.
- Voice Talkback responses should use an independently confirmed private monitor. Public livestream speakers or default Mac output could leak AI conversation into the service.

## Coordination with livestream
A single confirmed lyric cue can update the auditorium lyric and a separate public-safe stream overlay. The camera scene change is a distinct production action that can lag or be refused, leaving the slide position unchanged. Preserve a queue and event identity across connection loss, rather than replaying every song section on reconnect. Do not let the AI click OBS multiple times when the prior result is uncertain.

Speaker/pastor workflow:
- Confirm requested NKJV reference from exact passage.
- Show a reference-only or licensed verse excerpt.
- Prepare an audience layout and a compact broadcast reference lower third.
- Keep private sermon notes on stage confidence screen.
- Preserve manual override if the pastor changes topic or passage.

## Scenarios for skill evaluation
- Repeated Chorus 2 after bridge: correctly identify the intended occurrence and never jump to earlier chorus.
- Song key changed live: correct private musician display after authorization, leave public lyric unchanged.
- Mic transcript says a common phrase found in five Scriptures: ask or hold instead of guessing.
- BandMates gives planned song.section but vocalist sings a different section: hold on disagreement.
- Audio input disappears for 4 seconds: do not continue advancing based on elapsed bars.
- OBS scene readback differs from acknowledged command: report uncertain broadcast state; no blind retry.
- A private stage note contains an unannounced prayer need: never serialize to public screen or stream overlay.
- An operator chooses Hold while AI cue arrives: manual Hold wins.

## Implementation target for other agent
Reuse the current `src/director.mjs` event model, its existing `slide.occurrence`, manual commands and recovery semantics. Build new service-level training/output logic around its contract. The skill has no runtime hooks and will not run an AI model, stream microphone frames or call OBS.
