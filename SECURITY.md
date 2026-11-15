# RDC security and capability boundaries

## Deployment model

RDC 0.1 is a single-owner worker. It is not a multi-tenant service. HTTP distinguishes an agent token from an owner token; only owner routes can approve reviews or pause/resume input. Stdio trusts the operating system account starting it. The service binds to loopback and rejects invalid hosts/origins and oversized request bodies. Credentials must never be posted into AI conversations, embedded in URLs, or committed.

Run the worker as a dedicated OS account, container, or VM when it should not inherit the owner's full access. Browser and file-root checks do not confine shell execution. With `allow_exec=true`, a permitted command runs as the worker account and can access or modify that account's private state. Owner and agent HTTP tokens do not provide a privilege boundary against that same account. An owner grant to shell execution must be assessed in that context.

Native `shared` mode uses the active desktop cursor and focus. Native `isolated` mode assumes that a distinct desktop/display/VM already exists. The configuration flag neither provisions nor verifies it. Headless Playwright sessions have separate input and browser profiles, while sharing worker resources and network access.

## Remote connections

Use an authenticated tunnel or HTTPS gateway with correctly configured origin/host policy. Keep the listener private. Direct clients use the agent token. The optional `cloud-gateway` source supplies an owner-private Sites route, and `rdc relay` connects the device outbound using independent Site and device credentials. The private gateway pins the authenticated owner identity; its service credential does not grant a user identity. Preserve that authentication boundary when deploying. Public multiuser OAuth onboarding is unfinished. Do not disable authentication to make a connector accept a URL.

The credential broker exposes only configured aliases, fill requests and status to agents. Owner consent and enrollment remain outside MCP. Persistent grants bind the credential mapping, device and exact HTTPS origin. Native OS prompts still apply. The broker is an application-level control, not protection from fully authorized same-account code or a website reading its own password field. See [credential limits](docs/CREDENTIALS.md).

macOS mappings require an explicit classic Keychain file and a version-2 locator. The private helper requires one matching item in that file and verifies its server/account/HTTPS/port metadata before reading password data from the same retained reference. Older server/account-only aliases require removal and re-enrollment; existing grants cannot bypass that check. This targeted lookup does not grant Apple Passwords/iCloud access, lock the item against another authorized local writer, or establish a signed native broker identity. Synthetic tests cover the selection and C API boundary; actual native credential access remains unqualified.

Browser observations remember a broker-filled element within its document and redact its value after a Show Password type change. Playwright capture independently checks document sensitivity, then masks every input and private-marked field in a credential-sensitive document. This also covers a direct preview after type/marker changes, before another observation. Fresh nonsensitive documents return to normal password-field and marker masking. WebDriver refuses credential-sensitive screenshots. Probe or capture/masking failure returns no image and a fixed public error. These controls cover known fields, not a hostile website copying their values elsewhere or altering page-side tracking. The website necessarily receives the password selected for it.

WebDriver is a privileged local automation endpoint. Configure its URL and capabilities as the owner and keep it inaccessible from untrusted networks. RDC ignores ambient HTTP proxies for driver requests and does not follow redirects. Browsed pages still have full worker network access. Use network isolation when local services must be inaccessible.

When WebDriver creation succeeds but later setup fails, RDC attempts cleanup of that exact session. If cleanup cannot be confirmed, the session remains listed as `cleanup_required` and accepts close only. Inspect and close that session instead of assuming creation was rolled back.

## Data and recovery

Telemetry is absent. No RDC vendor receives commands or files. A chosen cloud AI still receives tool results, page text, screenshots, and any other data returned to it. Review approvals and job logs may contain sensitive command arguments, filenames, and output. Protect the state directory and choose an appropriate retention policy. This alpha bounds each log, not the aggregate disk usage.

The relay records an authenticated `operation_not_found` response to a result upload as `undeliverable`, including for a mutation. This permits unrelated work to continue without claiming delivery or dispatching that operation again. Its original request/result remain local within the payload retention bound; a persistent identity record prevents replay after payload pruning or restart. Other authentication and identity failures retain their stricter failure behavior. Preserve the journal and inspect the worker before another attempt. These identity records have no automatic aggregate retention limit.

Complete MCP protocol rejections are preserved without poisoning later bridge requests. Timeouts and connection loss still require inspection of potentially completed work. Partial stdin delivery is acknowledged only after every byte is accepted and the requested stream closure succeeds. A failed delivery marks the job incomplete even if the child exits zero; input is never replayed automatically.

POSIX state directories use mode700 and token/config files use mode600. Windows profile ACL inheritance needs deployment review. Filesystem roots are a best-effort application policy, not a kernel sandbox. Atomic replacement can change file metadata such as ACLs or extended attributes; use a native job workflow if those must be preserved. Hash preconditions cannot eliminate races with unrelated external writers.

MCP and owner API roles are tested, but this alpha has not had a professional security audit. Avoid putting a publicly reachable full-host worker into production. The user remains responsible for granting device permissions through normal OS mechanisms.

The [2026-11-15 internal audit](docs/AUDIT-2026-11-15.md) separates confirmed repairs, the final frozen 147-test iMac result, synthetic native-provider evidence and unfinished platform/host qualification. Its [receipt](docs/verification-results-0.1.0a2.json) binds the result to 35 unchanged inputs. The timeout-fixture subprocess warning remains a diagnostic limit without PID attribution; a passing suite does not qualify real native credential access or production embedded rendering.

## Reporting

Before a public issue tracker exists, report flaws privately to the repository owner. Do not publish credentials, personal logs, or exploit payloads against other users' workers. Provide the release, platform, minimum synthetic reproducer, observed result, and expected boundary. There is no security-contact address fabricated for this project.

