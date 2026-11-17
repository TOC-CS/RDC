# RDC v17 rollback and result-boundary independent review
Date: 2026-11-16 (America/Chicago)
Status: SOURCE REVIEW PASSED LOCALLY; LIVE ACTIVATION AND WHOLE RDC RELEASE ON HOLD.

## Scope and ownership
- Continue existing draft PR #1 in TOC-CS/RDC, repair/preview-v8-host. Do not duplicate the PR.
- Keep existing owner-private Site project appgprj_6af932b7b1608191823588d50d059ac2, v16 production and v15 retained pre-inline rollback unchanged.
- Keep private plugin/App identity, worker, permissions, Site D1/R2 data, and BandMates unchanged.
- Original live v16 is not a safe rollback target once inline-only v17 results exist.

## Exact implementation under local test
- Implementation commit: 22290da2b0f4e8f1e202d9b0ae907ee8728702c8.
- Implementation Git tree: ca3cf16f2440545d0c101debab0f69554ff936ba.
- In the existing gateway module, createRollbackCompatibleGateway forces maxInlineResultBytes=0 after all caller limits, while retaining the inline-aware reader, owner checks, TTL sweeps, existing R2 reads and no-replay semantics.
- Old v16 reader and cleanup confirmed from git source 3001050: it checks result_key alone, reports result_expired for inline-only rows and excludes them from cleanup. An additive migration alone is insufficient.
- Four exact UTF-8 JSON body regressions: 8192 ASCII and multibyte inline, 8193 ASCII and multibyte R2 fallback. Tests cover result_size, readback, expiry, owner isolation and idempotency.
- Worker-forged structuredContent._rdc_gateway_operation_id and _meta['rdc/operation_id'] are overridden by the true gateway-owned operation ID on first recovery and identical replay; serialized worker result is preserved for hash/idempotency validation.
- Same D1/R2 fixture tests v17 inline write through the compatible reader, TTL and retained terminal identity, rejection for wrong owner, R2-only writes after rollback, legacy R2 readback, and no worker redispatch.

## Local verification
- Gateway Node tests: 41 passed, 0 failed (cloud-gateway/tests/gateway.test.mjs).
- Full Python worker unittest discovery: 364 passed, 0 failed. Isolated temp workspace; no production worker interactions.
- Focused worker unittest: 112 passed, 0 failed.
- Gateway production build: passed.
- Gateway ESLint: 0 errors, 1 existing image-optimization warning in app/page.tsx.
- git diff --check: passed; working implementation branch was clean before this report.
- Test logs: /Users/brandondawson/RDC-Development/checkpoints/rdc-v17-gateway-review-20261116/.

## Built rollback candidate (OFFLINE ONLY)
- Stage: /Users/brandondawson/RDC-Development/checkpoints/rdc-v17-rollback-candidate-20261116/.
- Only staged source change relative to the verified gateway source: lib/rdc-gateway.ts imports and invokes createRollbackCompatibleGateway instead of createGateway. No separate gateway service or route.
- Staged production build: passed. Compiled minified gateway chunk contains a single maxInlineResultBytes:0 factory override; original v17 bundle contains none.
- Compiled rollback chunk SHA-256: 96d0d5aeff66b299b647359c220260da6f80fbfe0f2eea4684fd8d43cc32cc8b.
- Both compiled configurations have identical D1 DB and R2 BUCKET bindings. Both additive migration files are unchanged.
- Offline source and build tar.gz: rollback-compatible-site-source-and-build.tar.gz.
- Archive SHA-256: 457a9b91a4dd15804e35fbf8d76c4929f80508ae9f11519aedc8514f2700f016.
- Archive excludes node_modules, environment credentials, local state and Git internals.
- No live Site migration, inactive Sites version save, worker restart, cloud device mutation or production deployment occurred.

