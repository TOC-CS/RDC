# RDC Superpowers, free hosted AI models, brainstorming and swarm readiness

**Date:** 2026-11-17 CST
**Owner:** Existing RDC development owner session. **Project:** TOC RDC.
**Status:** METHODOLOGY ACTIVE, DETERMINISTIC SWARM TESTED, HOSTED AI INFERENCE BLOCKED BY APPROVED CREDENTIAL BROKER ACCESS.
**Controlling directives:** `docs/TOC_MASTER_BUILD_WORKFLOW_V1.md` and `docs/TOC_SHARED_HOSTED_AI_API_ACCESS_V1.md`. Preserve the current owner/branch, existing private App/Site, v16 production and v17 release HOLD.

## Requested outcome
RDC must outperform Desktop Commander in coding, terminal execution, task accuracy, throughput, multi-agent scheduling and skills. Target >=2x better p50/p95 on matched eligible workloads, with no accuracy, security, robustness or resource regressions. Failing dimensions remain OPEN. No claims of superiority from local engine-only tests.

## Actual skill and tool availability
- Superpowers plugin appears in the owner's ChatGPT Plugins settings, but this session's callable tool catalog provides **no Superpowers MCP actions or installed Superpowers skill documents**. The full TOC Superpowers workflow directive was read and applied as working methodology: brainstorming, independent plan, first failing test, systematic debugging, focused green, measurement, verification, independent review. Status: **methodology applied; external plugin tool activation UNAVAILABLE**.
- Brainstorming methodology was applied to the bottleneck review below. Separate callable brainstorming skill adapter: **UNAVAILABLE**.
- REA v6.9.0 CLI is present. Earlier static compiled-bundle analysis failed due an installed macOS Swift toolchain helper. Source is available, so deterministic source inspection and tests are preferred for this task. Do not change global tools merely to satisfy optional REA.
- ChatGPT RDC App and Remote Desktop Commander (DC) tools both callable on the same authorized iMac. Hosted AI provider adapters for RDC **not yet authenticated**.
- No ChatGPT subagent dispatcher exposed by the current callable tool catalog. The existing BandMates-Swarm is separately owned, read-only inspected and untouched.

## Secure hosted model readiness, no credentials exposed
Existing owner-approved service names, **not secret values**: `toc-dev-swarm-nvidia`, `toc-dev-swarm-openrouter`, `toc-dev-swarm-gemini`, `toc-dev-swarm-grok`.

The current shell ran **metadata-existence only** `security find-generic-password -s SERVICE` with all output suppressed and **without** `-w` or `-g`. The default search list returned status 44 for all four. A second *explicit login-keychain file* metadata-only lookup returned status 0 for **all four service entries**, confirming they exist in that Keychain. The BandMates-Swarm `doctor` still reports NVIDIA, OpenRouter and Gemini as `configured:false`; its opt-in secret lookup uses `security find-generic-password -w -s SERVICE` **without** the explicit login-keychain positional argument, making default search-list mismatch a concrete hypothesis. Successful metadata lookup does not establish permission to read tokens or use provider APIs. The saved-key GUI indicators are consistent with the explicit login-keychain metadata result. **APPROVED KEYCHAIN BROKER ACCESS/OS CONSENT REMAINS UNVERIFIED**. We did not invoke `-w` or `-g`, start provider inference, reveal key bytes, change Keychain ACL, modify the separately owned BandMates-Swarm, or trigger approval prompts. Recommend that the owning Swarm team add an explicit authorized login-keychain lookup and test it inside the owner-approved process, without returning secret bytes.

Candidate free-only model routing once an *authorized* broker and account-free status are confirmed:
1. **OpenRouter:** an exact currently available `:free` model for coding/review, or `openrouter/free` routing only if the task permits a model chosen dynamically. Use the official current model catalogue and confirm returned model ID, prompt/completion pricing $0 and limits before dispatch. The documented free variant rate cap is 20 requests/minute and 50 requests/day for nonfunded accounts, subject to change. No purchased credits.
2. **NVIDIA hosted NIM API:** use its official available developer API catalogue, only an eligible free serverless development endpoint; verify specific model and account entitlement before sending prompts. No assumption of unlimited credits.
3. **Gemini:** a model with a confirmed Gemini Developer API Free Tier for that exact project and account, with usage ceilings and data-policy review before coding. No automatic paid tier.
4. **Grok/xAI:** billable inference explicitly DISABLED.

Public model catalogue references: https://openrouter.ai/collections/free-models/ ; https://build.nvidia.com/explore ; https://ai.google.dev/gemini-api/docs/pricing/ . No source or secrets have been transmitted to model providers. Live account quota, credits, saved keys, and coding model quality remain unverified.

## Brainstormed bottleneck hypotheses and decisions
- **Coding microproject:** 30/30 local deterministic workflows passed. Source hash checking, code search, batched file reads, exact edit, test creation, test recovery and terminal errors were correct. p50 270.821 ms, p95 368.258 ms (local Engine, excluding cloud/AI-host).
- The three Python subprocess test phases consumed p50 approximately 84.3 + 84.2 + 53.0 ms. The candidate optimization order is preserving safe session reuse and reducing unnecessary process spins, *after* independent research of DC and Python worker semantics. Do not weaken process isolation, shell permission checks or no-replay.
- **Real separate worker processes (not AI agents):** 1x2 workflows 2/2 correct at ~1.8 tasks/s; 2x4 at ~4.254 tasks/s; 4x8 at ~6.785 tasks/s. A lower-priority 8x8 run passed 8/8 at ~4.424 tasks/s, p50 ~1019 ms per task. Concurrency gains are not monotonic; use bounded pool and protect foreground BandMates audio.
- **Cloud bottleneck:** prior v16 gateway phase samples n=12 showed pickup p50 311 ms and claim-to-result p50 678 ms, while ChatGPT terminal round trips were seconds. Host/network and serialized polling require distinct measurement before changing relay concurrency or claiming 2x over DC.
- **Inter-agent safety:** use exclusive worktree paths, approved read-only reviews, SHA-checked merges, bounded concurrency, per-agent CPU/RAM budgets, no duplicate execution and owner-only approval gates. Swarm tasks must not use private customer/code data in model prompts without authorization.

