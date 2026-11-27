# Preview v9 repair and publication record — November 23, 2026

The owner's current request authorizes these preview bug repairs and their installation, GitHub publication and existing ChatGPT plugin update. This is a narrow repair of the existing worker/gateway, independent of the unreleased V2 transport/inline-result migration. The V2 speed gates remain OPEN.

## Repaired behavior

- Recover one exact source when valid host input arrives after an unbound initial result. No global or last-used source is selected.
- Wait for a confirmed source before automatic floating. Pending, unavailable and ended tasks cannot open an empty floating view. Host support and returned mode remain authoritative.
- Schedule successful single-flight frame reads with a 250–1500 ms idle wait based on observed request time, retaining pending/failure recovery and slow-read backpressure.
- Serve the compact preview bundle and original compact RDC icon from the deployed gateway. Both preview tool metadata pointers advertise v9; resource aliases v1–v8 remain readable.
- Explain exact native-window binding for an external signed-in Chrome window in both source skills and the existing App-backed plugin.

## Installed and published identities

| Surface | Verified result |
| --- | --- |
| Local worker | Preview source/bundle installed into existing worker 0.1.0a8; three active browser sessions preserved; no daemon restart |
| Live local MCP resource | 741,250 bytes; SHA-256 `eb352a2f06b79cacb8a66770adb216a88b9f92b108f9a4a1f597357687a28aa5`; v9 marker present through retained v8 alias |
| Gateway | Private RDC Site version **17**, preview-only source commit `d232317dfe316b20bb29e89b39a322daec92522b`; deployment succeeded |
| Site artifact | SHA-256 `7000a7d9ba344079237083272a1117ad5f6e87cd94d45359e60ed433e7160bec`; actual v16 source plus preview assets/resource-alias changes only |
| ChatGPT App-backed plugin | **1.0.35**, release `pluginrel_6b0506de52ec8191ae2c8396c7f4538f`; same private plugin, App reference and audience |
| Local plugin installation | Cache advanced to 1.0.35; both manifests, App binding and all three changed guidance files match the published package |
| GitHub | Existing draft PR #21, `perf/rdc2-owner-speed-20261121`; this repair and the two previously unpublished polling/upload-recovery commits are published together; no merge |

Preview HTML decreased from 2,021,512 to 741,250 bytes (63.3%). Icon data URI decreased from 1,327,346 to 45,546 bytes (96.6%). These are payload measurements, not live terminal speed claims. The running worker retains its already-imported v8 resource identifier while serving the new bundle; new worker processes advertise v9. Active browser sessions were not interrupted to change that identifier.

## Verification and limits

The cumulative ledger charges **82/100** slots, including every failed/repeated trial and four reserved capture requests that never dispatched. Actual runtime executions were 78. The 51 successful automated source/UI/resource checks include final green reruns; six deliberate red assertions reproduced the new defects before correction. No unbounded suite or inherited GitHub CI was run. Compilation, asset builds, source review and hash comparison are static checks, not runtime cases. See the adjacent JSON ledger for individual runs.

Five headless Chromium iframe tests exercised the bundled SDK: exact source isolation, floating open/reopen, single-flight/wrong-source handling and refusal of unsupported host floating. These fixture passes do not establish actual ChatGPT floating placement.

The deployed ChatGPT connector reached the original worker. The exact reported Chrome window bound successfully, and its original pending preview operation recovered successfully. Capture returned `window_capture_unavailable`; the window was not marked onscreen. The native helper reported both Screen Recording and Accessibility permission granted.

A separate temporary, registered macOS test app proved the existing native helper captures its visible window correctly (840 × 464 JPEG; SHA-256 `114371bca42537100550dc9cd18a788a4fc4cd2bc100360ceebdccb158154e41`). The same window failed capture after minimization. Two earlier unbundled fixture attempts were not enumerated; their capture requests never dispatched, and all reserved slots remain charged. The fixture exited, and the exact Chrome test binding was forgotten without closing Chrome.

Minimized-window capture remains unavailable in this tested configuration. Restore the intended source window before retrying its preview. No desktop fallback, source substitution or permission workaround was added. No new live ChatGPT floating-placement proof or 30-sample hosted speed benchmark was obtained; broader speed/cross-platform gates remain OPEN.

## Rollback and release boundaries

Pre-install preview files and their receipt were retained locally. The prior Site v16 source/archive and existing release history remain available. The plugin update preserves all prior files, including independent mobile support assets. No worker state, pairing, permissions, database migration or active browser lifetime changed. Private publication and `[skip ci]` do not certify full production/platform acceptance. Keep PR #21 draft; do not activate the V2 migration from these preview results.
