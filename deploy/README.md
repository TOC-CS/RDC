# Linux isolated worker recipe

This optional recipe gives RDC its own Linux virtual display, browser processes,
workspace volume, and input stream. Your host's desktop stays available because
neither its display nor its input devices are mounted. The Docker image and native
Xvfb input route require qualification on your own Docker host; see the evidence
labels in [platforms.md](../docs/platforms.md).

From the repository root:

```sh
docker compose -f deploy/compose.yaml up --build -d
docker compose -f deploy/compose.yaml exec worker rdc owner-token --state-dir /home/rdc/state
```

Open `http://127.0.0.1:8765/` on the host and paste that owner token. The token
command prints a credential: keep it out of chat, screenshots, and committed files.
The compatible AI host opens an optional embedded live view. A new Chromium session runs headlessly
and has no access to your ordinary browser profile. Firefox and WebKit require
installing their Playwright binaries in a derived image.

The service runs as an unprivileged user, retains private state in `worker-state`,
and retains files in `worker-files`. It uses `xvfb-run` with an Xauthority cookie,
X11 TCP disabled, and no host X11 socket, privileged mode, host input devices, or
Docker socket. RDC listens on container loopback at port 8766; `socat` forwards
container port 8765 to it. Compose publishes only host loopback port 8765. The
forwarder provides reachability, not authentication or encryption. Both RDC owner
and agent bearer checks still apply.

Shell execution and native input start disabled. To grant native input to this
container's display, set `RDC_DESKTOP_MODE: isolated` before the first initialization.
To grant command execution as the worker account, explicitly set `RDC_ENABLE_EXEC:
"1"`. Existing configuration remains authoritative on subsequent starts. Change
that private configuration deliberately and restart instead of expecting
initialization environment variables to override it. Keep approval mode `review`
for owner review. Test native screenshot, typing, pointer, and owner interruption
against a harmless application before relying on a new host.

The embedded preview observes the selected browser session. Native desktop screenshots and
input are exposed through the adapter tools; a full native desktop video viewer
is outside the embedded viewer. You can launch a GUI application through an
approved terminal job when execution is enabled; it inherits the worker display.

For phone access, retain this local binding and put an authenticated TLS gateway
or private network path in front of it. Configure the exact external HTTPS origin
in `allowed_origins` in the worker's private configuration; RDC checks Host and
Origin as well as its bearer. Do not publish the port to the public Internet or
place credentials in a URL. The gateway and phone path are deployment work, not
an automatic hosted relay. A phone browser controls this worker, not the phone's
native applications.

The browser and shell retain the container's network access, including reachable
local services. Containers share the host kernel. For stronger isolation and
untrusted workloads, run the worker in a dedicated VM and grant only needed
network/filesystem access. Disabling file tools outside `/workspace` does not
confine commands after shell execution is granted.

To stop without deleting state:

```sh
docker compose -f deploy/compose.yaml down
```

Keep the named volumes to preserve tokens, job history, and files. Browser sessions
end when the daemon exits. This recipe does not claim checkpointing or restoring
browser sessions.
