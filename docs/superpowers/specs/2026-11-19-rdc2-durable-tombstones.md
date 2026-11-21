# RDC 2.0: Durable tombstone capacity and rollback

Date: 2026-11-19. Status: isolated source verified, NOT released.

## Identified failure
The V2 journal had a lifetime maxRecords=10,000 cap, including completed and
expired operation rows. Ordinary admission would eventually return journal_full
permanently even after payload expiration. Removing original IDs creates a risk
of replaying a mutating operation after a reconnect.

## Test-first fix
An additive immutable SQLite table, rdc2_tombstones, preserves the original
operation ID, bound owner, request key and digest, tool, mutation bit, final
state, claim ID, and result digest, without executable arguments or results.
An atomic, bounded transaction archives completed operations only after
result expiry, SQL payload retirement and R2 pointer deletion. Unclaimed
expired queue entries may be compacted. Unexpired, claimed and uncertain
operations remain in the hot journal. Duplicates and owner recovery read
both tables and retain exact original operation identity. Old result bytes
never return after expiry, and archived mutations never execute again.

This reclaims hot capacity, not the lifetime storage for deduplication
tombstones. There is no strict storage quota. Too many unresolved unknown
operations can still saturate hot capacity as a conservative failure.

## Critical rollback gate
An old V2 binary only reads rdc2_ops and would lose replay protection if
newer versions archived into a new table. Therefore the archive writer is
OFF by default and requires the EXACT explicit private actor variable
RDC2_TOMBSTONE_ARCHIVE_ENABLED=1. Do not enable it on a shared or production
private Site until the verified, protected rollback release can read both
tables and reject archived original mutation keys. The current live reader
has not yet been qualified for that capability.

An additively created empty tombstone table is ignored by the old reader.
The default continues old journal behavior. Synthetic local Workerd tests
may opt in; no V1 shared tables or deployed worker were modified.

## Verified contracts
TDD RED: three new tombstone tests failed before implementation.
Second RED: unconditional archive writes failed the rollback-default test.
GREEN: retained original IDs survive journal restart and 256 synthetic
confirmed mutations over 32 expiration cycles with only eight hot slots.
Unknown outcomes and unexpired R2 pointers remain unarchived. Forged digest
and foreign owner denied. Default write flag is OFF.

Real locally compiled Workerd Site: 30 real isolated WebSocket/terminal
operations, followed by server shutdown, offline expiration of synthetic
result payload bytes, restart, and owner-triggered archive of the 30 exact
original operations. Original keys and IDs survive, attempted duplicate
returns expired original outcome without command execution.

## Release status
Protected hosted deployment, tombstone-aware protected rollback,
at least 30 actual connected samples per five mandatory speed targets,
30 matched RDC versus DC terminal/file/coding/browser workflows, full
platform/security acceptance, and safe release drain are STILL OPEN.
Local HTTP and Workerd measurements must never be described as hosted
ChatGPT-connected performance.
