# Direct iOS sandbox terminal (development candidate)

The direct terminal uses the existing, owner-authorized Apple developer
connection to a compatible RDC Mobile Debug companion. It avoids keyboard
entry and native UI hierarchy reads. It is not a Unix shell, an arbitrary
process launcher, a public network listener, or a replacement for native
touch input.

Set ios_direct_terminal_enabled to true only in a private worker config
with the exact selected iOS/XCUITest profile for org.tocministries.rdc.mobile.
The development candidate accepts companion version 0.1.3, build 4.
No live config is enabled by this source change.

Use rdc_mobile_ios_direct_terminal_execute with profile, a canonical
unique request_id (UUID), and a bounded command. The dedicated operation
requires owner review even in trusted mode. It is deliberately excluded
from the generic mobile mutation router. Close native mobile sessions before
using the developer route. The request may relaunch only the selected RDC
companion. The existing UI terminal remains a separate fallback route;
never switch routes after an uncertain submission.

The worker records the request ID, exact profile/device binding, command
digest and phase in a private journal before any copy or launch. It
validates the returned request and command digest, run ID, exit status,
duration and bounded output. If a result is missing, recover it with
rdc_mobile_ios_direct_terminal_recover using the original profile and
request ID. Recovery only reads. A duplicate execute with the same request
and command also only reads the receipt. A conflicting reuse is refused.
An unresolved request blocks new commands to the same device. The journal
is capped at 256 records; review and reconciliation are required instead
of silently deleting recovery identities.

Command/result files and the exclusive claim reside in the companion's
developer-accessible Documents container. The interpreter remains confined
to its private workspace. Keep these records private. The development
transport does not expose a production service, provide arbitrary
administrator privileges, or authorize other app containers.

Source and device qualification are separate from installed AI-connector
activation and production release. Measure the full preflight, request
transfer, launch and result delivery using matched physical samples before
claiming a latency target. User-specific apps, screenshots, identifiers,
credentials and private signing material are excluded from publications.
