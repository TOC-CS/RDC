# RDC 2.0 post-result credit: measured A/B rejected

2026-11-20. Scope: isolated VPS loopback-only gateway through encrypted SSH tunnel to the same authorized iMac test worker. The installed ChatGPT private Site and production relay were never changed.

Candidate: post-completion credit scheme previously committed as 900a2b8. TDD local regression passed 12 gateway + 28 relay, and standard 100-case source campaign passed. Single 30-operation full MCP trial was also correct, but its p50 was slower.

A controlled interleaved 60-operation benchmark executed 12 alternating batches of five calls. Each variant completed 30 real read-only terminal commands with original exact output. This campaign obeyed the shared maximum of 100 operations. Raw local evidence: RDC-2.0-QA/rdc2-postack-interleaved-ab60-20261120.json.

| Measured latency | Existing gateway | Opt-in post-result credit |
| --- | ---: | ---: |
| p50 | 139.308 ms | 158.285 ms |
| p95 | 187.078 ms | 257.044 ms |
| p99 | 563.239 ms | 490.411 ms |
| Maximum | 715.953 ms | 566.584 ms |
| Worker claim_wait frames | 33 | 8 |
| Correct outputs | 30/30 | 30/30 |

The candidate eliminated most claim_wait frames and improved the rare worst tail, but increased median by 18.977ms and p95 by 69.966ms in the interleaved campaign. The speed-first acceptance priority rejects this source change. This document and the original commit retain the experimental evidence; the active source reverts to the faster baseline. Do not re-activate this design without a fresh, demonstrably faster candidate.

The separate post-ACK QA gateway on port 18788 was gracefully stopped after exact process identity verification. Existing owner gateway and QA gateway on ports 18782, 18784 and 18786 were all confirmed healthy. Production Site remains untouched.

The release gate still requires five absolute measured live targets plus the sixth independent >=2x matched Desktop Commander advantage on the actual ChatGPT-connected path.
