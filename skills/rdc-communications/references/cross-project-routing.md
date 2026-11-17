# Independently approved Atlas cross-project chat routing

**RDC/DC development contract | Live cross-project routing DISABLED pending Atlas review**

## Why an independent approval is required

The existing Atlas Bus v1 has exactly four platform project domains: `atlas`, `rdc`, `bandmates`, and `presentation`. Its current owner-maintained `BusStore` returns `CROSS_PROJECT_DENIED` for every direct cross-project send. Native ChatGPT Project membership is a separate subtenant of `rdc`, and its same-project one-time permissions are not permission to cross these four platform domains.

Central Atlas management needs an independently approved project-pair route to request and receive responses from RDC, BandMates, Presentation and Bus owners. The allowed direction and the **reverse direction** for replies require separate explicit grants. The routing policy may specify exact enrolled source/recipient sessions and `message` permission. Status read operations may have a separate scope. There is no competing bus, automatic owner enrollment, or new unrestricted manager superuser.

## Development adapter

`rdc.chat_cross_project.CrossProjectChatRouter` is an injection-only contract with three dependencies: trusted source/target identity verification, independent grant resolution, and an approved dispatcher. It refuses unverified principals, same-project or unsupported project pairs, absent grant, wrong direction, untrusted operations and a missing dispatcher.

The injected Atlas approval service must be authoritative and owner-controlled. Merely supplying `approved: true` or a `grant_id` in model text can never authorize a route. The `grant_id` received through the trusted approval service binds the exact source and destination project, operation, and reviewer identity. Every cross-project request retains immutable message and idempotency IDs. No shell execution, live mixer commands, device control or session cancellation is enabled by a messaging grant.

The adapter calls only an independently approved `dispatcher.send_once(grant,envelope)` interface with durable no-replay behavior. It deliberately does not call raw `BusStore.enqueue` to circumvent the current `CROSS_PROJECT_DENIED` gate. A synthetic test dispatcher validates the contract, but `live_configured` remains false. The existing Atlas Bus project owner's independent review and approved production adapter are still required.

## Acceptance path

- Atlas manager obtains an independent approval for `atlas -> rdc`, `atlas -> bandmates`, and `atlas -> presentation`, with explicit project owner consent. A return path such as `rdc -> atlas` requires a separately approved reverse direction.
- The actual authenticated manager ChatGPT session sends one bounded, permitted message using the installed RDC chat tool. A real recipient project session is enrolled through the same Atlas Bus and receives it without interrupting its active task.
- The recipient records explicit adapter fetch and **recipient acknowledgment**, then sends a permitted reply. The manager performs **reply readback** with matching correlation and causation IDs in its original session.
- Test idempotent retries, stale leases, refused grants, wrong project, changed payload, actor spoofing, browser interruptions, and one-time grant revocation. No unsafe replay is permitted.
- Only after independently accepted host tests can an approved inactive site candidate be promoted, and only with validated rollback. Public release remains held until the whole RDC communication feature is operational.

The four platform domains, authenticated routing, and project ownership remain with their original owners. BandMates audio/MIDI callback work must never wait for chat routing or SQLite. This development update is an integration contract and documentation, not a live authorization grant.
