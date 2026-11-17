# RDC speed, functionality and startup test evidence
Date: 2026-11-17. All calls performed through the connected RDC ChatGPT app on the authorized iMac.
Scope: Browser startup and cloud dispatch. No chat-to-chat communications work is included.
Release scope: PRIVATE Site v16 and installed worker 0.1.0a8 were NOT changed.

## Current live ChatGPT RDC workflow, one measured sequence
Fresh headless Chromium session, standalone HTML data page, no credentials.
- `rdc_browser_start`: 3,590 ms, returned dedicated session ID
- `rdc_browser_navigate`: 3,014 ms, success
- `rdc_browser_observe`: 2,162 ms, returned title and button control
- **Startup/navigation/inspect sequence total: 8,766 ms in 3 cloud calls**
- `rdc_browser_click`: 2,528 ms, one action
- `rdc_browser_observe`: 2,377 ms, verified "Clicked OK"
- **Click and verify total: 4,905 ms in 2 cloud calls**
- `rdc_browser_screenshot`: 1,969 ms, JPEG capture acknowledged
- `rdc_browser_close`: 2,598 ms, closed true
All outcomes were observed; no session left open. Times are single samples and exclude model deliberation.

## New isolated source candidate
Worktree: `~/RDC-Development/workspace/rdc-performance-startup-20261117`
- Cloud dispatch: uses one online-only heartbeat query rather than the full status helper. A red-green gateway regression test verifies one fewer standalone pending-operation COUNT per new dispatch. The public status tool retains the count.
- `rdc_browser_start_navigate_observe`: combines three initial actions in one cloud mutation. Its source code validates URL before launch; on post-start errors returns a recoverable session ID and never replays a navigation.
- Previously checked-in `rdc_browser_click_observe` and `rdc_browser_fill_observe` combine post-action inspection into the same mutation.

Real Playwright Chromium smoke (source candidate executed by a connected RDC ChatGPT terminal job):
- Startup+navigation+fresh observation: **294.10 ms local execution**
- Click+fresh observation: **81.17 ms local execution**
- Correct title, accessible button handle, changed page text, screenshot and cleanup verified.
These local source timings DO NOT represent the undeployed ChatGPT gateway latency. They cannot be subtracted from live client timings to claim a savings.

## Tests and gates
- Full worker Python suite: **377 tests, 26 skipped, 0 failures**, exit 0, 129.448 seconds, through RDC.
- Full gateway Node test suite: **48 passed, 0 failures**, exit 0, through RDC.
- Focused real WebDriver fixture: 4 new cases, success; invalid URL; navigational error; observation error.
- Source and changed-file release checks must remain scoped to this performance worktree.
- The live ChatGPT browser call path and 30+ paired DC speed comparison remain UNVERIFIED for the new candidate because it has not been installed.
- Do not deploy to private Site v16 or restart the worker until an independently accepted rollback plan and reviewer authorization are in place. Site v17 rollback compatibility remains held.

## Next acceptance measurements
After reviewed activation, run a full 30-pair alternating-order ChatGPT test of RDC and DC for startup, terminal, source context, file read and browser controls, with p50/p95/p99, correctness counts and crash/recovery metrics. Target lower than DC for each comparable workflow, without weakening owner approval, result durability or no-replay behavior.

Current interpretation: client cloud interactions and worker execution have materially different latency. The tested source candidate removes one D1 query and cuts first-browser workflow host tool count from 3 to 1. Production gain remains pending.
