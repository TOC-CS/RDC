#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
# Optional owner-approved packaging tool only. The RDC worker does not
# require this Xcode installation for direct USB developer services.
XCODE="/Applications/Xcode.app/Contents/Developer"
if [[ -n "$(printenv DEVELOPER_DIR || true)" ]]; then XCODE="$DEVELOPER_DIR"; fi
BUILD="$XCODE/usr/bin/xcodebuild"
[[ -x "$BUILD" ]] || { echo "Full owner-approved Xcode installation required." >&2; exit 1; }
export DEVELOPER_DIR="$XCODE"
if [[ ! -f RDCMobile.xcodeproj/project.pbxproj ]]; then
  command -v xcodegen >/dev/null || { echo "XcodeGen required." >&2; exit 1; }
  xcodegen generate --spec project.yml
fi
"$BUILD" -checkFirstLaunchStatus || {
  echo "Complete Apple Xcode first-launch setup before building." >&2
  exit 1
}
MODE=unsigned
if [[ $# -gt 0 ]]; then MODE="$1"; fi
OUT=build
if [[ $# -gt 1 ]]; then OUT="$2"; fi
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
case "$MODE" in
  unsigned)
    "$BUILD" -project RDCMobile.xcodeproj -scheme RDCMobile -configuration Debug -sdk iphoneos -destination 'generic/platform=iOS' -derivedDataPath "$OUT/DerivedData-unsigned" CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO build
    echo "Unsigned compile only. Device installation is not authorized by this build."
    ;;
  signed)
    TEAM="$(printenv RDC_APPLE_TEAM || true)"
    [[ "$TEAM" =~ ^[A-Z0-9]{10}$ ]] || { echo "Set the exact owner-approved Apple development team locally." >&2; exit 1; }
    DEVICE="$(printenv RDC_IOS_DEVICE || true)"
    [[ "$DEVICE" =~ ^[A-Za-z0-9-]{8,128}$ ]] || { echo "Set the owner-selected iPhone locally." >&2; exit 1; }
    "$BUILD" -project RDCMobile.xcodeproj -scheme RDCMobile -configuration Debug -sdk iphoneos -destination "platform=iOS,id=$DEVICE" -derivedDataPath "$OUT/DerivedData-signed" DEVELOPMENT_TEAM="$TEAM" CODE_SIGN_STYLE=Automatic build
    APP="$OUT/DerivedData-signed/Build/Products/Debug-iphoneos/RDCMobile.app"
    [[ -d "$APP" && -f "$APP/embedded.mobileprovision" ]] || { echo "Signed development bundle or provisioning profile missing." >&2; exit 1; }
    /usr/bin/codesign --verify --strict "$APP"
    echo "Signed bundle built and locally verified. No install performed."
    ;;
  *) echo "Use unsigned or signed." >&2; exit 1;;
esac
