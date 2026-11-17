# Worship Lyrics, Scripture, Song Arrangements and Content Authorization

## Original skill targets
- Organize a reusable song library by title, author, key, meter, tempo, licensing record, musical form and lyric sections.
- Sections: intro, Verse 1, Verse 2, Pre-Chorus, Chorus, Bridge, Tag, Instrumental, Outro and custom names. Each section has a stable ID. A performance arrangement references section IDs and repetition count, not duplicated pasted text.
- Assign unique occurrence identifiers when the same chorus appears in different places, including ad hoc repeats. This prevents autonomous following from skipping the wrong repeated chorus.
- Keep musician chords, key changes and rehearsal notes on private stage output only. Audience and stream representations inherit text and reference fields with appropriate public-facing credit.
- Split public lyrics by comfortable visual size and natural sung phrases, often one or two lines per slide. Handle a chorus with two phrase screens as multiple positions under the same section occurrence. Screen layout may differ for full projector versus streaming lower thirds.
- Provide live edit and rollback requirements: spelling, capitalization, accents, repetition, lyric line wrapping, and song order. Validate a live edit before sending changed words to congregation or stream.

## Spoken and sung following
Inputs include confirmed BandMates song/section/occurrence metadata, finalized speech transcripts, explicitly supplied lyrics and optional isolated singing recognition. The assistant should compare actual sung words against the expected current and upcoming lyrics with confidence and timestamp checks.

Do not advance on a preliminary partial transcript, unverified melody, tempo tick or rough music similarity. A singer can improvise, skip, repeat and extend. Manual Hold/Resume, jump-to-section and "show chorus" remain first-class cues. The existing independent presentation director already implements part of this concept, and the builder owns runtime integration.

## Scripture in a church setting
- Use **NKJV only** as the preferred display translation for this project. Preserve the exact displayed translation label and full passage reference.
- A reference such as "John 3:16 (NKJV)" is a valid standalone slide. For full verse body, use owner-supplied text covered by actual display rights, with exact source and range.
- A scriptural reference should be normalized and validated to identify book, chapter and verse; ranges may cross verses as the operator requests. Avoid silently replacing a requested passage with a different translation or paraphrase.
- Support search by reference, chapter navigation and keywords **only** when the authorized Bible data source is actually connected. Do not claim offline NKJV full-text availability based on the license for another product.
- Congregation text may show reference and authorized passage. Stage may show next verse and notes. Livestream can show a compact reference lower third or an authorized excerpt. The chosen layout depends on reading speed and camera composition.
- Do not allow a sermon keyword matcher to auto-project Scripture without confirmed context. Biblical terms recur across books and can produce false matches.

## Permissions and reporting
Renewed Vision's Bible installation guide separates free/public-domain and licensed translation copies, with paid translations licensed by computer in their product. A separate permission is required for any independent redistribution or new app content use. SongSelect integration requires an eligible CCLI license and subscription as applicable, and song reporting/copyright displays can be obligations for certain usage. Review scope for projection versus streaming, downloads, recordings and social clips with the actual rights holders. Never embed an unlicensed lyric library in a public or downloadable application.

## Original role examples
- "Sing original song, Verse 1, Chorus, Verse 2, Chorus, Bridge, Chorus twice." Store one chorus source with three distinct occurrence positions.
- "Show Psalm 100:1-2." Prepare NKJV reference-only unless cleared passage text is available.
- "Can I see the chords for the next verse?" Respond through private stage confidence, not the livestream.
- "We changed the song key to D." Update musician chord chart as a rehearsal suggestion, but do not transpose existing copyrighted audio, generate unauthorized lyrics, or send unsanctioned BandMates changes.

Official references:
- https://support.renewedvision.com/hc/en-us/articles/360062444614-Converting-a-Planning-Center-Song-Sequence-Into-a-ProPresenter-Arrangement
- https://support.renewedvision.com/hc/en-us/articles/360041347594-Using-Bibles-in-ProPresenter
- https://support.renewedvision.com/hc/en-us/articles/360041814913-Installing-Bibles-in-ProPresenter
- https://support.renewedvision.com/hc/en-us/articles/360041815033-SongSelect-and-ProPresenter
