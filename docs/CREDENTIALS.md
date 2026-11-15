# RDC credential broker

Status: the credential broker and owner enrollment are implemented. The final **0.1.0a2 iMac suite passed 147 tests in 55.091 seconds with no skips**, including explicit Keychain selection fixtures and the real Chromium direct-screenshot masking pixel check. All 35 recorded inputs matched the manifest and remained unchanged; see [release verification](VERIFICATION.md) and the [receipt](verification-results-0.1.0a2.json). No real Keychain or Windows credential store was opened. Native credential access and OS prompts remain unqualified.

Historical evidence includes the 101-test iMac broker baseline in 65.014 seconds, its 16 credential tests, the owner modal and a real Playwright private fill. The corresponding Linux suite ran 86 tests in 27.406 seconds with five environment/browser skips. Later historical combined results are preserved in the verification record. The earlier 59-test core snapshot predates the broker.

## Design decision

RDC requests a saved password through an owner-authorized broker on the worker. The agent selects an opaque configured credential ID and a freshly observed password field. The owner chooses **Allow Once**, **Always Allow for this site**, or **Deny** in the existing owner administration page. Persistent grants can be revoked there. Native operating-system authentication remains active when required.

The selected approach combines a narrow broker with existing platform credential services. Browser-provider autofill is a later adapter because a fresh isolated browser does not automatically inherit the owner's password-manager session. Direct browser-vault database extraction and bulk export are excluded. A dedicated RDC credential vault would require a separate enrollment workflow and remains a possible future provider.

## Implementation

1. `rdc/credentials.py` owns the three-tool agent contract, SQLite request/grant state and targeted native providers. The broker consumes one-time permission atomically and retains request outcomes for recovery. Its private `rdc/_keychain_helper.py` resolves an explicitly selected classic Keychain item before reading a password.
2. Private browser adapter methods validate the actual HTTPS origin, document observation and enabled password input before lookup and again before filling. The final field validation and value assignment occur in one browser JavaScript turn. Password bytes stay outside generic tool arguments, approvals, results and logs.
3. Owner-only credential routes extend the existing authenticated server. A modal and grant list extend the existing owner administration UI. The agent catalog cannot approve, revoke, or reconfigure a credential.
4. Synthetic tests exercise consent, origin changes, replay, revocation, pause, driver/provider error redaction, restart, the real browser fill and the permission modal. Independent review reproduced an initial-validation error-text leak and leftover modal metadata after disconnect; both were corrected with regression tests and re-reviewed.

Native lookup runs away from the browser's owning thread, so an operating-system authentication prompt does not block ordinary browser preview/status polling. Consent and pause are checked again after browser validation, immediately before native lookup, and before input. Existing jobs and browser sessions keep their existing lifecycle when the owner dismisses the permission view.

## Agent and owner interfaces

| Interface | Purpose |
|---|---|
| `rdc_credentials_list {}` | Lists configured opaque IDs, safe labels and permitted origins, with re-enrollment guidance for older macOS mappings. Native locators remain private. |
| `rdc_credentials_request {credential_id, session_id, observation_id, password_handle, idempotency_key}` | Requests one password fill, returning a request ID and redacted state. |
| `rdc_credentials_status {request_id}` | Reads the persisted request state without revealing the password. |
| `GET /api/credentials` | Owner view of requests, aliases and grants. |
| `POST /api/credentials/enroll {label, origin, provider, locator}` | Owner enrollment of one existing native credential locator; generates an opaque UUID. |
| `POST /api/credentials/remove {credential_id}` | Owner removal of a mapping, invalidating its grants and unadmitted requests. |
| `POST /api/credentials/decision {request_id, decision}` | Owner choice `once`, `always`, or `deny`. |
| `POST /api/credentials/revoke {grant_id}` | Owner revocation of one persistent grant. |

Agent requests never contain passwords or provider locators. A request ID identifies a status record, not an authorization capability. `trusted` operation mode does not bypass credential consent. A grant binds the worker device ID, opaque credential ID, canonical HTTPS origin and current provider mapping. Each request separately binds the session, document observation and password handle. A changed mapping requires a new grant. Existing requests are interrupted on worker restart and are never automatically replayed.

## Enroll a credential in owner administration

