#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$ROOT/dist/macos"
WORK="${TMPDIR:-/tmp}/compilar-ddlc-macos"
ARCH="${1:-$(uname -m)}"

rm -rf "$WORK"
mkdir -p "$DIST" "$WORK"

python3 -m pip install -r "$ROOT/build/requirements-build.txt"
python3 -m PyInstaller --noconfirm --clean --windowed \
    --name CompilarDDLC \
    --icon "$ROOT/icono.icns" \
    --add-data "$ROOT/icono.png:." \
    --add-data "$ROOT/icono DDLC.ico:." \
    --distpath "$DIST" \
    --workpath "$WORK/build" \
    --specpath "$WORK" \
    "$ROOT/CompilarDDLC.py"

ditto -c -k --sequesterRsrc --keepParent \
    "$DIST/CompilarDDLC.app" \
    "$ROOT/dist/CompilarDDLC-macos-$ARCH.zip"
ls -lh "$ROOT/dist/CompilarDDLC-macos-$ARCH.zip"
