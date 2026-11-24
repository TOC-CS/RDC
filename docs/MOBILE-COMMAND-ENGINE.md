# RDC mobile command engine: development preview

RDC exposes one client-neutral command interface over the existing authenticated
MCP worker. Any compatible AI client can discover and use the advertised tools.
No ChatGPT-specific runtime, hosted AI provider, or mandatory cloud service is
required for local worker operation.

## Select the execution location

| Route | Intended operation | Current boundary |
| --- | --- | --- |
| Device API | Enumerate configured devices/apps, launch/switch/terminate, diagnostics | Exact configured/authorized device; iOS discovery opt-in |
| Structured native UI | Discover controls, tap, fill, swipe, anchored gestures | Fresh observation and verified identity |
| Visual | Coordinate-based touch on a verified native frame | iOS full-screen single-window guard; up to two bounded contacts |
| Mobile-local sandbox | Commands and permitted files on the device | RDC companion private workspace; no unrestricted OS shell |
| Worker terminal | Existing durable terminal jobs | Executes on the selected authorized host, not the phone |
| Remote SSH | Remote host shell | Dedicated on-device SSH client integration remains pending |

Always use the most direct supported operation, inspect the actual result,
and never fall back to a second mutation when the first outcome is uncertain.
A failed launch-to-ready observation is not a failed launch. Preserve its
session and inspect instead of relaunching.

## Client workflow

1. Call rdc_mobile_command_read with operation capabilities and empty arguments.
   Read the schemas actually advertised by the connected worker.
2. Select a configured device, use open_ready or switch_ready, and keep the
   returned session/observation IDs. Inspect ready and timings_ms.
3. Use native handles first. Use a verified visual frame only for controls
   that need coordinate-based input. Refresh after input.
4. To use the local interpreter, open the RDC companion, enter its Local
   terminal screen, observe it and submit local_command with session_id,
   observation_id and command. Inspect execution_verified and exit_code.
5. Use the original durable job tools for host commands. Do not describe
   worker output as mobile-device execution. Use the original direct iOS
   launch tool when owner review is required. The original mobile close tool
   remains available for cleanup.

The local interpreter supports help, pwd, ls, mkdir, write, cat, sha256 and
echo. It runs on-device within the companion sandbox, with bounded input and
output, create-only files, no external file access or arbitrary process
launch. It is not a Unix shell, Python runtime, or unrestricted system terminal.
A submission is verified only from a fresh matching result receipt; a missing
or uncertain result must not trigger resubmission.

## Installation

See [mobile installation](MOBILE-INSTALL.md) and
[native source and packaging](../native-mobile/README.md).
The Android development package must be signature-verified before use.
iPhone and iPad builds require the user's own Apple provisioning and signing.
An iOS source archive is not an installable IPA. Do not redistribute personal
developer profiles, private keys, device identifiers or account information.

The native companion is distinct from the host-side automation driver.
A companion install does not grant the worker control of other applications.
The optional complete-source path needs a compatible, separately qualified
native driver. It is disabled by default; stock Appium does not provide
that custom command. Do not enable it merely because the worker supports it.

## Release and performance acceptance

The preview does not replace the production worker or release hold.
Measure app-to-ready, control discovery, input completion and input-to-fresh
frame separately. Initial engineering goals are warm app-to-ready p50 <=
1000 ms / p95 <= 2000 ms; discovery p50 <= 300 ms / p95 <= 750 ms; short-input
p50 <= 250 ms / p95 <= 500 ms; verified-frame p95 <= 750 ms; at least 10 distinct
frames per second. These are targets, not measured achievements. Cold
starts, driver startup, network transport and platform-specific restrictions
must be reported separately. Qualify at least 30 correct matched samples.
No test campaign may exceed 100 total runtime checks; preserve failures.

Public source, installers, walkthroughs and release notes use generic
synthetic fixtures only. No owner application usage, screenshots, private
test logs, signing material, personal paths, account information or device
identifiers may be packaged. Every published binary requires source identity,
signature status, SHA-256 and a truthful hardware qualification status.
