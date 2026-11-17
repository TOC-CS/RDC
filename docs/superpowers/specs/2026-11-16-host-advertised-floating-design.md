# Host-advertised floating-mode compatibility

## Goal
Make RDC's embedded UI honor the actual AI host display-mode capabilities before requesting automatic PiP. Keep automatic PiP on hosts explicitly supporting PiP, and preserve an inline view and visible explanation otherwise.

## Root cause
Codex/ChatGPT advertises only ['inline','fullscreen'] in its host context. Previous RDC canFloatInHost() treated the mere existence of legacy window.openai.requestDisplayMode as PiP support, resulting in automatic unsupported PiP requests, occasional fullscreen substitution, and extra restore-inline calls. The MCP Apps specification requires checking the host's actual availableDisplayModes before requesting a mode.

## Decision and alternatives
- Preferred: only request PiP when state.modes from the host includes 'pip'. This is smallest, portable, and host-authoritative. Existing automatic logic continues on a PiP-capable host. Unsupported hosts show the existing in-panel fallback notice, without a mode request or fullscreen transition.
- Reject: infer PiP support from legacy requestDisplayMode function existence; function existence does not establish host mode support and Codex refuses that request.
- Reject: popup/new OS window, automatic fullscreen, iframe overlay outside host surface, host injection, permission hacks. User explicitly forbids them.

## Acceptance
New regression fails on old code with a legacy bridge function present but the host omitting PiP: no request may be sent on initial open or reopen; note visible and canvas inline. Supported-host PiP still automatically requests once on open/reopen and uses confirmed host result. No worker, transport, App identity, browser session, BandMates or data configuration changes.
