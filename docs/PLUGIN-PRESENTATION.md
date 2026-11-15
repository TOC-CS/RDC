# RDC plugin presentation

Status checked on 2026-11-15. The public source package contains the proposed branding below. The connected private App's description already credits TOC Ministries, while its generic icon and developer label remain unresolved. **Source branding does not establish a change to the installed App's presentation.** The owner has kept both branding requests open and accepts the personal developer name if that change is unsupported. These requests do not block the rest of development. Public directory submission is a separate process.

## Proposed identity and descriptions

| Field | Proposed value |
|---|---|
| Display name | RDC |
| Full product name | Remote Desktop Commander |
| Author and developer | TOC Ministries |
| Short description | Remote Desktop Commander |
| Logo | The existing RDC logo in `rdc/assets/rdc-logo.png` |

The short description is 24 characters, within the documented public submission limit of 30. The display name remains RDC.

### Package description

Remote Desktop Commander by TOC Ministries: a free, MIT-licensed local worker for compatible MCP clients, with files, durable jobs, independent browsers, owner consent, embedded previews, and optional device adapters.

### Long description

Remote Desktop Commander (RDC) is an independent TOC Ministries project: a free, MIT-licensed local worker for self-hosted use with compatible MCP clients. Manage files and durable jobs, use independent browsers, and request saved-password fills with owner consent. The embedded live preview requires MCP Apps support; display modes depend on the host. Optional Android ADB and Appium adapters support configured Android, iPhone, and iPad workflows. Appium requires owner device setup, UiAutomator2 or XCUITest, and a compatible driver host. Native input uses the selected device's screen. This portable package requires an installed RDC command and configured worker; owner grants and OS permissions apply.

## Connected App editing constraints

The current Sites editing tool exposes a Site display-title change. Owner-supplied ChatGPT settings screenshots independently show App name and App description editors plus Refresh tools, with no icon or publisher editor. Those UI controls and the package-editing API have different capabilities. Plugin Creator's App-backed update contract permits skills and support-file updates while preserving the App's bindings, name and presentation. It exposes no supported icon or publisher setter for this App. Changing the website's logo or portable `plugin.json` does not establish that the ChatGPT listing or chat activity icon changed.

The documented public publishing workflow supports a primary icon and verified developer identity, but no in-place publishing route preserving this private Sites App's identity has been established. Use a supported management or ownership-preserving submission route for the existing App when available. Do not replace its connection, create a duplicate wrapper, change the global account profile, or invent metadata fields to bypass the editing limit. Refresh tools is a tool/resource metadata action; it has not been shown to change this App's icon or publisher.

## Public distribution

Public directory publisher names come from the selected verified developer or business identity, regardless of the publisher name in the ZIP. Publishing as TOC Ministries would require the appropriate verified business identity and the applicable submission checks. This is separate from private App presentation and does not require changing the user's general ChatGPT profile as a substitute.

Each owner must connect their own worker, credentials, and devices. The current private connection is not a public multiuser service. Mobile driver setup, OS permissions, compatible MCP transport, and MCP Apps host support remain requirements. Live hardware and host-rendering qualification are recorded separately in [verification](VERIFICATION.md) and [mobile setup](MOBILE.md).

## Official references

- [Connect and test your plugin](https://developers.openai.com/plugins/deploy/connect-chatgpt), tool/resource metadata refresh and host verification.
- [Upload and submit your plugin](https://developers.openai.com/plugins/deploy/submission), publishing identity and listing fields.
- [Plugin submission errors](https://developers.openai.com/plugins/deploy/submission-errors), developer identity defaults and presentation limits.
