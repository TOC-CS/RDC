# Try RDC in a real AI client

Use this sequence after the worker is running and the selected AI client is connected. It separates transport, actual task execution and embedded presentation. Keep the first run inside a disposable workspace with synthetic data.

## 1. Verify the actual connection

Ask the client:

> Use RDC to report the connected device, enabled browser backend and current grants. Do not change permissions. If this is a cloud connection, report its connection status too.

The client must call RDC's actual tools. Reading a README, displaying a mockup or using another desktop connector does not pass this check. Confirm the reported device is the intended one. A missing tool catalog requires connecting the plugin or refreshing the host's tool connection before continuing.

## 2. Exercise the independent browser

Ask:

> Create an RDC browser session with a small synthetic page containing a name field and a greeting button. Use the session ID returned by that browser to open its live preview inside this conversation. Fill the name with RDC, click the greeting button and verify the resulting text from a fresh observation.

Resolve any requested owner review in the local administration page. Confirm that the normal browser and desktop remain usable while the dedicated session changes. Save the full session ID. A separate administration tab or static screenshot does not prove in-chat rendering.

## 3. Check view lifecycle

Exercise the controls the host offers, such as Expand, Inline or Float. Resize the host panel if available. Hide and reopen, then dismiss and reopen with the same saved session ID.

The session ID and page state should remain the same. Start a second test browser and a harmless job through a separate task; the first viewer must keep its original frame source and never show the second task or its output. An open without a source and an ended source must not render the other test browser. No view control should close the browser, cancel a job or stop the worker. The AI host may decline a presentation request; RDC should state the actual resulting mode. Closing the worker itself ends browser sessions and is a different test.

## 4. Check durable work and reconnect

Ask:

> In the disposable RDC workspace, start a harmless command that waits briefly and prints a unique test marker. Save its job ID and retry key. Reconnect the AI client, recover that job and read the output from byte offset zero. Verify the marker, exit code and unchanged job ID without starting a replacement command.

Keep the worker running throughout. A cloud call that returns `pending` must be recovered through `rdc_operation_status` using its original operation ID. Never invent a new request ID to retry an uncertain mutation. File edits should use the latest content hash and be read back afterward.

## 5. Check saved-password consent

Use a synthetic account first. In owner administration, configure the one saved credential alias for its exact HTTPS origin and native provider. Do not paste a password into a chat or a tool argument.

Ask RDC to observe the login form, request filling the selected password field and report the request status. Choose Allow Once in the owner prompt. Confirm the field was filled without a password appearing in the model's observation or result. Filling must not submit the form. Repeat with a fresh request to verify another one-time approval is needed, then exercise a site-specific persistent grant and Revoke.

An OS authentication prompt may still appear. Complete it yourself. Record the real provider and OS version separately from the synthetic broker tests. Modern Apple Passwords/iCloud, password-manager extensions and phone providers are separate integrations; a classic Keychain or generic Windows target cannot certify them.

## 6. Record client and platform evidence

For each run, record the client/version, OS/browser, RDC revision, selected tool transport, passed steps, denied or unavailable host modes and observed failures. Never include credentials, authorization headers, personal browser profiles or private page contents in a public report.

Repeat on Claude using its own connection and model. A successful ChatGPT run does not qualify Claude automatically. Run actual Safari through its configured driver; Playwright WebKit cannot stand in for that test. Windows and physical phone routes need their own devices and normal OS permissions.

## Replacement decision

Use the current connector for workflows whose RDC acceptance check has not passed. RDC can replace the tested workflow once its actual device, client, browser, recovery and permission paths work reliably. Record success rate and end-to-end time on equivalent tasks before claiming a speed or reliability advantage over another product. Hosting and AI-provider costs remain separate from RDC's MIT-licensed source.