## Proposed hosted swarm work packets (NOT YET DISPATCHED)
| Packet | Proposed lane | Exclusive scope | Required verified output |
|:--|:--|:--|:--|
| RDC-CODE-REVIEW-A | Hosted coding reviewer, read-only | Existing isolated benchmark + public tool schemas | Three evidence-backed improvements, no unsafe calls |
| RDC-TEST-REVIEW-B | Separate hosted test reviewer, read-only | Synthetic regression/benchmark snapshots | Failure modes, missing tests, exact reproducible commands |
| RDC-SCHEDULER-C | Hosted architecture brainstorm, read-only | Synthetic relay/queue model only | No-replay safe concurrent lane design and rollback conditions |
| RDC-BENCH-D | Deterministic local bench analyzer | Only files under `checkpoints/rdc-v17-gateway-review-20261116` | p50/p95/p99, errors, throughput, workload fairness, no invented metrics |

The packets are **queued proposals**, and nobody has been told to run them under another project's identity. Owner approval for the future broker is governed by the existing directive, and all source writes must go through the existing RDC owner after independent Atlas review.

## Follow-on real tool-boundary and coding-context evidence
- Matched live v16 RDC cloud and DC tool calls on the same iMac used the exact same harmless shell stdout and working directory, with 30 balanced AB/BA pairs and exact output validation. Both were **30/30 correct**. RDC tool-boundary p50/p95: **3,178/5,148.3 ms**; DC p50/p95: **1,820/3,642.5 ms**. RDC is currently **1.746x slower** at median and **1.413x slower** at p95 for this limited shell-echo workload. Command execution p50 **5 ms**. This confirms the 2x RDC win target is OPEN and cloud/connector overhead is the key next qualification scope. Raw data: `/Users/brandondawson/RDC-Development/checkpoints/rdc-v17-gateway-review-20261116/RDC-DC-MATCHED-30-TERMINAL-20261117.json`. No claim for coding edits, multi-agent or v17 on this sample.
- To remove repeated remote coding-inspection hops, added candidate read-only `rdc_code_context` with bounded project-subtree listing, literal search and up to 20 independent hashed source reads. The added Python regression went RED with `unknown_tool`, then **4/4 GREEN**, including correct hashes, in-review read-only use, path escapes denied before partial output and bounded per-file error results. The added gateway catalog sync test went RED with missing tool, then GREEN after regeneration; tool count is now **59** while preview HTML, original logo and compact icon remained byte-identical. Production activation not performed.
- Direct-local balanced code-context benchmark: 30/30 correct on each variant; **three calls p50 8.257 ms**, **combined one call p50 8.421 ms**. The combined call adds only 0.164 ms local median on a synthetic 60-file workspace but avoids two *potential* cloud round trips. This is **not a measured cloud speed win**. A read-only six-thread parallel experiment was rejected after it worsened p50 to 12.556 ms; source was reverted to the simpler bounded path. Raw both versions: `RDC-CODE-CONTEXT-30-TRIALS-20261117.json` and `RDC-CODE-CONTEXT-30-TRIALS-PARALLEL-20261117.json`.
- Updated offline gateway test suite: **45/45 passed**; gateway production build passed and lint had zero errors (one previously known image hint). Python full-suite rerun is recorded separately and must be confirmed after the final source change before review. No RDC worker or BandMates restart, no Site changes and no new provider inference.
- Real multi-agent hosted reasoning remains BLOCKED until the separately owned Swarm's authenticated broker can access the explicit login Keychain with normal macOS approvals, free-only model routing and isolated worktree ownership. The Atlas Build Communication Bus is synthetic only, without real session adapters or independent reviewer acceptance.

## Reproducible local evidence
- `benchmarks/coding_workflow.py`
- `tests/test_coding_workflow_benchmark.py`
- `docs/superpowers/specs/2026-11-17-rdc-vs-dc-code-agent-performance.md`
- `docs/superpowers/plans/2026-11-17-rdc-coding-performance-qualification.md`
- `/Users/brandondawson/RDC-Development/checkpoints/rdc-v17-gateway-review-20261116/rdc-coding-terminal-local-30-trials-20261117.json`
- `/Users/brandondawson/RDC-Development/checkpoints/rdc-v17-gateway-review-20261116/rdc-coding-terminal-8worker-lowpriority-20261117.json`

## Acceptance gates
- No API model declared active without authenticated, zero-cost requests through approved credential access and a successful sanitized coding test.
- No actual AI swarm declared active without independently running agent instances, isolated task ownership, validated messages and evidence of outputs.
- No universal RDC > DC claim until matched 30+ trial competitive benchmark across all supported coding, terminal, concurrency and skill dimensions.
- v17 private Site production deployment remains on HOLD pending protected inactive rollback-compatible version and Atlas acceptance.
