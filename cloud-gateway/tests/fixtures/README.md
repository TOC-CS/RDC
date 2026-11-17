# Historical RDC Site v16 gateway test fixture

The file `rdc-gateway-core-v16.mjs` is an **unaltered source snapshot** of the actual gateway reader originally deployed in RDC Site v16. It came from the existing RDC repository commit `3001050`, path `cloud-gateway/lib/rdc-gateway-core.mjs`.

The fixture SHA-256 is:

`5651f14c6fc8a7308f37a5454a006ec2b0fb459aae97997554a8d296f160cd4f`

The `gateway.test.mjs` regression pins that digest, executes the historical `createGateway` implementation against a migrated in-memory D1 database and synthetic R2 bucket, and demonstrates two known incompatibilities with v17 inline-only records:

1. Original v16 returns `result_expired` for a completed result while its authorized inline payload is still present.
2. Original v16's key-only cleanup ignores an expired inline-only payload.

The same regression then runs the rollback-compatible gateway on the same database to enforce TTL cleanup while retaining the completed operation's no-replay tombstone. No live database, worker, credential, Site deployment or external network is used.

This file is a **test-only historical snapshot**. Never import it into production or modify it to silence a regression. Update its source or pinned hash only after an explicit independent review that establishes the precise historical version being tested.
