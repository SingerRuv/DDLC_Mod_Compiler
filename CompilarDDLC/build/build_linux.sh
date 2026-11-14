#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$ROOT/dist/linux"
WORK="${TMPDIR:-/tmp}/compilar-ddlc-linux"
ARCH="$(uname -m)"

rm -rf "$WORK"
mkdir -p "$DIST" "$WORK"

python3 -m pip install -r "$ROOT/build/requirements-build.txt"
python3 -m PyInstaller --noconfirm --clean --onefile \
    --name CompilarDDLC \
    --add-data "$ROOT/icono.png:." \
    --add-data "$ROOT/icono DDLC.ico:." \
    --distpath "$DIST" \
    --workpath "$WORK/build" \
    --specpath "$WORK" \
    "$ROOT/CompilarDDLC.py"

chmod +x "$DIST/CompilarDDLC"
tar -C "$DIST" -czf "$ROOT/dist/CompilarDDLC-linux-$ARCH.tar.gz" CompilarDDLC
ls -lh "$DIST/CompilarDDLC" "$ROOT/dist/CompilarDDLC-linux-$ARCH.tar.gz"
