# Durable local presentation session over RDC

The AI Presentation Agent has a standalone session manager for authorized local execution. The managed service keeps a single presentation director alive across separate RDC command jobs, BandMates cue messages and AI voice messages. It is optional. The existing RDC worker and its gateway remain independent.

## Start and connect

From the independent AI Presentation Agent source directory, start a durable background process with node scripts/managed-server.mjs. An operator-controlled launch may additionally set PRESENTATION_ALLOW_EXTERNAL_CONTROL=1 only when the appropriate app-specific permissions have been granted. The ordinary managed service leaves external writes disarmed.

The service binds an OS-selected loopback port. It generates separate control and viewer credentials using a secure random generator and stores them in a regular, owner-only control.json file under ~/.local/state/ai-presentation-agent. It prints no tokens. The state directory must be owner-only; symlinks and permissive state paths are rejected. When a second service tries to reuse the same state, the exclusive file create prevents it from replacing the existing session. A clean SIGTERM or SIGINT removes its own credential file.

Using RDC's existing supported durable command mechanism, run node scripts/presentationctl.mjs status, capabilities or readback. This CLI retrieves the local token from the owner-only file and makes authenticated requests. The AI tool argument list, output and chat never need a token. For instance:

- node scripts/presentationctl.mjs load --file /absolute/path/to/deck.json
- node scripts/presentationctl.mjs start automatic
- node scripts/presentationctl.mjs cue --file /absolute/path/to/authorized-cue.json
- node scripts/presentationctl.mjs voice --file /absolute/path/to/authorized-voice.json
- node scripts/presentationctl.mjs next
- node scripts/presentationctl.mjs hold
- node scripts/presentationctl.mjs resume

Use one managed server to preserve the director state. Invoking a new single-shot process for every MCP command would construct a fresh in-memory director, so it cannot preserve the existing session.

## Stopping a running presentation

node scripts/presentationctl.mjs stop stops and disarms the local PresentationDirector. The last slide stays in the deck for inspection, and a new owner-authorized start can begin later. It does not issue a native projector-screen blank or application quit command; the output operator is responsible for actual venue screen blanking. To terminate the managed server itself, signal its exact owner job as described below.

After stop and disarm, node scripts/presentationctl.mjs unload clears the deck and deletes the private last-known.json checkpoint. A subsequent crash restart cannot restore those finished slides. The server refuses unload during a running or armed presentation; it reports a storage error if the private checkpoint deletion fails, allowing a safe retry once repaired. The authenticated browser viewer then clears the previous slide DOM and shows PRESENTATION CLEARED. This does not blank a physical projector source that is still selected in a third-party app.

## Private browser output

When a deck is loaded, node scripts/presentationctl.mjs viewer-check verifies the authenticated local read-only viewer. To prepare an operator-openable browser output, use:

node scripts/presentationctl.mjs viewer-export --file /absolute/private/directory/stage-view.html

The HTML launcher contains a read-only viewer credential, stored with owner-only file permissions. The CLI returns only the local filename, not the token or URL. Only open that file in the operator's intentionally selected browser or output computer. The server is bound to the local host; a different venue computer or OBS machine needs a separate approved, authenticated network viewer bridge.

## Owner-only crash recovery and restart

A serialized last-known.json checkpoint is stored beside control.json with owner-only 0600 permissions. It contains only the presentation deck, last local slide index, schema and timestamp. It excludes both bearer tokens and previous external-output grants. Unchanged cues do not rewrite this checkpoint.

If the managed process terminates abnormally, a subsequent launch can remove the stale control.json **only after verifying the old PID is no longer alive**. A private lock protects against two new processes racing to take ownership. An existing running session, invalid PID, unsafe permissions or a locked recovery are refusal conditions, never reasons to force-delete someone else's session.

On restart, the recovered slide is visible in **RECOVERED PREVIEW** state: started=false, held=true, armed=false. This indicates the last known local position only. Do not automatically issue next, goto or a rearm request. A new explicitly authorized start begins at the first slide; true position recovery in a native external application requires app-specific independent readback and operator resynchronization.

For troubleshooting, inspect only status and the private state folder's owner permissions. Never print control.json, last-known.json contents, or viewer URLs in chat. An owner may explicitly delete the saved last-known.json after a finished service if retaining presentation content is undesirable. The service never launches an app or captures a microphone merely to restore a checkpoint.

## Operation and recovery

When a worker job is pending or outcome unknown, retain its job ID and original request identity. Inspect job status and director state before deciding whether to resend anything. Avoid repeating next, previous or native output operations after an ambiguous result. A retryable BandMates event should use its retained event ID.

When the owner requests the service to end, cancel its exact durable worker job or signal the exact managed-server process and independently verify that control.json was removed. Do not kill unrelated RDC, BandMates, MIDI or audio processes. Avoid automatically launching or activating a native presentation app on the owner desktop.

## Verified scope

The unit and cross-process test suite verifies owner-only state, duplicate service prevention, cue/voice state continuity and cleanup. In a real ChatGPT RDC cloud tool session, separate job calls loaded a demo deck, started automatic mode, advanced and held/resumed slides, delivered a BandMates chorus cue, and processed a host voice command with the correct continuing state. The temporary service was canceled and the control file was confirmed absent. The private live viewer was tested using isolated headless Chrome and Apple Vision OCR on synthetic slides.

These are software-path validations. They do not certify physical projection, live microphone/camera capture, actual OBS/ProPresenter operation, chat host voice streaming, or end-to-end latency.

## Stable command identities across resumed RDC jobs

Optional --request-id ID is accepted on presentationctl next, previous, hold, resume and goto. Use the same exact stable ID when recovering an uncertain RDC job result. presentation_command accepts the corresponding idempotencyKey in authenticated MCP/HTTP calls. Distinct actions require distinct IDs. Duplicate voice events also need a stable eventId from the primary AI host to suppress repeated slide changes and repeated speech. Do not automatically reissue commands with a new ID after a timeout.
