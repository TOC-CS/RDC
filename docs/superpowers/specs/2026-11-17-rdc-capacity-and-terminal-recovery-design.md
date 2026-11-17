# RDC capacity and terminal recovery design
TOC Ministries | 2026-11-17 | Isolated development branch

## Intent
Keep an authenticated RDC worker usable under high request volume, including when the retained D1 journal is full and the active queue is empty. Preserve durable command IDs, output recovery, exit codes, and owner approvals. The actual connected @RDC tool must verify released fixes; speed superiority over Desktop Commander requires live matched data.

## Evidence
Live private Site v16 RDC connection_status reported online=true and pending_operations=0. The system_status and diagnostics_status calls both returned gateway_busy before queueing. Source SQL limits total retained rows independently from active backlog. REA research identified D1 polling and host round trips. Exact live D1 row count was unavailable.

## Approaches considered
A. Increase capacity limits: rejected as primary fix; delays recurrence and raises storage risk.
B. Delete old, unknown or completed mutations, skip no-replay: rejected, unsafe.
C. At failed admission, reclaim bounded expired read-only records with no stored payload: selected for isolated development, retaining mutations, active/unknown operations, and unexpired or R2-held results. Re-attempt the identical operation once, no blind retry.

## Evidence and verification
TDD RED reproduced full journal with zero active operations, GREEN after the smallest source change. Verify with independent read-only test lanes for gateway, terminal/relay, coding-context safety. No live owner browser or BandMates interruption. A low-priority deterministic test-lane runner is not an AI swarm: hosted AI credentials and session dispatch remain unverified.

## Release gates
ChatGPT plugin skills and cloud gateway are separate deployments. Plugin guidance alone cannot repair the live gateway. The private Site v16 and worker stay unchanged until protected rollback and release gates. Read back exact GitHub commit and run hosted three-platform CI if published. Verify actual @RDC job run and status with original job id after safe deployment. Matched 30+ RDC/DC trials before performance claims.
