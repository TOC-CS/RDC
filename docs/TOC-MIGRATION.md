# Transition from TOC Commander to RDC

Keep the existing TOC Studio and its tools running while validating RDC in a separate directory and state profile. RDC is a clean implementation; it does not read or export the old private token, approval database, browser cookies, or machine-specific configuration.

1. Install the new worker into its own Python environment and initialize a limited test workspace.
2. Start `rdc serve` and use `rdc connect` from the AI client. This preserves one shared browser for the preview.
3. Verify file read/create/exact-edit, a background command, retained failure output, duplicate-start prevention, reconnection, browser fill/click/image, pause, and owner takeover using synthetic fixtures.
4. Expand owner grants only for the actual workflows needed. Configure native desktop or mobile permissions through the OS. Select isolated workers when native input must not interfere.
5. Add client configuration alongside existing tools, then select RDC deliberately for a real bounded project. Keep the existing service available for rollback.
6. Replace the hosted connector only after the needed ChatGPT surface, remote endpoint, authentication, and device routing have passed actual tests. Local Codex success does not prove ChatGPT web connector readiness.

The existing TOC integration's broken `edit_block` contract is avoided by RDC's consistent `rdc_file_edit(file_path, old_text, new_text, expected_sha256)` schema. Old TOC tool names are not silently aliased. Any custom scripts calling the old `/api/commander/agent` endpoint must be migrated intentionally to MCP or the new owner API.

No subscription is cancelled by this migration. Cancellation should follow a verified replacement and the owner's decision. Existing TOC private content and third-party proprietary remote assets must stay out of the public source repository.

