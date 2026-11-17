# Authorized livestream comments and AI responses

**Status:** READY FOR ATLAS REVIEW for the reusable local control and mock-provider adapters only. Platform OAuth, account authorization and actual live platform operations remain OPEN.

The desktop master plan added requirement 9: the presentation AI agent should read, draft and respond to livestream audience comments, using the user's explicitly authorized credentials, across supported social and broadcast platforms.

## Design

The optional LiveCommentsController in src/live-comments.mjs keeps one provider and one stream bound to an authorized connector. It supports read-only, assisted and automatic modes. Reading cannot publish. Drafting uses a caller-supplied AI response generator. Posting requires all of the following: an explicitly armed mode, a separate host-level live-comment-posting grant, a per-comment provider/stream authorization decision and an approved moderation callback for autonomous responses.

Other protections: deduplicated message IDs, own-channel exclusion when a trusted author ID is configured, rate limits, bounded history, source checks, unique outbound request IDs, and an uncertain-send hold that prevents repeat posting. An ambiguous send counts against the posting rate cap; the agent never silently retries it. Comment content is untrusted input to the AI reply generator.

The operator or AI host calls live_comments_read, live_comments_draft, live_comments_status, live_comments_mode, live_comments_arm and live_comments_reply after injecting an authorized controller into createMcpHandler. Live comments tools return unavailable by default. Read-only presentation API credentials alone cannot authorize public posts. Autonomous response passes may be triggered by a separately configured host loop; merely connecting an account does not start a background comment publisher.

## Platform-specific status

| Service | Current adapter | Actual account verification |
| --- | --- | --- |
| YouTube Live | Official liveChatMessages list and insert REST endpoints, OAuth tokens supplied at action time by a connected host; message polling respects pollingIntervalMillis | No real account or event tested |
| Facebook Live | Official Graph API v27.0 live-video comments GET with Page token supplied by host; this specific live-video comments edge does not expose a create operation | No real account or event tested |
| TikTok Live | No official verified live comment read/write adapter | Unavailable |
| Instagram Live | No verified read/write adapter | Unavailable |
| Zoom | Meeting chat and livestream comments require distinct authorized application interfaces | Unavailable |
| Microsoft Teams | Graph channel/chat messaging has separate permissions and endpoint semantics; no live-stage-specific adapter validated | Unavailable |
| Other services | Adapter registration is possible through a host-provided and separately verified connector | Unavailable until integrated |

YouTube liveChatMessages.insert publishes a **new live chat message**, not an API-level threaded reply to an existing live message. The connector retains the triggering comment ID for local correlation, but does not invent a threaded reply relationship.

No access token is stored in project files, model prompts, tool request arguments, or output logs. getAccessToken is an action-time callback supplied by the host's authorized account connector. Never infer permission to post from permission to read.

## Tests

- node --test tests/live-comments.test.mjs tests/live-comments-mcp.test.mjs
- node --test tests/youtube-comments.test.mjs tests/facebook-live-comments.test.mjs
- npm test

All tests use fake HTTP responses or fake connectors, never real social accounts. Credentials inside fixtures are synthetic non-functional placeholders.

## Official APIs used for adapter contract research

- YouTube liveChatMessages list: https://developers.google.com/youtube/data/live/reference/rest/v3/liveChatMessages/list
- YouTube liveChatMessages insert: https://developers.google.com/youtube/data/live/reference/rest/v3/liveChatMessages/insert
- Facebook Live Video comments: https://developers.facebook.com/docs/graph-api/reference/live-video/comments/
- Microsoft Graph send chatMessage: https://learn.microsoft.com/graph/api/chatmessage-post

## Remaining work

Attach real user-selected providers through supported OAuth connectors and granted scopes, verify app review/permission availability, implement a resilient event subscription or platform-respecting polling loop, inspect live comments under authorization, rehearse AI drafting and optional reply approval, validate repeated messages and rate limits, and test actual display/voice synchronization. When a service lacks a supported publishing API, preserve a draft-only mode instead of inventing access.

Mark whole-project and real-platform acceptance OPEN until verified and accepted by Atlas.
