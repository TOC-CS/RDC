# RDC coding, terminal, Superpowers, hosted models and multi-agent review

**Date:** November 17, 2026 CST
**Review state:** READY FOR ATLAS SCOPED SOURCE REVIEW. Competitive superiority and hosted AI swarm remain OPEN.
**Owner:** Existing RDC development session, branch repair/preview-v8-host.
**Base published source:** 0e3058292dac6555663548614276ad28dea1a2fe, Git tree 90717688950d70e578fec961e9240cbf2f33c43e.
**Safety:** Private RDC App/Site, production v16 and live worker preserved. V17 ACTIVATION ON HOLD pending a protected inactive compatible-reader rollback version, Atlas decision and independent readback.

## Owner requirement
RDC must outperform Desktop Commander (DC) for coding, terminal work, efficiency, accuracy, skill usage and multi-agent tasking. The 2x faster p50/p95 goal on matched supported tasks, 100% deterministic test correctness, safe recovery, resource efficiency and concurrent-agent isolation are acceptance gates. They are not yet satisfied.

## Methods and availability
The TOC Superpowers and brainstorming directives were read. Their approaches were actively applied: compare alternatives, write a plan, reproduce failures, test first, diagnose, measure before/after and reject regressions. Superpowers appears in ChatGPT plugin settings but exposes no callable action in this session. Actual plugin tool activation is UNAVAILABLE. REA 6.9.0 exists, but earlier macOS toolchain analysis failed; source and contract tests provide the current evidence.

## Tested results

| Measurement | Result | Scope |
|:--|:--|:--|
| Python worker tests | 370 / 370 passed | Local candidate |
| Gateway Node tests | 45 / 45 passed | Local candidate |
| Gateway build and lint | Build passed, zero errors, one existing image hint | Offline candidate |
| Synthetic coding workflow | 30 / 30 correct; p50 270.821 ms, p95 368.258 ms | Local Engine |
| Eight separate coding worker processes | 8 / 8 correct; 4.424 tasks/s, p50 1,019 ms | Deterministic processes, not AI |
| Matched RDC v16 terminal | 30 / 30 correct; p50 3,178 ms, p95 5,148.3 ms | Cloud ChatGPT tool |
| Matched Desktop Commander terminal | 30 / 30 correct; p50 1,820 ms, p95 3,642.5 ms | Same iMac and shell |
| Legacy three-call coding inspection | 30 / 30 correct; p50 8.257 ms | Local Engine |
| New one-call coding context | 30 / 30 correct; p50 8.421 ms | Local Engine |

RDC v16 is 1.746 times slower than DC at p50 and 1.413 times slower at p95 on the matched echo workload. Worker command execution median was 5 ms, so transport and connector delivery deserve investigation. This is pre-v17 evidence, and no 2x competitive gain is claimed.

## Read-only coding-context candidate
Added rdc_code_context, which combines directory listing, literal code search and up to 20 hashed reads within a selected authorized project subtree in one cloud operation. Listing is bounded to 200 entries, search to 100 hits and 1,000 scanned files, and individual file text to 16 KiB. Per-file errors remain observable. It does not promise an atomic filesystem snapshot.

Tests went RED with unknown_tool and then 4/4 GREEN after the minimum implementation, including no escape to unrelated files, safe partial read failures, bounds and read-only behavior during owner pause. A synced gateway catalog regression went RED when the tool was absent and GREEN after exactly one tool was added, bringing the catalog from 58 to 59. Original preview HTML and branding bytes remained identical.

Local median overhead was 0.164 ms greater for the combined request, but the AI-host operation count falls from three to one. That potential cloud improvement is still UNVERIFIED until deployment and measurement. An internal six-thread parallel experiment worsened local p50 to 12.556 ms, so it was reversed.

## Hosted models and credentials
Login Keychain metadata-only lookups confirmed the four owner-named service entries exist when the explicit login Keychain file is selected. The default search list returned status 44, and the separately owned BandMates-Swarm doctor reported NVIDIA, OpenRouter and Gemini unconfigured. This is a concrete Keychain search-list mismatch hypothesis, not proof of secret access or successful API authentication. We did not read key bytes, change ACL, start provider inference or trigger macOS approval prompts.

Free developer options have been publicly verified, subject to account and model qualification: OpenRouter :free variants or the openrouter/free router (capped), NVIDIA developer serverless NIM endpoints, and eligible Gemini API Free Tier. Paid model fallback and Grok inference remain disabled. Official docs:
- https://openrouter.ai/collections/free-models/
- https://build.nvidia.com/explore
- https://ai.google.dev/gemini-api/docs/pricing

The existing Swarm owner must verify an explicitly authorized login-keychain lookup and broker access before any hosted model calls. The model should receive only sanitized synthetic code, and every returned proposal requires independent tests.

## Swarm status
Separate deterministic coding worker processes were tested at 1, 2, 4 and 8 concurrent processes using independent temporary roots. They are not independently reasoning AI agents. No actual model-dispatch tool was exposed in this ChatGPT session. The Atlas Build Bus remains a synthetic SQLite core without approved real session adapters. Read-only hosted review, test-review and scheduler design work packets are documented in docs/ATLAS-RDC-SUPERPOWERS-HOSTED-SWARM-READINESS-20261117.md and remain NOT DISPATCHED.

## Evidence
All raw logs and samples are under /Users/brandondawson/RDC-Development/checkpoints/rdc-v17-gateway-review-20261116/:
- RDC-DC-MATCHED-30-TERMINAL-20261117.json
- rdc-coding-terminal-local-30-trials-20261117.json
- rdc-coding-terminal-8worker-lowpriority-20261117.json
- RDC-CODE-CONTEXT-30-TRIALS-20261117.json
- RDC-CODE-CONTEXT-30-TRIALS-PARALLEL-20261117.json
- rdc-code-context-RED-20261117.log and rdc-code-context-GREEN-20261117.log
- rdc-code-context-gateway-RED-20261117.log and rdc-code-context-gateway-GREEN-20261117.log
- rdc-code-context-worker-full-20261117.log
- rdc-code-context-gateway-full-20261117.log, rdc-code-context-gateway-build-20261117.log and rdc-code-context-gateway-lint-20261117.log

## Open gates
Protected inactive Site rollback version, actual authenticated free AI provider broker, real multi-agent dispatcher and Atlas approval, matched coding/edit tool-boundary benchmarks, and post-v17 performance remain OPEN. Keep v17 release on HOLD. Request Atlas ACCEPT or REWORK for the scoped source and tests, not whole-product or performance approval.
