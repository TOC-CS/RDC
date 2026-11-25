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

### Keyboard-active control discovery

The keyboard-active form correction recognizes an explicitly visible
control inside the observed noninteractive full-window layout chain,
when exactly one visible native keyboard is present in a separate
window of the same visible application. It preserves hidden-window,
ambiguous-window, secure-field, disabled-ancestor and stale-observation
checks. It does not make arbitrary hidden UI elements actionable.
Physical execution and latency acceptance remain separate from source
regressions.

### General mobile interaction acceptance

Use generic, reproducible workloads and verify effects, not just input
acknowledgements. Keep the private test corpus separate from publications.

| Area | Required evidence |
| --- | --- |
| App identification and readiness | Exact app identity, launch result, usable controls, cold/warm elapsed time |
| Native navigation and input | Correct tap, text entry, back/forward, switching and close, with observed state changes |
| Scrolling and swiping | Correct axis, direction, displacement, target, end state and both orientations |
| Simultaneous touch | Independent contact identity, overlapping movement, correct endpoints and release order |
| Instrument-like surfaces | Actual timing, accurate target selection, chords, independent holds, repeated hits and continuous movement |
| Game-like surfaces | Verified practice-only movement, aim and independent simultaneous control; no competitive or account-state changes |
| Unfamiliar app surfaces | Discover available controls, select direct/structured/visual route, verify effect, refuse ambiguous or protected input |
| Continuous feedback | Distinct correctly attributed frames, timestamps, latency, dropped/stale-frame rate, no uncontrolled input queue |

Do not claim support for every application or instrument from one app or
synthetic fixture. Report measured coverage and remaining unsupported or
unverified surfaces. Keep the existing 100-operation campaign ceiling,
live acceptance thresholds, owner authorization and release hold.

### Combined input and fresh control observation

For tap, fill, swipe, anchored gesture and verified visual gesture operations,
pass the optional boolean post_observation=true to request a fresh structured
control observation in the same tool response. Use the new observation ID
and handles only after observation_status is observed. The response also
reports input_acknowledgement and action_to_observation in milliseconds.

This saves a separate client round trip and avoids sending image data for a
structured read. It does not eliminate native freshness verification or
establish the intended UI effect. A failed post-action observation returns
the original acknowledged operation and observation_status unavailable;
inspect the current state without replay. If the input itself has an
uncertain outcome, do not automatically observe-and-retry. Choose either
post_observation or post_frame_max_edge, not both. Visual input still
requires its own fresh verified frame.

This is source-qualified development preview functionality. The current
native driver and connected AI-host catalog must be verified independently
before using it; live latency reduction is not yet measured.

### Independently timed visual contacts (development preview)

The experimental iOS visual_timeline operation accepts up to three
continuous contacts, each with up to eight explicit logical-coordinate
waypoints (at_ms, x, y) and a release_ms time. The first contact starts at
zero; all contacts overlap into one continuous gesture of at most 3000 ms.
Each contact remains independently held until its own release. The worker
compiles aligned native action ticks, including interpolation at other
contacts' timing boundaries. It sends one native action request instead of
separate AI tool calls for each waypoint.

Use only a fresh verified frame from the intended authorized application.
All coordinates are bounded by the verified screen and the worker
revalidates the native hierarchy and exact window anchor before dispatch.
Uncertain input is never replayed. Native driver capabilities, physical
three-contact accuracy, release timing and actual latency require hardware
qualification; a generated action record alone is not evidence of them.

Optional post_frame_max_edge returns verified feedback after acknowledged
input, with separate input_acknowledgement and action_to_frame timings.
These timings include requested touch durations. Optional post_observation
returns structured controls instead. Do not claim a faster live control
loop from reducing client calls alone.

The timed-contact route is disabled by default. Only a dedicated, explicitly
owner-enabled iOS qualification profile may set the boolean capability
rdc:experimentalTimedContacts to true. It is consumed by the worker, not
forwarded to Appium, and never inherited by another application after a
profile switch. Existing ordinary tap, swipe and two-contact routes are
unchanged.

Source tests verify three independent planned paths and their timing.
An instrumented physical trial reported extra contact events and incorrect
endpoints. Do not use the experimental route for ordinary application
control until the native event record and actual touch receipts agree.
The optimization removes redundant coordinate moves after the last waypoint;
it retains required dwell waypoints before further motion. Reduced native
work is not an accepted latency benchmark when accuracy fails.
