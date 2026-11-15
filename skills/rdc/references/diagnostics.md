# Private incident reports

Use this guidance when a connected core 0.1.0a4 or later worker advertises `rdc_diagnostics_status`. Confirm the active worker and gateway catalog; saved guidance does not activate a release. RDC records bounded local categories for worker failures and relay transport, dispatch and result delivery. The recorder observes existing behavior without executing tools, changing grants, installing code or sending telemetry.

## Read the report

Call `rdc_diagnostics_status` with an optional integer `limit` from 1 through 50. It is read-only and remains available during owner pause and review mode. There is no repair, action or free-text argument. Keep normal cloud operation recovery authoritative when this call or the original task is pending.

For an authorized local inspection with a known private state directory, use:

```sh
rdc diagnostics --state-dir /path/to/private/rdc-state --limit 20
```

Use the selected worker's existing state location, never a guessed path. The CLI reads retained history without loading worker configuration, reading credentials, starting a worker or creating diagnostics files. An absent or unsafe store can return exit code zero with `available: false` and `incomplete: true`; inspect the JSON fields.

| Field | Interpretation |
| --- | --- |
| `available`, `storage_status` | Check both. `ready` describes readable retained history. `unavailable` can mean absent, unsafe, damaged or temporarily inaccessible storage. `unsupported_platform` means capture is disabled on that platform. |
| `incomplete` | Known drops, pending capture, unavailable storage or writer failure can set this flag. A false value cannot prove that every incident survived a crash, power loss or retention. |
| `capture_scope` | Distinguishes retained history plus current-process counters from CLI history or a process whose live capture failed. CLI output cannot reveal another process's pending queue, counters or liveness. |
| `events`, `totals`, `retained_events` | Events are newest first; totals count retained event rows. Different layers and repeated delivery attempts can describe the same incident. Counts do not represent distinct failed user tasks or lifetime totals. |
| `dropped_events`, `pending_events`, `invalid_events` | Report known dropped capture, current-process queued/writing entries and current-process rejected entries. Drops never persisted before a process exit can be absent from later history. |

The store retains at most 2048 events within 2 MiB; each report returns at most 50. Before a first stored event, history may be unavailable. The report contains finite categories and timestamps, without argument values, exception text, stack traces, paths, operation IDs, credential locators or page content. Existing authorized operation results retain their own output behavior. Use their actual IDs and state for recovery instead of trying to identify a particular task from aggregate incident categories.

## Interpret observed recovery

| Event | Next interpretation or action |
| --- | --- |
| `operation_failed`, `unexpected_error` | Inspect the original authorized result, reproduce a defect where appropriate, or resolve the reported configuration/owner condition. |
| `connection_interrupted`, `reconnect_attempt` | The existing relay performs bounded reconnection attempts. An attempt alone establishes no recovery. |
| `reconnected` | Worker identity/catalog checks and a gateway poll succeeded after interruption. Check the original task separately. |
| `result_upload_retry`, `result_uploaded` | The relay retries upload of the retained result. Uploaded means that exact result was acknowledged and delivery persisted; the result can still report failure or an unknown outcome. |
| `outcome_unknown` | Inspect actual worker state before a new action. The execution tombstone prohibits automatic replay. |
| `interrupted_before_dispatch` | An old received operation was retired without automatic execution. |
| `result_undeliverable` | The gateway retired the exact operation identity. Its result was not acknowledged; the action stays unreplayed. |
| `worker_rejected`, `permanent_failure` | Inspect the configuration, authentication or owner condition using authorized routes. An incident entry performs no repair. |

Use [cloud operations](cloud-operations.md) to recover the exact original request, operation, job or approval. Heartbeats and incident history cannot establish successful device actions. A code defect needs a reviewed fix, meaningful verification and activation through the approved installer. Do not turn diagnostics into arbitrary code execution, unattended grant changes or a new action-retry mechanism.

## Platform and storage boundaries

Secure capture requires the POSIX directory-descriptor, `O_NOFOLLOW` and SQLite serialization capabilities described by the core release. Linux qualification does not qualify the exact macOS runtime. Windows returns `storage_status: unsupported_platform`, `available: false` and `incomplete: true`; ordinary worker and relay operations continue. Apply the current release evidence to the intended worker before claiming capture works there.

Unsafe, linked or damaged storage is refused. Preserve that result and inspect the cause; never relax permissions or file checks to force capture. No automatic repair or recreation of a corrupt store occurs. Removing a preserved diagnostic store while RDC is stopped discards its history and requires a deliberate owner-authorized maintenance decision.
