# RDC development branch: cross-platform coding fixture line endings

TOC Ministries | 2026-11-17 CST

**Scope:** Source-only compatibility repair on existing `feat/rdc-chat-interconnect-20261117`. Public App release and live Site deployment remain on HOLD.

## Root cause

The branch's GitHub Windows runner at `22cf3eff0b0a7d5e9055556a1e3f19427e21bd59`, run `44054420243`, failed three coding-related tests, while the macOS and Ubuntu jobs passed. The Python test setup and benchmark used `Path.write_text` to create synthetic UTF-8 files containing LF. On Windows, text-mode writing normalized these explicit LF bytes to CRLF. The RDC file tools correctly hashed and read actual stored bytes, exposing a mismatch with the tests' LF-only source literals and SHA expectations.

## Minimal repair

Only the tests and disposable local benchmark fixture creator were changed:
- `tests/test_coding_context.py`: Create the `app.py` and `README.md` fixtures with `Path.write_bytes` and explicit LF binary literals; add raw-byte assertions in the readback test to prevent future regression.
- `benchmarks/coding_workflow.py`: Create synthetic `calc.py` and `test_calc.py` with `write_bytes(UTF8_string.encode("utf-8"))`. Preserve the actual byte-for-byte source, SHA, subsequent guarded edits, and command lifecycle unchanged.

The dedicated tests `tests.test_coding_context` and `tests.test_coding_workflow_benchmark` passed 8/8 on the iMac after repair. Test evidence: `~/RDC-Development/checkpoints/rdc-chat-cross-tool-20261117/windows-lf-fixtures-SCOPED-20261117.log`.

## Qualification and release gates

- Full Python regression: **449 tests, zero failures, 26 expected skips**, 136.383 seconds. Evidence: `windows-lf-fix-FULL-20261117.log`.
- Node gateway regression: **47/47 passed**, zero failures. Evidence: `windows-lf-fix-GATEWAY-20261117.log`.
- Exact same-revision Windows GitHub CI remains required to confirm actual runner behavior. Local macOS results are not Windows qualification.
- No change to real worker file encoding, terminal input, approval controls, auth, production D1/R2 or live Site v16.
- Public ChatGPT plugin release, v17 activation, cross-ChatGPT live enrollment and BandMates integration remain separately held until end-to-end host tests and independent review.

**Review:** Confirm explicit LF fixture generation and current Windows hosted CI, without changing the underlying RDC file functions to mask platform differences.
