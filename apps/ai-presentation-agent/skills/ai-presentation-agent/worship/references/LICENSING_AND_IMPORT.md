# Licensing, Bible Text, SongSelect, Planning Center and Media Import

## Purpose
Teach the AI Presentation Agent and its builder to distinguish authorized source content from materials that are only known by title or reference. A church presentation can be built using original materials without any ProPresenter license or third-party subscription.

## NKJV and Scripture
- Use NKJV as the preferred Bible translation for this ministry's presentation training.
- A Bible citation such as "Psalm 100:1-2 (NKJV)" may be displayed without embedding full text.
- Full NKJV text requires a valid owner-supplied source and permissions for the intended use. An account or license in another application does not automatically grant embedding/distribution rights in an independent app.
- Store reference, range, translation, content source, authorization status and revision separately. Invalid references or missing text generate an editorial review task.
- No automatic substitution with another translation, no invented verse body and no scraping copyrighted Bible texts into an app library.

## Worship lyrics and CCLI
ProPresenter supports SongSelect with eligible CCLI and advanced SongSelect accounts. CCLI licenses and streaming permission can differ by use, territory, work and service. For each song, record title, author/composer, rights holder where known, public display authorization, livestream rights if applicable, required copyright notice and reporting responsibilities. Verify terms rather than assuming every popular worship song can be freely copied into downloadable software.

Teach three routes: original owner-written lyrics, properly licensed owner-provided lyric source, and metadata-only placeholder that requires text clearance. With unknown rights, display song title or request the church's authorized text and refrain from projecting a fabricated lyric.

A church may need to show a copyright credit and its CCLI license number on projected lyrics where applicable. Official guidance: https://support.renewedvision.com/hc/en-us/articles/53940538326419-How-to-Display-Copyright-Information-in-ProPresenter

## Planning Center, SongSelect and optional provider integrations
- Planning Center service-plan imports may include scheduled songs, sequences, people, notes and timing. The builder must verify a documented authorized API, per-organization permission, OAuth scopes, offline cache and data retention before importing.
- SongSelect content requires eligible owner account access and terms-specific use. Store minimal required metadata; private keys and credentials live in an OS-secure or provider-authorized store, never church presentation JSON.
- ProPresenter media, templates or Bible modules are licensed for that ecosystem. Do not copy them into the independent app, reverse engineer protected binary resources or imply cross-license reuse.
- When a provider is disconnected, preserve local original/authorized service materials and clearly label missing data. The core church slideshow still works offline.

## Video, images, audio and livestream clips
Before adding a background video, song backing track, sermon clip, logo, external photograph, illustration or stock media, record owner authorization and permitted venue/stream usage. Streaming or recording may introduce rights concerns distinct from in-room projection. Respect music and camera release requirements when applicable.

## Data security
Private pastoral notes, worship-team contact details, prayer requests, attendee lists, stream destinations and platform OAuth tokens must remain outside public HTML, broadcast overlays, livestream comments and shared logs. Stage confidence requires a separate protected view. A livestream comments integration requires its own authorization and moderation gate.

Primary sources:
- https://support.renewedvision.com/hc/en-us/articles/360041814913-Installing-Bibles-in-ProPresenter
- https://support.renewedvision.com/hc/en-us/articles/33122394289043-Bible-Translations-Available-for-ProPresenter
- https://support.renewedvision.com/hc/en-us/articles/360041815033-SongSelect-and-ProPresenter
- https://support.renewedvision.com/hc/en-us/articles/360062444614-Converting-a-Planning-Center-Song-Sequence-Into-a-ProPresenter-Arrangement
- https://support.renewedvision.com/hc/en-us/articles/53940538326419-How-to-Display-Copyright-Information-in-ProPresenter
