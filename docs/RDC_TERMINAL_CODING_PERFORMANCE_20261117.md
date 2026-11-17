# RDC Performance: Terminal, Coding and Cloud Gateway Qualification
November 17, 2026 | Source-only candidate | Independent release review required

## Goal and baseline
User requirement: RDC must outperform Desktop Commander (DC), not merely match, on startup, terminal, coding, file workflows, response time, accuracy, reliability and concurrency. Never report universal superiority from one local or synthetic result.

Historical matched 30/30 ChatGPT terminal echo baseline in the installed RDC coding skill: RDC v16 p50 **3,178 ms**, DC p50 **1,820 ms**. Both 30/30 correct. This remains a performance GAP, not an accepted win.

Additional actual RDC ChatGPT terminal probes in this build conversation:
- Trivial printf worker interval ~47 ms, ChatGPT-to-RDC tool call 6,109 ms.
- Deliberate exit-23 command worker interval ~4 ms, ChatGPT tool call 2,402 ms, exact stderr retained. Subsequent status/output readback confirmed exit 23. Deliberate duplicate with the same worker idempotency key returned `reused:true` and the exact original job ID.
The device and cloud/host roundtrip are distinct measurement planes. Existing private Site v16 and installed worker 0.1.0a8 remain active.

## Implemented in isolated performance branch
1. **Read-only cloud status:** `rdc_connection_status` now avoids global D1 maintenance UPDATE/DELETE, yet uses an expiry-aware count for queued/claimed operations. Normal dispatch and device polling still run cleanup. Regression tests confirm status cannot mutate the operation journal and legacy cleanup still occurs.
2. **Gateway timing diagnostics:** `rdc_recent_operation_metrics` (new owner-authenticated, read-only, bounded up to 50 completed calls) returns tool names and three safe phase durations: queue wait, claimed-to-result, and total gateway service. It never exposes request arguments, result bodies, tokens, principals or operation IDs. This equips future live RDC performance investigations to distinguish D1 pickup from local work.
3. **Coding source context:** `rdc_code_context` now resolves relative `file_paths` inside its selected project, rechecks the project boundary at read time, and defaults to a fast source search that skips `.git`, `node_modules`, `.venv`, `__pycache__`, `.next`, `dist`, `build`, and `target`. The explicit `search_mode:"all"` restores generated/dependency search. Ordinary `rdc_file_search` behavior remains unchanged.
4. **Bounded coding edit batches:** `rdc_code_edit_many` accepts 1 to 10 SHA-256-versioned exact edits in one selected project in one gateway mutation. It inherits owner review, pause and cloud idempotency guards. Every target is validated before edits; each edit returns its own outcome and partial completion is disclosed without replay or an all-or-nothing claim.
5. **Race-condition fix:** A red test proved that replacing a file with a symlink after batch admission could redirect an edit into a sibling project in full-host mode when a matching SHA was present. The fix rechecks `scoped_root` inside `Files.edit` against the actual resolved target. The post-fix regression rejects the cross-project edit; ordinary `rdc_file_edit` callers retain their original signature behavior.

## Actual local benchmarks, 30 counted runs per condition
The following trials executed the real local RDC Python Engine through the connected RDC ChatGPT terminal tool, in isolated synthetic temporary projects. **They exclude cloud and ChatGPT transport, and they do not establish superiority over DC.**

| Workload | Baseline | Optimized | p50 speedup | Accuracy |
|---|---:|---:|---:|---|
| Literal search of 660 files vs source-only search of 10 files | 110.775 ms | 2.470 ms | 44.85x | 30/30 each |
| Six independent surgical file edits vs one scoped batch | 4.365 ms | 3.453 ms | 1.26x | 30/30 each |

Source search p95: full 149.288 ms, source mode 2.687 ms. Batched edit p95: six individual calls 5.001 ms, one batch 4.213 ms. Source search scans different scopes by design; the synthetic benchmark places its only matching symbol in the included source directory to keep returned answers identical. See `test-results/rdc-coding-source-search-benchmark-20261117.json` and `test-results/rdc-coding-batch-edit-final-20261117.json`.

## Verification and safety evidence
- Complete local RDC Python suite: **387 tests, 26 skipped, zero failures**, exit code 0, about 129.4 seconds. Ran via connected RDC ChatGPT tool. Log: `test-results/rdc-performance-final-worker-20261117.log`.
- Gateway Node suite after final asset catalog synchronization: **51 tests, zero failures**, exit code 0, through connected RDC. Catalog contains 64 tools. Log: `test-results/rdc-performance-final-gateway-suite-20261117.log`.
- Targeted coding and source scope tests: 16/16 pass before the additional adversarial race test, which independently passed after the fix. The complete worker suite above includes the race test.
- Existing startup/browser candidate incorporated from base commit `06314011805b42b71bfe4b84be435927a2f98799`: one-call browser creation+navigate+observe and one fewer D1 count on ordinary dispatch. Its original local suite and Chromium smoke test passed; the active private Site still lacks those new routes.
- No live Site deployment, worker restart, D1 migration, credential use, browser takeover, chat-session coordination change, or BandMates change occurred.

## Mandatory release and superiority gate
1. Secure independent review and rollback-compatible inactive Site candidate while production v16 remains untouched. The earlier v17 rollback concern remains a separate held gate.
2. Build and compile the exact candidate, qualify on macOS/Linux/Windows where possible, and verify source manifest/tree hashes.
3. Deploy only after authorization and readback of the exact installed gateway and worker versions.
4. Run balanced, matched, real ChatGPT RDC vs DC comparisons, at least 30 non-warmup samples per workload: cold connection/init, short and long terminal jobs, failure/recovery, file search/read, code-context discovery, multi-edit changes, browser startup/actions, and isolated concurrency.
5. Report p50/p95/p99, correctness/failure rates, response truncation, queue wait, completion/upload, startup time, and resource consumption. **Pass requires RDC faster at every named comparable scenario without inferior accuracy or reliability.** Any failed dimension remains OPEN, even if the average improves.

A reduction in host tool calls does not by itself prove RDC p50 is faster than DC. Do not publish an outperformance claim before the final live comparison.
