"""Owner-only mobile onboarding for the independent RDC gateway."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import stat

from .mobile import validate_mobile_profiles


def provision_mobile_token(directory):
    """Opt in to read-only mobile status; never replace or print credentials."""
    root = Path(directory).expanduser().absolute()
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode) or (os.name == "posix" and (
            info.st_uid != os.getuid() or info.st_mode & 0o077)):
        raise ValueError("Use an existing private gateway state directory.")
    if not all((root / name).is_file() for name in ("client-token", "device-token", "device-id")):
        raise ValueError("Initialize the independent gateway first.")
    path = root / "mobile-status-token"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w") as output:
        output.write(secrets.token_urlsafe(48) + "\n")
    return path


def make_profile(alias, platform, udid, app, activity=None, endpoint="http://127.0.0.1:4723"):
    """Generate a validated config fragment without modifying a live worker."""
    if not isinstance(app, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_][A-Za-z0-9_-]*)+", app):
        raise ValueError("Choose an exact installed bundle or package ID.")
    caps = {"appium:udid": udid, "appium:noReset": True}
    if platform == "ios" and activity is None:
        pair = ("iOS", "XCUITest")
        caps["appium:bundleId"] = app
    elif platform == "android" and isinstance(activity, str) and re.fullmatch(r"\.?[A-Za-z_$][A-Za-z0-9_.$]*", activity):
        pair = ("Android", "UiAutomator2")
        caps["appium:appPackage"] = app
        caps["appium:appActivity"] = activity
    else:
        raise ValueError("Choose iOS or Android with an exact Android activity.")
    profiles = {alias: {"platformName": pair[0], "automationName": pair[1],
                        "endpoint": endpoint, "capabilities": caps}}
    validate_mobile_profiles(profiles)
    return profiles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    enable = sub.add_parser("enable-status")
    enable.add_argument("--state-dir", required=True)
    profile = sub.add_parser("profile")
    profile.add_argument("--alias", required=True)
    profile.add_argument("--platform", choices=("ios", "android"), required=True)
    profile.add_argument("--udid", required=True)
    profile.add_argument("--app", required=True)
    profile.add_argument("--activity")
    profile.add_argument("--endpoint", default="http://127.0.0.1:4723")
    probe = sub.add_parser("ios-usb-check", help="Read-only local USB and existing trust diagnostic")
    probe.add_argument("--udid", help="Exact owner-selected device if multiple are attached")
    prepare = sub.add_parser("ios-usb-profile", help="Create a private fragment for a trusted USB device")
    prepare.add_argument("--udid")
    prepare.add_argument("--alias", default="iphone")
    prepare.add_argument("--output", required=True)
    android_probe = sub.add_parser("android-usb-check", help="Read-only Android USB authorization diagnostic")
    android_probe.add_argument("--serial", help="Exact owner-selected USB device if multiple are attached")
    android_prepare = sub.add_parser("android-usb-profile", help="Create a private fragment for an authorized USB device")
    android_prepare.add_argument("--serial")
    android_prepare.add_argument("--alias", default="android")
    android_prepare.add_argument("--app", required=True)
    android_prepare.add_argument("--activity", required=True)
    android_prepare.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.action == "enable-status":
        provision_mobile_token(args.state_dir)
        print("Read-only mobile status enabled. Retrieve mobile-status-token privately from the state directory.")
    elif args.action == "android-usb-check":
        from .android_usb import usb_check
        print(json.dumps(usb_check(args.serial),indent=2))
    elif args.action == "android-usb-profile":
        from .android_usb import write_profile
        try:
            write_profile(args.output,args.alias,args.app,args.activity,args.serial)
        except (OSError,ValueError,EOFError,TypeError,KeyError):
            parser.exit(1,"Unable to create private Android profile; verify the authorized USB device, installed activity and output path.\n")
        print("Private Android profile created; no live worker configuration or phone data changed.")
    elif args.action == "ios-usb-check":
        from .ios_usb import usb_check
        print(json.dumps(usb_check(args.udid),indent=2))
    elif args.action == "ios-usb-profile":
        from .ios_usb import write_profile
        try:
            write_profile(args.output,args.alias,args.udid)
        except (OSError,ValueError,EOFError,TypeError,KeyError):
            parser.exit(1,"Unable to create private iOS profile; check connection, existing trust and output path.\n")
        print("Private iOS profile created; no live worker configuration or phone data changed.")
    else:
        print(json.dumps({"mobile_profiles": make_profile(args.alias, args.platform, args.udid,
                         args.app, args.activity, args.endpoint)}, indent=2))


if __name__ == "__main__":
    main()
