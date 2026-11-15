# RDC plugin presentation

Status checked on 2026-11-15. The public source package contains the proposed branding below. **The connected private App's listing has not been updated by these source changes.** Public directory submission is a separate process.

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

The current Sites editing tool exposes a Site display-title change. It does not expose publisher, App-logo, or App-description editing. Plugin Creator's App-backed update contract preserves the App's identity, bindings, descriptions, and presentation. Its supported package edits therefore cannot apply this branding to the connected App. Changing the website's logo or portable `plugin.json` does not establish that the ChatGPT listing changed.

OpenAI documents name and logo editing in an App's **Manage** menu when those controls are available. That documentation does not establish a publisher or description editor for this private App. The available tools and documentation were inspected without changing the App, global profile, permissions, or audience. No duplicate App or plugin was created. Use a supported management control for the existing App when available; do not replace its connection or invent metadata fields to bypass the restriction.

## Public distribution

Public directory publisher names come from the selected verified developer or business identity, regardless of the publisher name in the ZIP. Publishing as TOC Ministries would require the appropriate verified business identity and the applicable submission checks. This is separate from private App presentation and does not require changing the user's general ChatGPT profile as a substitute.

Each owner must connect their own worker, credentials, and devices. The current private connection is not a public multiuser service. Mobile driver setup, OS permissions, compatible MCP transport, and MCP Apps host support remain requirements. Live hardware and host-rendering qualification are recorded separately in [verification](VERIFICATION.md) and [mobile setup](MOBILE.md).

## Official references

- [Connecting custom MCP servers in ChatGPT](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt), existing-App name and logo controls.
- [Upload and submit your plugin](https://developers.openai.com/plugins/deploy/submission), publishing identity and listing fields.
- [Plugin submission errors](https://developers.openai.com/plugins/deploy/submission-errors), developer identity defaults and presentation limits.