Connect to the existing owner administration page and use its credential configuration section. Enter a safe **Credential name**, the exact HTTPS **Website origin**, and the **Native provider**. For macOS, enter the **Keychain file** containing the existing item and supply its **Keychain server** and **Keychain account**. The form suggests `~/Library/Keychains/login.keychain-db`; change it when the item belongs to another classic Keychain file. Enrollment expands an explicitly entered `~/` path for the worker account and saves an absolute path. Relative paths and another user's `~name` shorthand are rejected. For Windows, supply the generic **Credential Manager target**. The form never asks for the password. It generates the opaque credential ID and saves the locator to a private regular mapping file atomically, with mode `600` on macOS/Linux.

Enrollment validates configuration only. It does not read the vault, verify that the native item exists, alter OS permissions or grant permission to fill a password. A later fill request still needs Allow Once or a matching Always Allow grant. The first native lookup can reveal that the entry is missing, unavailable on this platform, locked, or requires additional OS authentication.

The owner can remove a configured alias in the same section. Removal invalidates its persistent grants and requests that have not been admitted. Removing an alias or revoking a grant does not erase a password already entered into a page or sign out an existing website session. Those remain subject to normal browser and account controls.

### Upgrade older macOS mappings

An older locator containing only `server` and `account` remains listable and removable with `requires_reenrollment: true`. Requests and decisions using that locator fail with `credential_reenrollment_required` before native lookup. Remove the old alias in owner administration, then use **Add saved credential** with the selected Keychain file to enroll it again. The new alias needs its own fill consent. Existing Windows aliases remain usable under their normal consent rules.

## Advanced private mapping file

The owner form maintains `credential-locators.json` inside the initialized worker's state directory. Advanced owners can also edit that file privately. With no file, the tool lists no credentials and the rest of RDC works normally. Use a regular file owned by the worker account, with mode `600` on macOS/Linux. Keep Windows state restricted to the intended account. RDC's file tools exclude the entire state directory.

For a classic macOS Keychain internet-password item, the mapping has this shape. The outer file format stays at version `1`; the macOS locator uses version `2`. The example names are synthetic; replace them privately with the selected absolute Keychain file, exact existing item server/account, and intended website origin:

```json
{
  "version": 1,
  "credentials": [
    {
      "id": "5fa92907-4a83-4fe4-81a4-3a2af7267cef",
      "label": "Example work account",
      "origins": ["https://example.test"],
      "provider": "macos-keychain",
      "locator": {
        "version": 2,
        "keychain": "/Users/example/Library/Keychains/login.keychain-db",
        "server": "example.test",
        "account": "example-account"
      }
    }
  ]
}
```

Choose a stable UUID for each credential. The label and allowed origins are visible to the connected agent, so use a safe label. The native locator remains private. HTTPS origins are exact: scheme, hostname and port must match; arbitrary paths, wildcard hosts and HTTP origins are rejected. Each version-2 macOS locator accepts exactly one HTTPS origin, and its server must match that origin's host. Use an absolute Keychain path in a manually edited mapping; home-path expansion belongs to owner enrollment.

For a Windows generic Credential Manager item, replace the provider and locator in an entry with:

```json
{
  "provider": "windows-credential-manager",
  "locator": {
    "target": "RDC/example-account",
    "encoding": "utf-16-le"
  }
}
```

The target must identify an existing, intentionally selected generic credential whose blob contains the password. UTF-16LE is the default; `utf-8` is also accepted. Unsupported binary credential blobs are rejected. Neither example contains a password, and no password belongs in this mapping file.

The broker reloads mappings for requests and execution checks. Changing a mapping invalidates matching old authorization for future input. In the owner page, observe a login form and choose a configured alias under its password field, or let the agent request the fill. The permission modal identifies the alias, actual origin, worker and browser session. Use **Later** or Escape to defer a request, then **Review credential** to reopen it. The grant list provides **Revoke**. Usernames remain ordinary browser fields in this initial version.

On a private gateway connection, a credential request has both its core `idempotency_key` and the cloud `_rdc_request_id`. Preserve both and recover pending cloud operations by `operation_id`; do not issue a new credential request merely because a transport response was delayed.

## Platform boundaries

### macOS

