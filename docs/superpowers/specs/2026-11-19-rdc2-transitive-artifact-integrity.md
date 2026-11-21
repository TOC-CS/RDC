# RDC 2.0 release artifact tree integrity guard

Date: 2026-11-19. Status: isolated local engineering only. No public Site, production deployment or live performance claim.

## Root cause

The first compiled Site guard pinned only `dist/server/index.js`, but the generated production worker uses `no_bundle: true` and loads separately emitted JS modules plus client assets. An unauthorized or accidental change to `dist/server/_next/static/*.js` or `dist/client/**` can leave the entrypoint hash unchanged. Thus an entrypoint-only pin cannot identify the exact executable Site release.

## Test-driven fix

RED: a transitive JavaScript module modification after pinning was not rejected. A normal `dist/server` plus `dist/client` layout also failed before support was implemented. GREEN: a deterministic SHA-256 fingerprint now contains every file's relative path and content hash across the entire supplied `dist` tree. The verifier rejects injected modules, changed client assets, symlinks, missing tree digests, misplaced entrypoints and unbounded artifact sets, while also preserving earlier exact binding and migration parity checks.

The verifier requires a separately pinned `--artifact-tree-sha256`, `--artifact-root`, `--bundle`, `--bundle-sha256`, `--baseline` and `--candidate`. It reports both individual entrypoint and whole-tree digests. Accepted layouts are a flat test artifact root or an actual `dist/{server,client}` tree, with manifest and entrypoint together under `server`.

The digests must be recorded independently from a known-good, controlled build. Recomputing a digest from an already compromised candidate immediately before checking it does not prove provenance. This verifier cannot prove private Cloudflare Site identity, deployed version history, live plugin configuration or rollback safety.

## Release gates unchanged

Protected owner-private Site version and rollback evidence, live compatible worker acceptance, >=30 correct real ChatGPT-connected samples for each speed target, p50/p95/p99 with no gateway_busy, and 30+ paired RDC versus Desktop Commander terminal/file/coding/browser workflows remain unverified. Do not enable tombstone archival or alter the production installation.

All test artifacts and receipt files stay in `RDC-2.0-QA`. Do not push to GitHub, publish a Site, or spend money for this milestone.
