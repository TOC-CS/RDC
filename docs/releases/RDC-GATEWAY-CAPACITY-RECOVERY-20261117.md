# RDC Gateway Retained-Journal Capacity Recovery
TOC Ministries | November 17, 2026
Status: ISOLATED SOURCE PATCH ONLY. NOT DEPLOYED.

## Observed live symptom
The connected RDC connection status returned online=true and pending_operations=0. Connected system status and diagnostics both failed with gateway_busy: "The relay has reached its bounded backlog or retention capacity. No operation was queued." Production D1 row counts could not be read via the current tool catalog. Retained journal saturation is source-consistent but production cause is not definitively proven.

## REA pipeline grounding
See ~/RDC-Development/checkpoints/rdc-dc-pipeline-rea-20261117/PIPELINE-TRACE-AND-BENCHMARK-MASTER.md. RDC uses D1 queue and long polling. DC 0.3.1 uses a Realtime notification and conditional claim. REA completed selected source-file analysis but not hosted backend analysis. The 30-pair user-facing echo baseline was RDC p50=3178ms and DC p50=1820ms. This patch addresses refused admissions, not measured p50 superiority.

## Source root cause
Admission limits total retained rows to maxOperations (default 2000), in addition to backlog. Standard cleanup erases expired payloads but keeps most completed read-only rows for operationTtlMs (24 hours), allowing journal refusal with zero active jobs.

## Repair
Only after an admission fails, check whether the retained journal row limit is reached. If so, delete at most 32 completed or expired nonmutating rows whose result retention is expired and whose R2 and inline payloads are absent, then retry admission of the exact same request once. Do not remove active/unknown operations, mutations, unexpired responses, or R2 references. Full active backlogs, valid retention and mutation-only saturation still reject, preserving no-replay safety.

## Evidence
~/RDC-Development/checkpoints/rdc-gateway-capacity-hotfix-20261117/
- capacity-RED.log: failure reproduced first.
- capacity-GREEN.log: 2 focused tests pass.
- gateway-FULL-FINAL.log: 58 of 58 gateway tests pass; 0 skipped.
- git diff --check: pass.

## Release boundaries
Source-only from b2349b6. No live Site, worker, secrets or active BandMates changes. Separate owner maintains overlapping uncommitted capacity and communications changes at rdc-chat-bridge-service-binding-20261117. Its earlier gateway suite was 64 passed and four failed. Reconcile source and tests before integration and cross-platform CI. Existing v17 protected rollback and deployment authorization gates remain. Refusal caused by retained mutations or unexpired payloads requires separate authorized diagnosis, not deletion of protected operations.