## Outstanding review and release gates
1. Save and read back the exact rollback-compatible artifact as a protected, INACTIVE version of the EXISTING owner-private Site before allowing any v17 inline writes. This requires Site version-management access; the present session has no Site-specific tool exposed. If a saved inactive version cannot be verified, keep v17 activation blocked.
2. Publish the verified source to the EXISTING draft PR and obtain GitHub Actions macOS, Linux and Windows results on the precise published commit. This local document does not count as hosted CI.
3. Obtain Atlas scoped acceptance of the rollback plan, authority override, byte-boundary evidence, Site version protection and rollback selection rule. The original v16 binary must never be selected as a post-inline rollback.
4. After all gates, any later live database migration and Site activation require explicit authorized release steps and independent readback. This review authorizes none.
5. Whole RDC completion also requires outstanding native host/device, preview and integration acceptance; leave project open.

## Follow-on payload optimization verified in compiled local runtime
- Source change commit: 1643fbdee58e692338a350fa391ef965263c68f9; exact Git tree c37961e4e9c6e7a9a8017d2534cb2e883a129c15.
- Preserve the original 1254x1254 PNG (995,493 bytes) for the Site and native UI. Add a checked-in derived 192x192 PNG (34,141 bytes; SHA-256 9091e1f6d0fd0ab8854af3d39383ca1767811e4919b59b37fd48ec24df5066ad) solely for inlined MCP icon metadata.
- Source generation uses this prebuilt PNG on every OS, verifies PNG dimensions and <=60,000-byte bound, and does not require macOS tooling in GitHub CI. The MCP Implementation icon now carries sizes:["192x192"] per the public 2026-07-28 MCP specification.
- Generator readback retained exact catalog SHA-256 6df1402bef2da86485ef4fee6c079db91d3c75bac2b9318061db8fcc1e08f501 and preview HTML SHA-256 21cdb99273b873f622375cd3d8cfae350818f2c5a5881dae865ae9ecdf032551. No tool or preview content change.
- Red-green test: test failed because thumbnail was missing before implementation; now the complete gateway suite has 42/42 passing. Production v17 build passes; ESLint 0 errors, 1 unrelated existing image warning.
- A real isolated local HTTP test ran the original compiled rollback and the rebuilt rollback using loopback-only local D1/R2 with dummy credentials, then terminated each runtime. MCP initialize payload decreased from 1,328,374 to 46,594 bytes, a reduction of 1,281,780 bytes (96.5%). Original and new implementations both rejected unauthenticated status, unauthenticated tool calls, and incorrect device credentials with HTTP 401. This measures wire payload reduction, not real cloud latency.
- Superseding staged rollback artifact (unpublished): /Users/brandondawson/RDC-Development/checkpoints/rdc-v17-rollback-iconopt-20261116/rollback-compatible-site-source-and-build.tar.gz. SHA-256 476048e22b067c049f3f5775134c3ff02e3c60a53b38c5125a17fc0a877a5413. Compiled rollback gateway chunk SHA-256 39b3df09188f3e0d08393af5a8cb2207e7798adb14c5246d37e47afadf029a1d. Compiled forced R2-only writer and D1/R2 binding parity verified. Previous unoptimized stage remains as immutable baseline evidence.
- Full Python worker tests previously passed 364/364 and worker code was unchanged by the icon optimization. No fresh hosted CI or live deployment has occurred.
- This reduces MCP metadata size but cannot force the ChatGPT/Codex host to show a branded outer app icon. UI presentation is a separate host integration/acceptance gate.
- Official MCP icon guidance: https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/basic/index.mdx

