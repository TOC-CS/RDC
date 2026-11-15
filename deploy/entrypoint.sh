#!/bin/sh
set -eu
umask 077
# No host X11 socket, input devices, Docker socket, or desktop profile are used.
state_dir=${RDC_STATE_DIR:-/home/rdc/state}
if [ ! -f "$state_dir/config.json" ]; then
    case "${RDC_DESKTOP_MODE:-disabled}" in
        disabled|isolated) ;;
        *) echo 'Container desktop mode must be disabled or isolated.' >&2; exit 2 ;;
    esac
    set -- init --state-dir "$state_dir" --root /workspace --desktop-mode "${RDC_DESKTOP_MODE:-disabled}"
    if [ "${RDC_ENABLE_EXEC:-0}" = 1 ]; then set -- "$@" --allow-exec; fi
    rdc "$@"
fi
# xvfb-run creates a temporary Xauthority cookie; X11 TCP listening stays off.
exec xvfb-run -a --server-args='-screen 0 1440x900x24 -nolisten tcp' /bin/sh /app/deploy/worker-session.sh
