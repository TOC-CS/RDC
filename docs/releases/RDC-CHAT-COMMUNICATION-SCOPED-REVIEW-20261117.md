# RDC Cross-Session Communication: Scoped Source Review

**TOC Ministries | November 17, 2026 CST**
**Review state:** READY FOR INDEPENDENT ATLAS SOURCE REVIEW, subject to complete final-suite evidence and precise commit hash.
**Activation state:** HELD. This is a local source and synthetic session integration checkpoint, not production ChatGPT, Claude, Grok or BandMates delivery.

## User requirement

Build RDC communication skills that can connect ChatGPT, Claude, Grok, other supported AI models and chat sessions in the actual browser/app, open new conversations, communicate two ways between distinct sessions, and offer the same communication through a durable message bus and terminal. Add BandMates AI Studio as a compatible endpoint without interrupting its music, mixer or MIDI workflows.

## Architecture selected through Superpowers brainstorming

Three alternatives were considered: browser-only UI automation (fragile and subject to host permissions), a new independent message server (duplicates Atlas), and the existing Atlas Bus plus RDC adapter contracts. The third approach was selected for this isolated scope. The design and test-driven plan are at `docs/superpowers/specs/2026-11-17-rdc-ai-chat-interconnect-design.md` and `docs/superpowers/plans/2026-11-17-rdc-ai-chat-interconnect.md`.

## Implemented, testable software

- `rdc/chat_interconnect.py`: typed same-project `ChatClient` bus adapter with source-bound synthetic identity, deterministic UUIDv4-shaped message IDs, idempotent send, correlation/causation replies, bounded text, wrong-recipient denial, explicit claim/fetch/ack/action confirmation and message status visibility.
- `rdc/chatctl.py`: terminal `python -m rdc.chatctl` with explicit `--synthetic-only`, Atlas source injection, private sandbox marker, reusable SQLite state across independent subprocesses and commands `init`, `sessions`, `send`, `claim`, `fetch`, `ack`, `reply`, `confirm`, `status`.
- `rdc/chat_surface.py`: capability-gated direct-chat host `ChatSurfaceGateway` contract to open new verified sessions, attach user-approved conversations, submit once, observe bounded replies and reconcile uncertain delivery. A stable new-chat request ID prevents accidental duplicates after a timeout. All receipts currently live in memory, so host/process restarts require future durable receipts before real usage.
- `skills/rdc-communications/SKILL.md` and `references/integration.md`: reusable instructions for all three routes and ChatGPT/Claude/Grok/API/desktop/BandMates constraints; parent `skills/rdc/SKILL.md` now links to this skill. No new provider accounts, credentials or real chat login were touched.
- `docs/BANDMATES-RDC-CHAT-INTEGRATION-20261117.md`: RDC-side integration handoff aligned to the existing independently owned BandMates `RDCMusicianHandoffDrafts` synthetic transport, `MusicianVoiceMailbox` and direct Studio command-bus constraints. No BandMates files changed.

## Verified results

- TDD RED evidence recorded for absent `rdc.chat_interconnect`, `rdc.chatctl`, `rdc.chat_surface`, new-chat no-replay, missing bidirectional host capabilities, missing skills, parent-skill discoverability, and the symlinked sandbox DB redirect. Each behavior subsequently passed focused tests.
- Full focused new communication tests: **26 of 26 passed**, zero failures against the actual Atlas Bus v1 synthetic core from its separately owned, read-only source. Final checks include a missing two-way host capability refusal and symlinked sandbox database denial. Evidence: `chat-focused-final-symlink-20261117.log`.
- Earlier complete Python source checkpoint: **395 tests, zero failures, 26 expected environment skips** before the final parent-skill discoverability test. Evidence: `chat-full-python-20261117.log`.
- Final full Python regression after the complete communication and security fixes: **398 tests run, zero failures, 26 expected skips**, 124.341 seconds. Evidence: `chat-full-python-SOURCE-FINAL-20261117.log`. The earlier whole-suite run is historical evidence only.
- Cloud gateway Node tests: **45 of 45 passed**, zero failures, on the unchanged local cloud gateway source. Evidence: `chat-gateway-45-20261117.log`.
- **Seven direct, authorized, existing live RDC v16 terminal jobs** independently executed the sandbox CLI `init → send → claim → fetch → ack → reply → claim`, verifying exact exit 0, independent process identities, persisted Atlas D1-like SQLite sandbox, message source and reply causation. The BandMates endpoint was a fixture; no live Studio or provider chat action. Exact worker job IDs and output receipts were inspected within the executing chat.
- No real model inference, Keychain password read, account charge, Browser UI click, user desktop input, Site migration, live worker restart, hidden chat access, BandMates audio operation or GitHub source publication.

## Security and compatibility gaps

**Actual browser/app chat is OPEN.** The current browser integration is read-only in regular Chat and has specifically blocked ChatGPT settings/Sites origins. RDC must use only permitted, genuinely connected interactive host/browser or documented API adapters; it cannot turn browser history or a guessed ID into a writable chat surface. OpenAI API conversations are separate from consumer ChatGPT threads; Claude Messages API is stateless; xAI API requests have separate account/cost gates.

**Real enrollment is OPEN.** Atlas core only authorizes synthetic fixture sessions. Its actual cross-project path remains `CROSS_PROJECT_DENIED`, correctly preventing BandMates-to-RDC delivery. A production adapter needs authenticated per-session identity, approved per-project ACL, durable host operation receipts, operator permissions, crash-safe no-replay and actual destination readback.

**No performance superiority claim.** The new communication prototype has no matched live browser/API latency measurements, provider throughput figures, cross-host tests or production multi-agent proof.

## Next staged acceptance

1. Atlas independently review exact committed source/plan/tests, require one reviewer decision with original provenance, and keep whole release OPEN.
2. Atlas Bus owner separately approve real enrollment, scoped cross-project ACL and persistent local transport; do not modify their uncommitted core from RDC.
3. BandMates owner separately review its existing chat handoff contract and authorize a real status-only pilot, strictly outside live audio and MIDI callback.
4. Provider/host owners implement one authenticated direct-chat UI or free-approved developer API adapter at a time with real new-session, submit, reply and readback tests. The first real ChatGPT browser test requires a permitted interactive host, not a blocked browser tab.
5. Add production-persistent no-replay/open receipts, bounded receipt/queue transport, offline and reconnect tests, host permissions/consent, and portability validation on Windows/Linux as applicable.
6. Preserve owner-private existing RDC Site v16. Later v17 activation continues on HOLD until independently approved compatible inactive rollback version and release gates exist. Updating a skill alone cannot activate a missing tool.

**Requested Atlas decision:** ACCEPT SOURCE SCOPE or REWORK with exact failing checks, without approving real enrollment, deployment, AI autonomous action or closing the full RDC project.
