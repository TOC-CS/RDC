# Private RDC diagnostics

RDC records a bounded local incident history for worker tool failures and relay
transport, dispatch and result delivery outcomes. This is an observation layer.
The recorder does not execute a tool, request approval, change grants, install
code or send telemetry.

Use the read-only `rdc_diagnostics_status` MCP tool with optional integer `limit`
from 1 through 50. It remains available during owner pause and review mode.
There is no action or free-text argument. The local equivalent is:

```sh
rdc diagnostics --state-dir /path/to/private/rdc-state --limit 20
```

The CLI does not load the worker configuration, read credentials, start a worker
or create diagnostic files. Its JSON contains no state directory path. An absent
or unsafe store returns `available: false` and `incomplete: true` with exit code
zero, so callers should inspect these fields rather than infer capture from exit
status.

## Finite data and limits

Each event contains a timestamp and predefined component, event, severity, tool
category and recovery category. Tool names are reduced to one of `files`, `jobs`,
`browser`, `mobile`, `desktop`, `credentials`, `system` or `other`. Arguments,
exception text, stack traces, paths, operation identifiers, credential locators,
page content and arbitrary caller text are never copied into diagnostic storage
or reports. Existing operation results keep their existing behavior; this change
does not sanitize or replace their authorized output.

The producer queue holds at most 256 entries. `record` performs no filesystem or
network operation and never waits for queue space. A background daemon drains
batches of at most 256. The SQLite store retains at most 2048 event rows and is
limited to 2 MiB. Reports return at most 50 events, newest first; `totals` counts
only the retained rows by finite event category. These are observed events, not
distinct user tasks or lifetime failure totals. Two layers can observe the same
incident, and an acknowledgement retry can be observed more than once.

Dropped writes and overflow increment `dropped_events`. The next successful write
persists the known drop count. `invalid_events` counts rejected event/component
submissions in the current process. `pending_events` counts queued and currently
writing entries in that process. A reader lock is nonblocking. Only the background
writer retries brief lock contention, for at most 50ms per batch. Persistent lock,
write or corruption failures drop that batch, make capture incomplete, and leave
the underlying authorized operation unchanged. A later event can attempt capture
again. No database repair or recreation of a corrupt existing store is automatic.

`close()` waits at most 250ms. The writer is a daemon; a slow filesystem can leave
pending capture after that deadline. `incomplete` identifies known drops, pending
capture, unavailable storage or a writer failure. It cannot prove that every
incident survived a crash, forced process termination or a device power failure.
In-memory drops that never reach a later successful write cannot appear in a
subsequent process's report. Retention also intentionally removes old events.

`capture_scope` distinguishes retained history plus current-process counters from
a CLI history-only view. CLI reports cannot observe another process's pending
queue, counters or liveness. A worker whose writer could not start explicitly
reports live capture unavailable even when older history remains readable. Before
the first stored event, the store can be absent and the report unavailable. A
successful read of old history alone does not demonstrate that a worker is running
or that all capture succeeded.

## Private file handling and supported platforms

Diagnostic files live in a private `diagnostics` directory beneath the existing
private worker state. Unix directories must be owned by the account and mode 700;
files must be owned by the account with no group or other permission bits. RDC
refuses symlinks, nonregular files, hardlinked files, oversized stores and unsafe
permissions. Directory and file access uses pinned descriptors and relative
`O_NOFOLLOW` opens. Replacing a path with a symlink cannot redirect a write to its
target. Filesystem paths never reach `sqlite3.connect`.

SQLite runs in memory and serializes its bounded image through checked file
descriptors under a nonblocking interprocess lock. This permits worker and relay
processes to aggregate incidents without SQLite following a replaced pathname.
SQL execution has a 100ms progress deadline, including reads of an externally
modified schema; malformed data is never exported as arbitrary report text. The
serialized store is written in place and synced while holding the lock. A crash
mid-write may corrupt this optional store. It cannot corrupt the separate worker
or relay journal, and the diagnostic store then reports unavailable. The account
owner can preserve and remove a damaged diagnostic store while RDC is stopped to
start fresh capture. This also removes its old diagnostic history.

This release supports secure capture on POSIX platforms with Python's
`O_NOFOLLOW`, directory-descriptor operations and SQLite serialize/deserialize
support. Independent Linux recorder and relay tests passed, and the frozen macOS
26.6.2 arm64 candidate passed all 254 tests with Python 3.14.7 and no skips. See
the [release evidence](VERIFICATION.md). Windows lacks
these directory-relative nofollow guarantees in the Python standard-library API.
It therefore returns `storage_status: unsupported_platform`, `available: false`
and `incomplete: true`; worker and relay operations continue. Tests simulate this
missing capability and exercise unchanged delivery/no-replay contracts. Native
Windows capture is unqualified and intentionally disabled rather than silently
weakening the file checks. On other storage failures, `storage_status` is
`unavailable`; successfully readable history has status `ready`.

After alpha4 activation, the local CLI read the real shared store with
`available: true`, `storage_status: ready` and `incomplete: false`, then exited
zero. At that check it retained one real relay `result_uploaded` event, with no
dropped or pending events. This history snapshot retains the capture and crash
limits above; it does not establish another process's continuing liveness.

## What RDC actually recovers

| Event | Meaning and existing behavior |
|---|---|
| `operation_failed`, `unexpected_error` | A guarded worker call failed. Existing results or exceptions remain intact. Reproduce and verify a repair, or resolve the owner/configuration issue. |
| `connection_interrupted` | Relay transport failed. Existing bounded backoff reconnects transports; no uncertain action is redispatched. |
| `reconnect_attempt` | Another connection cycle started after interruption. This records an attempt only. |
| `reconnected` | The worker session passed its identity/catalog checks and a gateway poll succeeded after interruption. This confirms transport observation, not successful completion of an earlier user task. |
| `result_upload_retry` | A retained result upload hit a transient failure. Only the recorded result is eligible for another upload. |
| `result_uploaded` | The gateway acknowledged that exact recorded result and the relay persisted delivery. The result may itself describe an error or unknown outcome. |
| `outcome_unknown` | Dispatch began but its outcome is uncertain. Inspect the worker before any new action. The execution tombstone forbids automatic replay. |
| `interrupted_before_dispatch` | Restart found an old received operation. It is retired without automatic execution. |
| `result_undeliverable` | The authenticated gateway retired the exact operation identity. Local state retains the outcome within the existing payload bound; the upload was not acknowledged and the action is not replayed. |
| `worker_rejected`, `permanent_failure` | A request, protocol, configuration or authentication condition requires inspection or owner action. Recording an event does not fix it. |

Heartbeats can observe interruptions during an active dispatch; their success does
not label that device action repaired. `reconnected` belongs to the complete main
connection cycle described above. Existing result retention, execution tombstones,
owner pause, credential consent, process ownership and approval boundaries remain
authoritative.

Unknown code defects require reproduction, a reviewed fix, meaningful tests and
activation of the approved exact version or trusted publisher through the reviewed
installer. Diagnostics never generate arbitrary repair code, install unapproved
updates, restart a device or claim that incident recording itself repaired code.