The provider launches a fixed private helper through isolated Python. Locator and origin metadata travel over private stdin, and password bytes return to the broker through its private stdout pipe. The helper opens only the selected classic Keychain file. It searches that file for the configured server/account, inspects at most two matching item references, and requires exactly one. It then reads metadata without requesting secret data and checks server, account, HTTPS protocol and the effective port against the permitted origin. Native port `0` is accepted only as the HTTPS default, `443`.

Only after those checks does the helper request password data from the same retained item reference. Missing, ambiguous and mismatched items return fixed errors without a password read. There is no default-Keychain search, broad second lookup, ACL change or OS prompt automation. System prompts remain under macOS control. The retained reference avoids selecting another search result; it does not lock the item against changes by another authorized local process between the metadata and password calls.

The helper has a 90-second timeout, suppresses native diagnostic output and reports fixed public failure codes. It preserves password bytes, including a trailing newline, and clears the native and mutable helper buffers it owns. Python/browser string copies remain subject to the practical limits below. Unavailable native APIs fail closed. Actual macOS API execution, saved-item lookup and OS prompt behavior remain unqualified by the synthetic tests.

| Result | Owner action |
|---|---|
| `credential_reenrollment_required` | Remove the older alias and enroll it with a specific Keychain file. |
| `credential_item_not_found` | Check the selected file, server and account privately. |
| `credential_item_ambiguous` | Select a file/account combination with one matching internet-password item. |
| `credential_item_mismatch` | Check the saved item's HTTPS protocol, server, account and port against the configured origin. |

