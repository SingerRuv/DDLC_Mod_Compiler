"""Developer-mode helpers: source snapshots and Konami code matching."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENTRY = ROOT / "DDLCModManager.py"
WATCHED = (ENTRY, ROOT / "ddlc_mod_manager")
IGNORED = {".git", "__pycache__", "build", "dist", ".venv", "venv"}
DEV_ENV = "DDLC_MOD_MANAGER_DEV"
SUPERVISED_ENV = "DDLC_MOD_MANAGER_SUPERVISED"
KONAMI = ("up", "down", "up", "down", "left", "right", "left", "right",
          "space", "space")


def snapshot(paths=None):
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
            if any(part in IGNORED for part in item.parts):
                continue
            try:
                stat = item.stat()
            except OSError:
                continue
            files[str(item)] = (stat.st_mtime_ns, stat.st_size)
    return files


def source_available():
    return ENTRY.is_file() and not getattr(sys, "frozen", False)


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
