#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$ROOT/dist/macos"
WORK="${TMPDIR:-/tmp}/ddlc-mod-compiler-macos"
ARCH="${1:-$(uname -m)}"

rm -rf "$WORK"
mkdir -p "$DIST" "$WORK"

python3 -m pip install -r "$ROOT/build/requirements-build.txt"
python3 -m PyInstaller --noconfirm --clean --windowed \
    --name DDLCModCompiler \
    --icon "$ROOT/icon.icns" \
    --add-data "$ROOT/icon.png:." \
    --add-data "$ROOT/DDLC.ico:." \
    --distpath "$DIST" \
    --workpath "$WORK/build" \
    --specpath "$WORK" \
    "$ROOT/DDLCModCompiler.py"

ditto -c -k --sequesterRsrc --keepParent \
    "$DIST/DDLCModCompiler.app" \
    "$ROOT/dist/DDLCModCompiler-macos-$ARCH.zip"
ls -lh "$ROOT/dist/DDLCModCompiler-macos-$ARCH.zip"
