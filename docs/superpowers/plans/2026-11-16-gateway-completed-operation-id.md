# Completed Gateway Operation ID Plan
Use Superpowers test-driven-development and verification-before-completion.

Goal: make existing owner-only cloud phase diagnostics discoverable from normal completed connector tool calls.

Architecture: annotate only the existing completed readback boundary, with a reserved structuredContent metadata property. No new worker operations or database requests.

Tasks:
- Write a failing focused fast-terminal test asserting the gateway ID is visible in structuredContent, owner-only diagnostics can recover the ID, and original output is preserved.
- Confirm the focused test fails before writing production code.
- Implement a minimal guarded annotation in operationResult.
- Verify focused and full gateway suites, production build and diff checks.
- Keep changes isolated until main cloud-storage work is safely committed; preserve original private Site/Plugin identities and rollback.
