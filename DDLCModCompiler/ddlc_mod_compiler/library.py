"""Mod discovery and Launcher persistence."""
import json
from pathlib import Path

from .config import MODS_ROOT
from .mods import mod_kind
from .platforms import find_launcher

DATA_DIR = Path.home() / ".ddlc_mod_compiler"
STORE_PATH = DATA_DIR / "launcher.json"
LAUNCHER_SUFFIXES = (".exe", ".app", ".sh")
SKIP_DIRS = {".git", "__pycache__", "game", "lib", "renpy", "saves",
             "cache", "dist", "build", ".venv"}


def _logo_for(root):
    for rel in ("icon.png", "logo.png", "game/icon.png",
                "game/logo.png", "game/gui/icon.png"):
        p = root / rel
        if p.is_file():
            return str(p)
    return ""


def entry_from_path(path):
    """Build one Launcher entry for a runnable mod folder, or None."""
    try:
        root = Path(path)
        if not root.is_dir():
            return None
        launcher = find_launcher(root)
        if launcher is None or launcher.suffix.lower() not in LAUNCHER_SUFFIXES:
            return None
        if launcher.suffix.lower() == ".app" and not launcher.is_dir():
            return None
        kind = mod_kind(root)
        return {
            "path": str(root.resolve()),
            "name": root.name,
            "launcher": str(launcher.resolve()),
            "kind": kind,
            "logo": _logo_for(root),
        }
    except OSError:
        return None


def scan_mods(root, cancel=None):
    """Recursively find runnable mods, without entering a detected mod."""
    root = Path(root)
    if not root.is_dir():
        return []
    found = {}

    def visit(directory):
        if cancel and cancel.is_set():
            return
        entry = entry_from_path(directory)
        if entry:
            found[entry["path"]] = entry
            return
        try:
            children = [p for p in directory.iterdir()
                        if p.is_dir() and not p.is_symlink() and
                        p.name not in SKIP_DIRS]
        except OSError:
            return
        for child in children:
            if cancel and cancel.is_set():
                return
            visit(child)

    visit(root)
    return sorted(found.values(), key=lambda e: e["name"].casefold())


def scan_roots(roots, cancel=None):
    found = {}
    seen = set()
    for root in roots:
        if cancel and cancel.is_set():
            break
        try:
            key = str(Path(root).resolve())
        except OSError:
            continue
        if key in seen:
            continue
        seen.add(key)
        for entry in scan_mods(root, cancel):
            found[entry["path"]] = entry
    return sorted(found.values(), key=lambda e: e["name"].casefold())


def load_state():
    try:
        data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return [], []
    roots = data.get("external_roots", [])
    paths = data.get("mods", [])
    if not isinstance(roots, list):
        roots = []
    if not isinstance(paths, list):
        paths = []
    old_root = data.get("root")
    if old_root:
        try:
            old = Path(old_root).resolve()
            if old != MODS_ROOT.resolve() and str(old) not in roots:
                roots.append(str(old))
        except OSError:
            pass
    return [str(r) for r in roots], [str(p) for p in paths]


def save_state(external_roots, entries):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "external_roots": list(external_roots),
        "mods": [e["path"] for e in entries],
    }
    tmp = STORE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(STORE_PATH)
