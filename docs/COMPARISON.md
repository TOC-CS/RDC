# Comparison and improvement targets

Reviewed 2026-11-15. Distinguish the free local DesktopCommanderMCP project from its hosted Remote Desktop Commander connector.

| Evidence | RDC response | Verification requirement |
|---|---|---|
| Local Desktop Commander is free MIT software; remote hosted implementation is proprietary with free and paid tiers | Original MIT worker, transport, dashboard and adapters, no mandatory vendor relay | Public repository/source availability; own hosting costs remain separate |
| Current remote tool synchronous waits cap at3seconds; commands can continue | Durable job admission with stable UUID and explicit status/output | Completion survives client disconnect and engine replacement |
| Existing remote connector already has asynchronous call recovery | Preserve job results in SQLite independently of the transport receipt | Retry keys create one command and reject changed arguments |
| Process offset0 means new unread output, file offset0 means beginning | Byte offset0 always means beginning | Repeat offset returns same retained bytes |
| Completed process handles disappeared during our earlier session; exact cause unproven | Store job metadata and bounded output after exit | Fast success/error and reconnect tests |
| Existing TOC edit schema uses file_path while validation expects path | One discovery/validation/dispatch registry | Schema-correct edit and stale-hash rejection |
| TOC approvals are memory-resident | SQLite approval records with expiry and exact arguments | Restart and duplicate-decision contracts |
| Existing TOC browser engine is Chromium only | Playwright engines plus W3C WebDriver routes for branded browsers | Actual Safari test still required; protocol fixture is insufficient |
| Full authorized shell execution is not contained by allowedDirs/blocklists | Explicit host grants plus separate worker/container/VM design | Deployment-specific containment qualification |
| Agent UI on a shared desktop can move the owner's pointer | Headless browser workspace with separate input; isolated native worker route | Actual concurrent browser/owner workflow, then native isolation tests |

Current remote pricing lists 10,000 tool calls/month in the free tier and $20/month plus applicable VAT for Pro. Those limits are commercial terms for that service, not a reason to remove safety and resource controls from a self-hosted tool. The local project has no monthly account limit. These terms may change.

No claim is made that RDC has fewer defects overall, supports every device function, or is faster than Codex. This alpha implements measurable improvements and records remaining work. Old upstream issue reports are regression ideas, not proof that current releases still have every reported defect. In particular, closed device-affinity and Windows file-handle issues must not be presented as current failures.

## Primary references

- [Pricing](https://desktopcommander.app/pricing/)
- [Plan limits](https://desktopcommander.app/help/account-billing/plans-and-tool-call-limits)
- [Remote project and proprietary implementation boundary](https://github.com/desktop-commander/remote-desktop-commander)
- [Local project](https://github.com/wonderwhy-er/DesktopCommanderMCP)
- [Local security policy](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/main/SECURITY.md)
- [Local privacy policy](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/main/PRIVACY.md)
- [Local MIT license](https://github.com/wonderwhy-er/DesktopCommanderMCP/blob/main/LICENSE)
- [Remote repository license](https://github.com/desktop-commander/remote-desktop-commander/blob/main/LICENSE)