Apple documents Allow, Always Allow and Deny for classic macOS Keychain ACLs, but explicitly excludes iCloud Keychain and iOS from that ACL model. Data Protection and synchronizable items use access groups. An RDC grant therefore does not grant general access to Apple Passwords or iCloud Keychain. Apple Password AutoFill also requires user consent and associated app/domain relationships for native app credential sharing. [Apple ACLs](https://developer.apple.com/documentation/security/access-control-lists), [Keychain access groups](https://developer.apple.com/documentation/security/sharing-access-to-keychain-items-among-a-collection-of-apps), [App access to saved passwords](https://support.apple.com/guide/security/sec8762eb992/web).

A native signed broker with a stable app identity remains future work. The private Python helper does not install that identity. Owners should assess the OS prompt actually presented; RDC must never automate an OS approval or change a Keychain ACL to allow every app. Apple documents per-item user-presence controls that can require authentication on each read. [Apple LocalAuthentication](https://developer.apple.com/documentation/localauthentication/accessing-keychain-items-with-face-id-or-touch-id).

### Windows

The initial provider uses `CredReadW` for one owner-configured generic Credential Manager target in the current logon session. This API does not supply arbitrary Chrome or Edge vault entries. Credential bytes are copied for the private fill, then native buffers are cleared and freed. Windows support must be qualified on an actual Windows host. [Microsoft CredReadW](https://learn.microsoft.com/en-us/windows/win32/api/wincred/nf-wincred-credreadw).

The broker's owner consent is distinct from Windows Hello. `CredReadW` itself does not create a Windows Hello prompt. A future native owner-authentication provider may use supported Windows credential or WebAuthn flows. A generic credential collection prompt must not be advertised as a secure-desktop prompt: Microsoft explicitly disallows combining `CREDUIWIN_GENERIC` with `CREDUIWIN_SECURE_PROMPT`. [Microsoft credential UI](https://learn.microsoft.com/en-us/windows/win32/api/wincred/nf-wincred-creduipromptforwindowscredentialsw).

### Browser and mobile providers

Chrome's `passwordsPrivate` permission is restricted to component extensions. An ordinary RDC extension cannot use it as a public password-vault API. Chrome supports native messaging for an installed extension and registered native host, with an exact extension allowlist and sender-origin validation. A future RDC extension can use that channel for its own narrow broker, not to bypass a provider's vault protections. [Chromium permission definitions](https://chromium.googlesource.com/chromium/src/+/main/chrome/common/extensions/api/_permission_features.json), [Chrome native messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging).

Safari and Google Password Manager have supported autofill flows, including configured Touch ID, screen-lock or Windows Hello checks. Apple also supplies iCloud Passwords extensions for supported third-party browsers. These are valid future handoff routes, but their operation in RDC's isolated browser profiles is untested. [Safari AutoFill](https://support.apple.com/guide/safari/ibrwf71ba236/mac), [Google Password Manager](https://support.google.com/accounts/answer/95606), [Apple browser extensions](https://support.apple.com/guide/passwords/mchlf7ac261e/mac), [iCloud Passwords on Windows](https://support.apple.com/guide/icloud-windows/icw2babf5e03/icloud).

iOS and Android credential providers remain separate future adapters. No universal mobile vault access is claimed. Native OS authentication can require an operating-system window, biometric action or device unlock outside the embedded AI preview. A waiting login should leave unrelated background jobs running.

## Security and practical limits

Passwords must never appear in MCP responses, ordinary tool arguments, the approvals database, job logs, URLs, command lines, clipboard contents, or public configuration. Provider/driver exceptions use fixed public error messages so an exception cannot echo a password. The private mapping file is excluded from RDC file access and public packages.

Observations remember each broker-filled input for its current document, so a Show Password control cannot expose its value by changing the input type. An observation restores the input's private marker if an ordinary page update removed it. Playwright capture checks document sensitivity independently of observation and uses native black masks over every input and private-marked field in a credential-sensitive document. Other form inputs are deliberately hidden too. This protects a direct preview even if the filled input changed type and lost its marker before another observation. A fresh nonsensitive document returns to normal password-field and marker masking. Probe or capture/masking failures return no image.

WebDriver screenshots return `screenshot_redaction_required` for a document that received a broker credential, because safe masking is unavailable through that route. Capture resumes after navigation to a fresh document that reports no broker-filled fields.

The browser necessarily receives a password when it fills the selected website. The website can read its own form fields, copy their values elsewhere or alter page-side tracking. These field protections cannot establish secrecy from an untrusted or compromised authorized website. A full-power shell running as the owner's account can also bypass application-level boundaries. This initial broker cannot promise secrecy against arbitrary same-account code or memory inspection. A stronger boundary requires an isolated native broker/account and restricted browser capabilities. Python and browser IPC may retain temporary string copies; clearing the broker's byte buffer is best effort, not verified memory erasure.

Allow Once is consumed atomically for one request. An uncertain fill is recorded and never retried automatically. Revocation or pause prevents a lookup or input that has not crossed its corresponding admission check; an already-admitted operation may finish. A grant is checked again before input even if a native lookup has already started. Closing the consent modal defers the request without cancelling jobs or browser sessions. Filling does not click Submit or authorize later account actions.

## Verification coverage and remaining qualification

- No provider read before consent; `trusted` mode still requires credential consent.
- Wrong origin, non-password input, stale observation, redirected document and unsafe driver transport fail before a secret is read or filled.
- Concurrent owner decisions and request retries cannot duplicate one fill.
- Persistent grants match only the intended credential, device, origin and provider mapping; revoke and pause are checked before filling.
- Provider and driver exceptions containing a synthetic password do not expose it in responses, request/grant records or logs.
- A fresh real browser fixture receives the synthetic password while ordinary observations remain redacted; the independent session continues after the modal closes.
- Privacy fixtures cover Show Password redaction, direct capture before another observation, native mask arguments, WebDriver capture refusal and private exception cleanup. The real Chromium pixel check passed on the iMac in the final 147-test run. The local container's earlier socket-denial skip remains an environment limit.
- Agent tokens cannot use owner enrollment, removal, decision or revocation routes; owner state clears on disconnect.
- Enrollment validates and stores a locator without reading a secret or authorizing input; removal invalidates future use.
- Synthetic native-API fixtures verify explicit Keychain selection, unique-item resolution, metadata-only inspection before secret access, exact HTTPS/port checks and reading from the same retained reference. They do not qualify the real macOS ABI or vault.
- Older macOS locators remain visible for removal but fail before native lookup; a legacy alias does not disable separately configured Windows aliases.
- A worker restart never replays a pending or possibly completed secret fill.

Use synthetic credentials for automated tests. Actual native Keychain, Windows Credential Manager, browser-provider and mobile qualification must be reported separately.

The 101-test iMac baseline also included the then-current 22 outbound-relay tests and embedded-preview lifecycle tests. It emitted the previously recorded subprocess cleanup ResourceWarning in the command output-capture timeout test; all assertions passed. The Linux environment required a writable task-local `TMPDIR`; its browser skips do not establish a Linux browser execution result. Actual production ChatGPT/Claude rendering and tool-identity branding remain separate host acceptance checks.
