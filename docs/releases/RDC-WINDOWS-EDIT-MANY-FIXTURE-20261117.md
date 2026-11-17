# RDC Windows Multi-File Edit Fixture Regression

TOC Ministries | November 17, 2026
Scope: Isolated `integration/rdc-performance-20261117` branch
Release: Source-only. Live Site v16 and worker v0.1.0a8 preserved. Public release held.

## Root cause and verified failure

The GitHub Windows job in run [44069200154](https://github.com/TOC-CS/RDC/actions/runs/44069200154) failed exactly two tests in `tests/test_coding_edit_many.py`:

- `test_two_surgical_edits_in_one_durable_operation`: Both SHA-256 edit preconditions conflicted.
- `test_stale_file_reports_explicit_partial_results_without_replay`: The second edit could not apply, so the expected partial-success state was absent.

The test setup used `Path.write_text` with LF string literals. Windows text-mode writing produced CRLF bytes in the synthetic `first.py` and `second.py` fixtures while expected hashes still described LF-only literals. The underlying guarded editor correctly rejected mismatched SHA-256 values. This is a test portability defect, with the same cause as the previously fixed coding-context Windows fixture problem.

Source CI evidence: `~/RDC-Development/checkpoints/rdc-performance-integration-20261117/windows-ci-ccb470d-REST-JOB.log`.

## TDD repair

First wrote `test_fixture_lf_bytes_survive_windows_text_writer` to simulate CRLF conversion during test fixture setup and assert exact stored LF bytes. **RED**: got `b'return a - b\\r\\n'` instead of `b'return a - b\\n'`. Evidence: `lf-batch-windows-sim-RED-20261117.log`.

Changed only the two fixture setup calls from `Path.write_text` to `Path.write_bytes` with explicit byte literals. No production editor or code context implementation was changed.

**GREEN**: all 8 focused edit-many tests passed locally, including the simulated Windows behavior. Evidence: `lf-batch-windows-sim-GREEN-20261117.log`.

## Acceptance

The full updated-source Python test suite and gateway suite must pass before publishing this fix. After the source is committed, Windows GitHub CI must pass on the new exact commit, with Ubuntu and macOS checked separately. The previous failing run is preserved as diagnostic evidence.

Keep the feature branch isolated from main, preserve its original merge ancestry and all unrelated branches, and do not activate held v17 or the private Site based solely on this fixture correction.
