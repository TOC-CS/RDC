# RDC 2.0: eliminate busy-worker wake and unrelated result fanout

Date: November 19, 2026. Isolated source candidate only, no deployed release.

## Goal and invariant
Reduce unnecessary WebSocket messages when RDC workers execute long commands or when other device connections finish jobs. Preserve every original durable operation, claim identity, owner guard, idempotent completion, R2 bulk recovery and legacy reconnect fallback.

## Test-first evidence
- Owner's 100-case governor preflight rejected an accidentally added 101st test before execution. The new assertions were folded into existing test cases, preserving 86 Node + 14 Python = 100, without relaxing any ceiling.
- RED regression, duplicate original claims: six work_available frames reached a busy socket. Log: RDC-2.0-QA/rdc2-busy-socket-backpressure-RED-20261119.log.
- GREEN regression: a claimed socket receives zero unrelated work_available frames during six queued admissions, then retains FIFO durable originals and may claim again only after exact original completion.
- RED regression, completion fanout: unrelated spectator received result_available for another socket's original operation. Log: RDC-2.0-QA/rdc2-result-fanout-RED-20261119.log.
- GREEN regression: the matching WebSocket claimant receives a single result_ack, no duplicate result_available; an unrelated socket receives no result notifications.
- Private bulk result regression: original WebSocket claimant receives one result_available when its original is completed through the HTTP/R2 large-result path, while the spectator receives none. R2 identity, recovery, duplicate and one-write guarantees hold.
- Focused test logs: RDC-2.0-QA/rdc2-busy-socket-backpressure-GREEN-20261119.log, rdc2-result-fanout-GREEN-20261119.log and rdc2-targeted-bulk-hint-GREEN-20261119.log.
- Final owner-governed campaign: RDC-2.0-QA/rdc2-busy-socket-final-100-20261119.json, exactly 100 executed, 100 passed, zero failures, zero skips. Omitted source tests remain untested.
- Source syntax and git diff whitespace checks passed.

## Source design
- If an authenticated connected socket already holds a durable claimed/unknown original, do not send it unrelated work_available hints during new admissions. It will ask for the next original after receiving the current exact ACK. The pending one-credit fast path is preserved.
- On committed result, clear the claim attachment for the matching original socket. Notify only this claimant when completion arrives by an alternate route. For WebSocket completion, the direct exact result_ack is sufficient, so suppress the duplicate result_available hint.
- Continue resolving all exact-operation owner HTTP waiters from the durable journal. Do not broadcast any tool arguments or private result data in hints.
- Keep legacy claim and claim_wait handshakes and owner authentication unchanged.

## Release boundary
Production ChatGPT RDC, Cloudflare Site, app, live worker, TOC VPS, Mac Mini and other projects were not modified. Local TDD and 100-case tests demonstrate correct source behavior but do not establish the required live terminal <=800ms, pickup <=50ms, claim-to-result <=150ms, notification <=1ms, coding <=800ms, nor >=2x versus DC. Authenticated protected hosted V2 canary, exact rollback, matched 30-pair task verification and source-identical cross-platform CI remain OPEN.
