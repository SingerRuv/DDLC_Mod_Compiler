#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$ROOT/dist/linux"
WORK="${TMPDIR:-/tmp}/ddlc-compiler-linux"
ARCH="$(uname -m)"

rm -rf "$WORK"
mkdir -p "$DIST" "$WORK"

python3 -m pip install -r "$ROOT/build/requirements-build.txt"
python3 -m PyInstaller --noconfirm --clean --onefile \
    --name DDLCCompiler \
    --add-data "$ROOT/icon.png:." \
    --add-data "$ROOT/DDLC.ico:." \
    --distpath "$DIST" \
    --workpath "$WORK/build" \
    --specpath "$WORK" \
    "$ROOT/DDLCCompiler.py"

chmod +x "$DIST/DDLCCompiler"
tar -C "$DIST" -czf "$ROOT/dist/DDLCCompiler-linux-$ARCH.tar.gz" DDLCCompiler
ls -lh "$DIST/DDLCCompiler" "$ROOT/dist/DDLCCompiler-linux-$ARCH.tar.gz"
