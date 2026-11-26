# Private warm USB terminal candidate

This experimental source keeps one authorized USB connection open while a separate
development companion consumes authenticated commands in the foreground. It executes
the existing bounded RDC interpreter inside the companion's private workspace.
It does not provide an iPadOS shell.

## Source structure

- `rdc/ios_warm_terminal_codec.py`: exact-byte HMAC envelopes and bounded schemas.
- `rdc/ios_warm_terminal_usb.py`: fixed-device USB Documents transport with pinned
  pymobiledevice3 source, no automatic reconnect or input replay.
- `rdc/ios_warm_terminal.py`: synchronous persistent-loop bridge and durable
  request mapping. The parent cold-terminal journal remains the shared device fence.
- `native-mobile/ios/RDCWarmTerminal`: separate foreground-only companion.
- `native-mobile/ios/warm-project.yml`: separate bundle/build target with file sharing.
  The unsigned legacy mailbox is excluded from this target.

A fresh session requires explicit private provisioning, exact target binding and
an authenticated readiness response. It expires within ten minutes and admits at
most 64 commands. The device retains at most 64 global execution claims; the owner
must review capacity rather than silently discard the ledger.

Each request is claimed durably before execution. Results are retained privately,
then published atomically to the shared mailbox. An uncertain outcome stops new
commands. Recovery reads the exact prior result, including through a new read-only
host attachment. Missing shared results after device interruption may require
the authorized developer container route to retrieve the private receipt.

A fresh host attachment is consumed before connection. Backgrounding, cancellation,
protected-data loss and app restart cannot resume that session automatically.
The host adapter requires a synchronous worker context. Real USB qualification
uses the inspected CPython 3.13/pymobiledevice3 11.63.1 environment; importing the
modules does not initialize USB.

## Development preview verification

The warm transport uses an explicitly authorized development session. Its
separate app remains a test candidate and is not exposed as a live connector
operation. The cold terminal retains owner review, exact companion version
checks, durable command claims and read-only recovery.

The retained qualification includes 43 Python checks, 16 Swift checks, and
one Python-to-Swift authenticated interoperability check. The iOS target
compiled, signed and passed a three-command physical functional trial.
A subsequent bounded performance campaign verified 30 correct commands:
create-only writes, reads and SHA-256 calculations over one connection.

| Physical local USB measurement | Result |
| --- | ---: |
| Correct commands | 30/30 |
| Median command-to-result | 108.132 ms |
| Nearest-rank p95 | 129.020 ms |
| Minimum | 69.895 ms |
| Maximum | 147.904 ms |
| Connection setup | 1,963.526 ms |

All outputs and execution receipts were verified; exact-result recovery did
not replay input. The temporary development installation was removed and
the original application baseline verified. The performance campaign used
53 checks, including setup and cleanup. These measurements exclude cloud
transport, model processing and application installation. They establish
the local USB performance gate only, not connected-host latency or the
matched speed comparison against another connector.

Production activation, catalog exposure for the warm route, continuous
multi-contact accuracy and independently measured hosted response time
remain unqualified. No restricted native touch experiment is included in
this preview.