## Final local-first preview resource optimization and protected rollback candidate
- Implementation commit: 5c0242b166398eedc0506fcb0a6b383d4e085d0f; Git tree ba798fce8513d24b152c0d498759acc905fda129.
- The 20x20 preview logo previously embedded the 1254x1254 original PNG (1,327,346-byte base64 URI). A checked-in local RDC asset `rdc/assets/rdc-icon-192.png` now serves as the shared branded 192x192 thumbnail for both the independent `rdc/embedded` build and the cloud gateway metadata. The full original file for native and App/listing branding remains unchanged.
- Rebuilding the local MCP Apps preview produced 739,712 bytes instead of 2,021,512 bytes. An exact byte comparison proves the sole rendered resource change was one replacement of the original base64 logo URI; all other HTML/CSS/JS bytes are identical. The synchronized cloud tool catalog remained 58 tools, with unchanged SHA-256 6df1402bef2da86485ef4fee6c079db91d3c75bac2b9318061db8fcc1e08f501.
- New Node regression and independent Python resource-size assertion passed. After the separate historical v16 executable regression, full gateway tests: 44 passed, zero failures; production v17 build passed, ESLint zero errors, one pre-existing image warning. This code includes the earlier v17 rollback, 8192/8193-byte UTF-8 and forged ID regressions.
- Both versions were served through isolated compiled local HTTP gateways with synthetic credentials and local D1/R2. Actual `resources/read` responses fell from 2,060,992 to 779,192 bytes (1,281,800 bytes smaller). `initialize` stayed at 46,594 bytes with compact icon. Both versions preserved 401 on unauthenticated status, unauthenticated tool and wrong-device-key requests. This establishes payload reduction, not postdeployment cloud latency.
- Final source-and-build rollback candidate (OFFLINE/INACTIVE): `/Users/brandondawson/RDC-Development/checkpoints/rdc-v17-rollback-fullopt-20261116/rollback-compatible-site-source-and-build.tar.gz`. SHA-256 `7b720e83474e784177c03c9b024e6f32844d0c603f7e8735f655b76e5e35d3ba`; compiled gateway chunk SHA-256 `a9aa4368d72c17caf97bc8cf16548e5a0815f899bbccf5cd23b8ae6afe38e9da`. Size approximately 2.7 MB. D1=DB and R2=BUCKET parity, migration hashes, forced compatible R2-only rollback writer, and source matching were checked. Prior candidate archives are retained for audit comparison.
- Full worker `unittest discover` rerun against this source completed successfully: 364 tests, 0 failures, 128.471 seconds. Evidence: `/Users/brandondawson/RDC-Development/checkpoints/rdc-v17-gateway-review-20261116/worker-full-previewopt-unittest.log`.
- **Independent browser visual acceptance after the icon optimization:** First run of 34 Playwright fixture tests found a premature native-resize layout assertion, with 33 tests passing and one failure: the test compared panel height to host height immediately on observing a resize request, before asynchronous readback/frame display settled (277px versus 730px). The unmodified original resize test passed independently, establishing scheduling sensitivity. The test was changed to wait for a confirmed `#screen.window-sized` and poll bounded panel-vs-host fit before asserting, with no application logic or resource changes. Fresh full visual suite: **34 tests passed, 0 failed (69.934 seconds)**. Three independent reruns of the resize case also passed. Evidence: `embedded-preview-visual-verification.log` (initial red), `resize-isolated-diagnostic.log`, `resize-race-fixed-isolated.log`, `embedded-preview-visual-revalidated.log` and `resize-repeated-{1,2,3}.log` in the review checkpoint. This verifies a synthetic MCP Apps browser host, not actual Codex/ChatGPT native PiP.
- Prepared independent Atlas scoped review request in `docs/ATLAS-RDC-V17-SCOPED-REVIEW-REQUEST-20261116.md`. It is a local document for Atlas/owner review; no Atlas dot response or approval was received from this session.
- A source-only GitHub publication and protected inactive owner-private Sites version remain blocked by available authentication/site controls. No live deploy or production migration was attempted. Never select historical v16 for rollback after inline rows exist. Whole RDC completion remains open.

