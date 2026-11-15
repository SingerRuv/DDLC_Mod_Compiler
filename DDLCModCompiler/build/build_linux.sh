#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$ROOT/dist/linux"
WORK="${TMPDIR:-/tmp}/ddlc-mod-compiler-linux"
ARCH="$(uname -m)"

rm -rf "$WORK"
mkdir -p "$DIST" "$WORK"

python3 -m pip install -r "$ROOT/build/requirements-build.txt"
python3 -m PyInstaller --noconfirm --clean --onefile \
    --name DDLCModCompiler \
    --add-data "$ROOT/DDLC.ico:." \
    --add-data "$ROOT/icons:icons" \
    --distpath "$DIST" \
    --workpath "$WORK/build" \
    --specpath "$WORK" \
    "$ROOT/DDLCModCompiler.py"

chmod +x "$DIST/DDLCModCompiler"
tar -C "$DIST" -czf "$ROOT/dist/DDLCModCompiler-linux-$ARCH.tar.gz" DDLCModCompiler
ls -lh "$DIST/DDLCModCompiler" "$ROOT/dist/DDLCModCompiler-linux-$ARCH.tar.gz"
