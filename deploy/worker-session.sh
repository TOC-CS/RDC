#!/bin/sh
set -eu
# These processes share only the container's virtual display.
openbox >/dev/null 2>&1 &
# RDC itself binds loopback. Docker publishes this internal forwarding port on
# host loopback only, as configured in compose.yaml.
socat TCP-LISTEN:8765,fork,reuseaddr TCP:127.0.0.1:8766 &
exec rdc serve --state-dir "${RDC_STATE_DIR:-/home/rdc/state}" --host 127.0.0.1 --port 8766
