# RDC and DC Chat Continuity: Independent Review Receipt

TOC Ministries | 2026-11-17 CST

**Scope:** New source-only, synthetic ChatGPT-to-ChatGPT coordination and session interruption defenses, built on the existing RDC `feat/rdc-chat-interconnect-20261117` branch. This is ready for independent source review, not accepted for live chat enrollment or Site deployment.

## User requirement and acceptance target

ChatGPT conversation A must communicate with conversations B and C directly in the authorized ChatGPT browser/app sessions using the same skill through either RDC or Desktop Commander (DC). One chat must not stop, interrupt or permanently strand another chat merely because a message arrives during an active task. Compatible provider adapters for Claude, Grok and BandMates remain planned.

## Built in this scoped follow-up

- `rdc/chat_rooms.py`: bounded 2/3-participant room fanout, stable room ID, separate recipient deliveries, correlation/causation replies, per-recipient immutable receipts, bounded hop count, no automatic browser writes.
- `rdc/chatctl.py`: `room-id` and `room-send` in the original isolated, explicitly synthetic terminal CLI; each separate invocation uses the same Atlas Bus v1 fixture SQLite DB.
- `rdc/chat_continuity.py`: recipient-owned simulated presence, stale/busy/interrupted/unconfirmed states, verified re-enrollment epoch and atomic single-flight direct delivery reservation. This is an in-memory prototype, not cross-host authentication or a production distributed lock.
- `rdc/chat_surface.py`: `deliver_peer` opts in to an authorized direct composer only after continuity reservation. DEFERRED leaves the browser untouched; lost confirmation becomes OUTCOME_UNKNOWN and suspends follow-up pushes. Success marks the recipient busy until the recipient signals readiness again.
- `skills/rdc-communications`: one skill for RDC and DC, room-based messaging, pull-only default, no direct push into a working chat, no chat stop/cancel/refresh/takeover, and browser/host permission boundaries. Same source can be packaged into the existing private ChatGPT RDC plugin without changing App bindings.
- `docs/superpowers/specs/2026-11-17-rdc-dc-chat-continuity-addendum.md` and `docs/superpowers/plans/2026-11-17-rdc-dc-chat-continuity-plan.md` record the design, tests and release boundaries.

## Fresh verification on exact local source before publication

- `python -m unittest discover -s tests` with the existing separate Atlas Bus injected by `RDC_ATLAS_BUS_TEST_ROOT`: **419 tests, zero failures, 26 environment skips**, 138.790 seconds. Evidence: `~/RDC-Development/checkpoints/rdc-chat-cross-tool-20261117/rdc-dc-confirmation-FULL-20261117.log`. Pre-existing temporary SQLite ResourceWarnings and simulated relay-interruption messages appeared but did not fail the suite.
- Seven new/source communication suites rerun: **47 tests, zero failures**. Evidence: `rdc-dc-confirmation-focused-20261117.log`.
- Node cloud gateway: **45 tests, zero failures**. Evidence: `rdc-dc-confirmation-GATEWAY-20261117.log`.
- **Real RDC+DC terminal transport:** RDC `rdc_job_run` emitted room A -> B/C, Desktop Commander `start_process` consumed messages and responded B -> A/C, RDC consumed replies and responded C -> A/B. Six distinct directed deliveries shared the same room ID and retained original causation links in one isolated SQLite Bus fixture. Evidence: `~/RDC-Development/checkpoints/rdc-chat-cross-tool-20261117/rdc-dc-cross-tool-3way-verification-20261117.json`. All ChatGPT session names were synthetic fixtures; no actual consumer ChatGPT tabs received messages.
- Synthetic continuity RED→GREEN tests cover unverified/busy/stale peers, owner-spoofed presence, uncertain delivery, interrupted connection without resume, stale epoch, single-flight post gating, and 40 concurrent reservation attempts admitting exactly one peer push.

## Limits and blockers

**Actual in-model ChatGPT messages remain UNVERIFIED.** No authenticated ChatGPT host session enrollment or approved writable/observable peer-chat interface was used. A browser tab, a separately authenticated developer API session, a CLI fixture and a bus receipt cannot be claimed as a ChatGPT conversation receiving a message. Real host permission and task-continuity test required.

Atlas Bus synthetic core denies cross-project routes by default; production session identity, cross-project ACL and BandMates adapters require their own separate owner review. Existing direct chat in-memory receipts and continuity state do not survive process restart, so they cannot yet guarantee crash-safe non-replay across multiple hosts. Multi-recipient broadcast is recipient-by-recipient, not atomic. Published skill instructions describe these as pending live requirements.

**Production restrictions:** owner-private RDC Site v16 unchanged. v17 activation remains held. Do not merge into main, deploy, restart production worker, access hidden browser conversations, or modify BandMates on this scoped evidence alone.

**Decision request:** Review the exact source commit and evidence independently. Approve or request rework of the local software scope only. Actual live ChatGPT↔ChatGPT operation and whole RDC completion remain OPEN.
