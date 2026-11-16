"""Owner-run macOS permission walkthrough. Never writes privacy databases."""
from pathlib import Path
import sys

from .errors import RDCError
from .windows import MacWindowBackend


def setup_status(state_dir, request=None):
    if sys.platform != 'darwin':
        raise RDCError('platform_unavailable', 'Native window permission setup requires macOS 14 or later. Headless browsers do not need these permissions.')
    if request not in (None, 'accessibility', 'screen-recording'):
        raise ValueError('Unknown macOS permission')
    backend = MacWindowBackend(state_dir)
    if request:
        backend('request_permission', permission=request)
    status = backend('permissions')
    capture = status.get('screen_recording') is True
    resize = status.get('accessibility') is True
    return {'platform':'macOS', 'screen_recording':capture, 'accessibility':resize,
            'ready':capture and resize, 'request':request,
            'helper_path':str(Path(state_dir)/'native-window-helper'/'RDC Window Preview.app'),
            'owner_action_required':not (capture and resize),
            'note':'Screen Recording enables capture; Accessibility enables exact-window resizing. The owner must grant each permission in System Settings.'}


def print_walkthrough(report):
    print('RDC native-window setup')
    print(f"Screen Recording (capture): {'allowed' if report['screen_recording'] else 'needs your permission'}")
    print(f"Accessibility (resize): {'allowed' if report['accessibility'] else 'needs your permission'}")
    print(f"Helper: {report['helper_path']}")
    if not report['ready']:
        print('Open System Settings > Privacy & Security. Use Screen & System Audio Recording for capture, and Accessibility for resizing.')
        print('Enable RDC Window Preview. If it is missing, click Add (+), press Command-Shift-G, paste the helper path above, then select Open. The older RDC app is a separate permission entry.')
        print('macOS may ask you to authenticate. Complete that yourself; do not share your password or bypass the prompt.')
        print('To register a missing entry through the normal macOS prompt, run rdc setup-macos --request accessibility or --request screen-recording with the same --state-dir.')
        print('After granting access, run rdc setup-macos again, then retry resizing in the same preview. Capture can continue while resizing is unavailable.')
    else:
        print('Both permissions are confirmed. Retry resizing in the same preview; do not create a replacement source.')
    print('Only owner-requested setup may display permission prompts. Routine capture and resizing do not activate your apps. Recheck after a helper update; local ad-hoc signing may require permission again.')
