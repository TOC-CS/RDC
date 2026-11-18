# RDC Search-to-Source Design | 2026-11-18

## Goal
Reduce ChatGPT tool roundtrips for reading source found by a code-context search, preserving bounded output, project scoping, SHA-256 versioning, and transparent partial errors. This advances the RDC versus Desktop Commander capability and latency work without touching the live v16 worker.

## Evidence and alternatives
The November 17 REA comparison establishes Desktop Commander 0.3.1 has a Realtime wakeup/conditional claim path, whereas RDC v16 uses durable D1 long polling. The previous matched 30-round terminal baseline measured RDC p50 3,178 ms versus DC 1,820 ms. These transport metrics do not prove RDC engine speed. Candidate RDC code_context already combines listing, search and explicit reads, but a new agent does not yet know file_paths returned from that same search.

Alternatives: (A) change gateway delivery to event-driven (potential speed, high rollout and no-replay risk); (B) optionally read the first distinct search matches in that existing read-only request (low risk, saves one discovery roundtrip); (C) maintain a content index (fast recurring searches, but stale or private data and invalidation concerns). Select B as an independently testable improvement. Pursue A separately with cloud diagnostics and release controls.

## Contract
Add optional rdc_code_context(read_matches: integer 0..5, default 0). It requires query when nonzero. After bounded search, select up to read_matches unique matching files, preserving match order; append only paths not already explicitly requested, and never exceed the existing 20 total reads. Each file is revalidated at use, read with the same 16 KiB output budget and SHA-256, with per-file errors visible. No writes. Results include auto_read_count and read_limit_per_file. Existing calls without read_matches behave as before.

## Security and measurement
Reject read_matches without query. Recheck project boundaries after discovery; never read a changed symlink outside selected project. Only request source from search_mode=source by default, explicitly all to include generated trees. Test duplicates, multiple lines, no matches, permission escape, and large file truncation. Compare same request over isolated local engine first; this feature is source-only until hosted Site/worker release and new live A/B tests. Keep original v16 and other owners intact.

## Skills
Extend skills/rdc-coding/SKILL.md with discoverability, exact usage, fallback for live environments where the catalog lacks read_matches, and replay/partial-output safeguards. Skill is versioned source only until authorized publication.
