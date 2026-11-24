# Saved-password workflow

Use the broker's opaque configured aliases. It is a targeted password-fill route, not an agent-readable password vault.

## Agent sequence

1. Call `rdc_credentials_list {}`. Read `credential_id`, the owner-chosen label, and permitted origins. An alias with `requires_reenrollment: true` cannot fill; let the owner remove and re-enroll it using the local owner-only CLI, without exposing its native locator. An empty list means no alias is configured; ask the owner to configure the intended alias privately instead of searching password stores.
2. Use the browser observation tools to confirm the intended HTTPS site and obtain a fresh `session_id`, `observation_id`, and password-control handle.
3. Call `rdc_credentials_request` with `credential_id`, `session_id`, `observation_id`, `password_handle`, and a stable `idempotency_key`. Add `_rdc_request_id` only on the cloud schema that requires it.
4. Recover any gateway `operation_id` first. From the broker result, save `request.id` and poll `rdc_credentials_status {request_id}`. Do not replace the request after a timeout or interrupted fill.
5. Let the owner decide using the local owner-only CLI. Allow Once is consumed for one request. Always Allow persists a grant for the configured credential, worker, exact HTTPS origin, and provider mapping. Deny leaves the password unfilled. Revocation is an owner operation.
6. Verify successful fill through redacted status or an appropriate nonsecret observation. Filling does not submit the form or authorize subsequent account actions.

Existing valid grants can avoid a new RDC consent prompt. A different site, alias, provider mapping, or worker requires appropriate owner authorization. Review/trusted mode for general actions does not override this credential consent.

## Preserve the private boundary

Do not read, print, request, export, or insert passwords into ordinary model-visible tool arguments. Do not collect native provider locators or owner tokens. Do not use shell commands, vault database extraction, clipboard operations, owner routes, or OS prompt automation to bypass the broker.

The worker validates the real page origin and fresh password input before lookup and again before filling. Redirected documents, stale observations, mismatched origins, revoked grants, and paused input can prevent the fill. A pending or uncertain request after worker restart is not automatically replayed. An already admitted input may finish before a concurrent pause or revoke takes effect.

Closing the owner consent view leaves unrelated jobs and browser sessions alive. Native OS authentication, biometrics, or device unlock may require owner interaction outside the embedded preview. Continue independent authorized work while waiting.

Treat `pending` as awaiting owner consent. An `executing` request may be waiting for native authentication; poll the same request and leave that prompt to the owner. Do not create a replacement request to accelerate a wait.

## Respect private capture refusals

Verify a fill through redacted status and observations. A filled input remains private through ordinary same-element Show password changes. Use RDC's normal screenshot or preview path, which rechecks document sensitivity at capture time without requiring an intervening observation. After a private fill, Playwright masks all inputs and marked private elements in that document; expect those image regions to remain hidden.

Treat `screenshot_redaction_required` or `screenshot_failed` as unavailable visual evidence. WebDriver refuses capture of a document that received a private fill; Playwright can refuse when the sensitivity check or native masking cannot be confirmed. Never bypass that refusal with desktop capture, another driver, raw browser calls, shell screenshots, or an unmasked image. Continue with redacted state. Navigate to a fresh document only when the authorized workflow permits it, then use the normal RDC capture path.

## Current provider boundaries

The macOS provider requires a version 2 mapping to an owner-selected classic Keychain file and one exact HTTPS origin. It rejects ambiguous server/account matches and mismatched protocol or port before reading a password, then uses the same retained native item reference. Older mappings require owner re-enrollment. This route does not provide unrestricted Apple Passwords or iCloud Keychain access. The Windows provider targets one configured generic Credential Manager entry; it does not expose arbitrary browser vaults and does not itself create a Windows Hello prompt.

For `credential_item_not_found`, `credential_item_ambiguous`, or `credential_item_mismatch`, let the owner correct the private mapping or selected saved item. Do not widen the search or choose the first match. Avoid editing that saved item while a fill is pending: the native metadata check is a point-in-time preflight, and another OS-authorized process can edit the same retained item before its password is read.

Synthetic broker, consent, redaction, and browser fixtures have been exercised. Real saved-password access through native Keychain, Windows Credential Manager, browser password-manager extensions, or mobile providers remains unqualified until separately verified. Preserve actual native prompts and do not claim those providers are ready from fixture results alone.

The destination website necessarily receives a password during fill and can read its own form fields. Redaction does not prove secrecy against a hostile authorized page, arbitrary same-account code, or memory inspection. Do not test this boundary with real user passwords.
