# v17 rollback compatibility and UTF-8 result boundaries

## Problem
Original v16 is a result_key-only reader: v17 inline records have result_key=NULL and result_inline_json populated. An additive database migration preserves rows, but original v16 reports result_expired and ignores inline TTL cleanup. The old v16 release therefore cannot be a safe post-inline rollback target.

## Selected approach
Use the existing v17 gateway source to construct a **rollback-compatible reader** via a dedicated factory that forces maxInlineResultBytes=0, regardless of caller overrides. It reads both inline D1 results and legacy R2 records, but always stores new completed results in R2. This reuses the existing authorized owner checks, operation IDs, retry/TTL paths and migration, with no new endpoints or second gateway implementation.

A rollback-compatible release must be built and saved as an inactive, owner-private Sites version **before** any v17 inline writer is activated. Only that verified compatible version can be selected for rollback once inline data exists. The original v16 release stays a pre-v17 recovery option only; it is explicitly disallowed after v17 begins writing inline data. If Sites cannot retain and identify the compatible version without activation, v17 activation stays on HOLD. This scoped work does not migrate or deploy the live Site.

## Rejected alternatives
- Additive schema only: fails original v16 readback and TTL.
- Immediately rollback to original v16: corrupts read availability even though the row survives.
- R2 dual-write for every inline result: defeats the targeted latency and R2 reduction.
- Ad hoc conversion/drain endpoint during an emergency: introduces new privileged writes and possible partial conversion; requires a separate approved design.

## Test/acceptance matrix
- Reproduce the original v16 key-only read/cleanup failure on an in-memory inline record and acknowledge that original v16 remains unsafe.
- Write inline completed operation under v17, read same operation through rollback-compatible reader, assert exact content, authoritative operation ID, same durable identity, no extra device dispatch and cross-owner 403.
- Check inline TTL just before expiry, cleanup at expiry via compatible reader, result_expired on lookup, retained completed/no-replay tombstone, zero null-key R2 deletes.
- Store a NEW completed operation through compatible rollback writer, prove R2-only storage and recovery with original v16-style result-key semantics.
- Verify old legacy R2 result still reads under compatible reader and expiry removes R2 object.
- Assert UTF-8 JSON result bodies of exactly 8192 and 8193 bytes for both ASCII and genuine multibyte characters. 8192 must be inline in v17; 8193 must use R2. Confirm byte length, result_size, readback, expiry and idempotency.
- Upload worker content with forged _rdc_gateway_operation_id and forged _meta.rdc/operation_id, prove both return the actual gateway-owned ID on first read and duplicate recovery. Stored payload remains unmodified.
- Keep v17 deployment, live migration, private App/plugin identity, production data, and BandMates untouched.

## Rollback acceptance gate
This review can verify a compatible reader and build offline. It does **not** authorize v17 activation. Atlas acceptance requires exact source and binary receipts, protected saved rollback-compatible Sites version, full rollback/TTL/owner test evidence, matching host CI, and explicit confirmation the original v16 release will not be used as a post-inline rollback.
