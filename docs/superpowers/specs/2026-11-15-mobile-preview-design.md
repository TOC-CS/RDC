# Configured mobile sessions and shared preview

The user authorized implementation in the separate `feat/mobile-devices` worktree. This scope extends the existing RDC design and embedded-preview contracts. The independent guardian proposal remains a separate design awaiting approval.

## Scope and selected approach

Add owner-configured Appium profiles for Android and iOS/iPadOS. Agents select a profile alias; they cannot supply endpoints or capabilities. Reuse RDC's engine admission, owner panel and read-only embedded preview instead of adding a separate mobile UI or a second approval system. The alternative of exposing arbitrary Appium capabilities is excluded by the owner-configuration requirement.

`Settings.mobile_profiles` defaults to `{}`. The mobile adapter validates profiles through `validate_mobile_profiles(profiles)`. Public settings omit the complete private mapping. `Adapters.status().mobile` exposes only sanitized profile labels/platform/automation and live session metadata. Mobile IDs are `mobile-<UUID>`; existing job, approval and browser credential IDs retain their current UUID schemas.

The mobile adapter owner implements `Mobile.catalog/call/status/snapshot/close` and adapter dispatch. This integration consumes sessions with `kind: mobile`, `backend: appium`, `platform`, `profile`, logical `width`/`height`, observation ID and an input notice. Observations include native controls with `can_tap`, `can_fill`, `editable`, `secure`/`sensitive`, `disabled` and opaque handles. Screenshots carry native logical coordinates and pixel dimensions.

## Preview and owner experience

The existing preview lists browser and mobile sessions, preserves explicit selection and the existing ended-session/pending-operation recovery, and delegates capture by session ID. Labels show the platform/profile and explain that device input is shared with whoever uses that device. Mobile support does not imply a separate physical cursor or independent device use. Hiding or dismissing the view leaves sessions and jobs running.

The owner panel can start a configured profile, observe, tap an observed control, fill an allowed ordinary text field, swipe within the reported logical viewport and close the selected mobile session. Browser navigation, keyboard entry, image-coordinate takeover and browser credential selection are unavailable for native mobile sessions. Secure fields have no fill or saved-password control. A privacy refusal hides the image and explains its state without marking a reachable worker disconnected.

An ended native driver or retained setup failure stops automatic captures and preserves the exact RDC record for owner cleanup. The embedded view allows an explicit read-only retry, without starting or closing anything. Unknown creation directs the owner to inspect Appium before restarting RDC; the owner UI does not offer Close when no exact driver identity exists. Other verified-capture failures hide the old image and remain separate from worker connectivity.

## Boundaries and qualification

- No automatic device discovery, arbitrary endpoints/capabilities, permission changes or native mobile saved-password broker.
- Default unconfigured state stays disabled. Existing agent review/pause gates apply to mobile mutations; owner actions remain owner-authorized.
- Browser behavior and credential consent remain covered by their existing contracts.
- No version changes, gateway asset synchronization, main-checkout changes, commits or live device calls in this task.
- Mocked engine, adapter and UI evidence qualifies integration only. Real Android/iOS/iPadOS devices, Appium permissions and actual host rendering require separate qualification.

