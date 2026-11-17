#!/bin/sh
set -eu
here=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
mkdir -p "$here/build"
xcrun swiftc -sdk /Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk -O -o "$here/build/stage-ocr" "$here/stage-ocr.swift"
echo "$here/build/stage-ocr"
