#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
SDK="$HOME/Library/Android/sdk"
if printenv ANDROID_HOME >/dev/null; then SDK="$ANDROID_HOME"; fi
if ! printenv JAVA_HOME >/dev/null; then echo "Set JAVA_HOME to an installed JDK" >&2; exit 1; fi
JAVA="$JAVA_HOME"
BT="$SDK/build-tools/36.0.0"
JAR="$SDK/platforms/android-36/android.jar"
for f in "$JAR" "$BT/aapt2" "$BT/d8" "$BT/zipalign" "$BT/apksigner" "$JAVA/bin/javac"; do
  [[ -f "$f" ]] || { echo "Required Android SDK 36 / build-tools 36.0.0 or JDK missing." >&2; exit 1; }
done
OUT=build
if [[ $# -gt 0 ]]; then OUT="$1"; fi
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
TMP="$(mktemp -d "$OUT/.rdc-build.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/classes" "$TMP/dex"
"$BT/aapt2" compile --dir res -o "$TMP/resources.zip"
"$BT/aapt2" link -o "$TMP/base.apk" -I "$JAR" --manifest AndroidManifest.xml "$TMP/resources.zip"
"$JAVA/bin/javac" --release 8 -classpath "$JAR" -d "$TMP/classes" src/org/tocministries/rdc/mobile/*.java
"$JAVA/bin/jar" cf "$TMP/classes.jar" -C "$TMP/classes" .
"$BT/d8" --lib "$JAR" --min-api 26 --output "$TMP/dex" "$TMP/classes.jar"
cp "$TMP/base.apk" "$TMP/unsigned.apk"
(cd "$TMP/dex"; /usr/bin/zip -q "$TMP/unsigned.apk" classes.dex)
"$BT/zipalign" -f -p 4 "$TMP/unsigned.apk" "$OUT/rdc-mobile-unsigned.apk"
echo "Created aligned unsigned APK: $OUT/rdc-mobile-unsigned.apk"
echo "Owner-held signing key required. No APK installed or published."
