# RDC Automatic Diagnostics and Recovery Reporting

## Intent and existing authorization

Continue the owner's approved RDC reporting and automatic recovery work. The previous conversation specified incident tracking, defined recovery, preparation and verification of repairs, and production changes tied to an approved exact version or trusted publisher. The owner approved the remaining repairs and requested takeover after the session limit.

The recovered alpha3 source already reconnects failed relay transports, retries retained result uploads, and preserves execution tombstones. It lacks a persistent, private incident overview. This continuation adds that missing observation layer and reports the actual recovery behavior. It never turns an uncertain device action into a repeat dispatch.

## Implementation decision

Use a small standard-library diagnostic recorder shared by worker and relay processes through a private SQLite database. Producers submit finite, sanitized events to a bounded queue and never wait for disk or network. Each process owns its writer thread; it closes within a bounded interval. SQLite provides process-safe aggregation. Record only predefined component, event, severity, tool category, and time fields. Do not store arbitrary messages, stack traces, paths, arguments, page content, identifiers, passwords, tokens or credential locators.

Keep at most 2048 recent events. Reports expose at most 50 entries and a finite set of totals and recovery categories. Incident categories explain which observed failures are handled automatically by existing reconnect/result-delivery behavior and which require a newly verified repair or owner action. Existing operating-system permissions, review mode, pause and credential consent remain authoritative.

Alternatives considered: raw log aggregation would admit private data; synchronous per-call writes would add latency and couple operation success to storage availability. A small bounded recorder fits the existing Python worker and adds no package or paid service dependency.

## Scope

- Automatic recording of worker errors and relay interruptions, successful reconnection, permanent relay failures and unknown outcomes.
- One read-only diagnostic MCP tool and a local diagnostic CLI command.
- Bounded, private persistent storage with conservative failure handling.
- Documentation of actual automatic recoveries and exact-version deployment controls.
- No arbitrary code generator, remote telemetry, new scheduled ChatGPT task, access grant, credential action, command replay, kill of active work, or automatic unapproved code installation.

Unknown code defects remain incidents for an agent to reproduce and repair under the existing development workflow. This component must never claim that recording an incident itself repaired it. The reviewed installer remains responsible for activating the approved, tested version and retaining rollback evidence.

## Acceptance

Synthetic secrets and user content cannot appear in diagnostic storage or reports. Recording does not block a command, approval or native action on a slow or unavailable diagnostic store. Retention, queue size and shutdown are bounded. Reports identify unavailable or incomplete diagnostic capture. Source behavior, API results and no-replay boundaries remain unchanged apart from the new diagnostic surface. Tests distinguish an interruption from a verified recovery.
