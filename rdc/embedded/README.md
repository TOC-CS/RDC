# Embedded RDC preview

`preview.html` is the self-contained MCP Apps resource served by RDC. It includes
the official `@modelcontextprotocol/ext-apps` client, CSS, and the RDC logo. The
worker does not need Node, an asset server, or a CDN to serve it.

## Rebuild

With Node 20 or newer installed, run these commands in this directory:

```sh
npm ci --ignore-scripts
npm run build
```

The pinned dependency graph is in `package-lock.json`. The build retains bundled
upstream license texts in `THIRD_PARTY_NOTICES.txt`. Keep both generated files in
source distributions. The original project logo remains at `../assets/rdc-logo.png`. The build embeds the checked-in 192x192 branded thumbnail at `../assets/rdc-icon-192.png` to keep the standalone MCP preview small. The full-size logo remains unchanged for native and listing artwork.

## Host contract

`rdc_preview_open` takes the exact visual session ID for this task. The server advertises `ui://rdc/preview-v10.html`; the earlier resource aliases still resolve. The host delivers the original tool invocation and result. An unbound result leaves the view empty, even if an older server returns a last-used session. The viewer does not discover a replacement source. If the host later supplies an explicit valid session ID, it performs one scoped recovery read. Automatic floating waits for a confirmed source, and still requires actual host support.

The resource contains a live image, a source-bound agent cursor only after confirmed pointer movement, and small viewer controls. The parent-bound MCP Apps SDK mediates reads of `rdc_preview_open`, `rdc_preview_frame`, and `rdc_operation_status`. The resource has no account credential and makes no direct network requests. It displays no worker dashboard or command output.

The AI host owns panel placement, size, and dismissal. Expand, Inline, and Float appear only when advertised and use the mode the host returns. Hide, document visibility changes and teardown suspend or clear observation without changing the worker. Reopen resumes the same source. If the host supports `updateModelContext`, dismissing shares the exact binding and any retained operation ID with the agent.

Successful frame reads wait 250–1500 ms before the next request, based on the measured read duration; slower reads retain backpressure. Frame reads are single flight. A frame must match the source and worker before its bounded PNG, JPEG or WebP image can render. A refused capture clears stale pixels. A pending open or frame retains its original ID across hide and reopen. Confirmed expiry permits one fresh read of the same source; uncertain results retain the reference for explicit retry. An expired read without a bound source never dispatches an unscoped open.

## Verification

`tests/test_embedded_ui.py` uses the bundled SDK in a sandboxed iframe and includes a real RDC engine, Playwright browser, and durable job. The tests cover missing or different sources, display modes, lifecycle, privacy refusal, and pending reads. Run a separate acceptance test in each intended host after deploying the matching worker and gateway.