## Executable historical v16 compatibility regression
- Imported the byte-for-byte historical v16 gateway from existing source commit `3001050` into a **test-only fixture** `cloud-gateway/tests/fixtures/rdc-gateway-core-v16.mjs`, pinned SHA-256 `5651f14c6fc8a7308f37a5454a006ec2b0fb459aae97997554a8d296f160cd4f`. Test directly executes that old gateway against a migrated in-memory D1 database and synthetic R2, without production data.
- An exact v17 inline-only completion is read through original v16: the **real historical code** returns `result_expired` while the payload remains stored. Advancing TTL and running original v16 cleanup leaves the expired inline result untouched. Running the rollback-compatible gateway cleanup on the same fixture removes the expired payload, keeps `state=completed`, avoids a null R2 delete, and rejects a replay of the original mutation.
- The new test was run RED with the missing fixture, then GREEN after installing the hash-pinned source. **44 of 44 gateway regressions passed**, gateway production build passed, lint had zero errors (one unrelated known warning). Evidence: `gateway-historical-v16-full-tests.log`, `historical-v16-executable-RED.log`, `historical-v16-executable-GREEN.log`, `gateway-historical-v16-build.log`.
- This test-only addition and accompanying review documents do not change the compiled gateway runtime from the final rollback archive; the preserved offline rollback bundle checksum still describes the verified runtime build. Release activation remains on HOLD pending a protected inactive Site version, hosted CI on the published branch, and Atlas review.

## Live v16 read-only gateway phase diagnostic
- Recovered **12 owner-only terminal phase reports** through the existing authenticated gateway, using original matching operation identifiers from the local relay journal opened in read-only mode. Gateway queue-wait p50/p95 **311/596 ms**, claim-to-result **678/1078 ms**, total created-to-completed **982.5/1391 ms** (nearest-rank p95, n=12). No operation was replayed.
- Two fresh harmless terminal markers returned exact output and exit 0. ChatGPT-to-completion durations were 3897 and 3223 ms; gateway service times for those calls were 1145 and 955 ms, command execution 4 and 5 ms. The remainder includes host/connector transport and delivery. Do not attribute this residual to D1, R2, or queueing alone.
- Three read-only connection calls completed in 847, 1069, 887 ms. These are context-only baseline measurements.
- Numeric-only summary preserved outside the source tree at `/Users/brandondawson/RDC-Development/checkpoints/rdc-v17-gateway-review-20261116/owner-v16-last12-terminal-phase-summary.json`. Human-reviewed methods and limitations: `docs/releases/RDC-V16-OWNER-PHASE-DIAGNOSTIC-2026-11-16.md`. The live Site remains v16 and the staged v17 performance claims remain unqualified.

## Publication and additional tool limitations
- Source-only push attempted against the existing draft branch with interactive Git prompts disabled. Git reported that no password was available. No GitHub remote change occurred. At the check, draft PR #1 remote head remained 3bfd044b2c0aa5ea35709dbb83b20d1a623dc32d. The GitHub connector offers read access but no push permission. Local review commits are retained on the iMac; hosted CI for the latest local head remains outstanding.
- REA 6.9.0 static analysis was attempted against the compiled rollback gateway chunk. Its parser could not finish because the macOS xcrun Swift process-ownership helper failed to compile with the installed macOS SDK. Partial REA evidence and doctor output were retained in the review checkpoint. Do not represent REA as a passing independent check. Direct source inspection and exact compiled-bundle checks independently confirmed the force-zero inline limit and unchanged D1/R2 bindings.
- Do not change the host's global Xcode/Swift toolchain or existing REA registrations merely to clear this optional analysis failure while BandMates and other work are active.

## Reference implementation research
- Cloudflare D1 migrations: https://developers.cloudflare.com/d1/reference/migrations/
- Cloudflare R2 consistency: https://developers.cloudflare.com/r2/reference/consistency/

Review outcome: local source acceptance for the scoped regressions, pending protected inactive Site version and hosted CI. NO v17 ACTIVATION.
