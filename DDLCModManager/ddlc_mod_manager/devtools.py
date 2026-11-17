"""Developer-mode helpers: source snapshots and Konami code matching."""
import sys
from pathlib import Path

from .config import STAGING_PREFIX

ROOT = Path(__file__).resolve().parent.parent
ENTRY = ROOT / "DDLCModManager.py"
WATCHED = (ENTRY, ROOT / "ddlc_mod_manager")
IGNORED = {".git", "__pycache__", "build", "dist", ".venv", "venv"}
DEV_ENV = "DDLC_MOD_MANAGER_DEV"
SUPERVISED_ENV = "DDLC_MOD_MANAGER_SUPERVISED"
KONAMI = ("up", "down", "up", "down", "left", "right", "left", "right",
          "space", "space")


def snapshot(paths=None, root=None):
    root = Path(root) if root else ROOT
    files = {}
    for path in paths or WATCHED:
        if path.is_file():
            candidates = (path,)
        elif path.is_dir():
            candidates = path.rglob("*.py")
        else:
            continue
        for item in candidates:
            if item.suffix != ".py":
                continue
            try:
                relative = item.relative_to(root)
            except ValueError:
                relative = item
            if any(part in IGNORED for part in relative.parts):
                continue
            try:
                stat = item.stat()
            except OSError:
                continue
            files[str(item)] = (stat.st_mtime_ns, stat.st_size)
    return files


def source_available():
    return ENTRY.is_file() and not getattr(sys, "frozen", False)


def build_staging(root, prefix=STAGING_PREFIX):
    """Return the build staging folders left in root."""
    try:
        return sorted(path for path in Path(root).glob(prefix + "*")
                      if path.is_dir())
    except OSError:
        return []


def make_test_mods(root, count=12):
    """Create layout-only mods for Launcher testing."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    created = []
    for index in range(1, count + 1):
        folder = root / ("Dev Test Mod %02d - Long Name For Layout Testing"
                         % index)
        game = folder / "game"
        game.mkdir(parents=True, exist_ok=True)
        (folder / "Game.exe").write_bytes(b"")
        (folder / "Game.sh").write_text("#!/bin/sh\nexit 0\n",
                                        encoding="utf-8")
        (game / "scripts.rpa").write_bytes(b"")
        (game / "mod_assets.rpa").write_bytes(b"")
        created.append(folder)
    return created


class Konami:
    def __init__(self):
        self._index = 0

    def feed(self, keysym):
        key = str(keysym).lower()
        if key == KONAMI[self._index]:
            self._index += 1
            if self._index == len(KONAMI):
                self._index = 0
                return True
            return False
        self._index = 1 if key == KONAMI[0] else 0
        return False
