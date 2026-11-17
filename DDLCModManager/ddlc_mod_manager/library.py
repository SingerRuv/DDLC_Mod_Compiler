"""Mod discovery and Launcher persistence."""
import hashlib
import json
import unicodedata
from pathlib import Path, PurePosixPath

from . import rpa
from .config import DATA_DIR, MODS_ROOT, STAGING_PREFIX
from .mods import mod_kind
from .platforms import find_launcher

STORE_PATH = DATA_DIR / "launcher.json"
LAUNCHER_SUFFIXES = (".exe", ".app", ".sh")
SKIP_DIRS = {".git", "__pycache__", "game", "lib", "renpy", "saves",
             "cache", "dist", "build", ".venv"}


LOGO_NAMES = ("icon.png", "logo.png", "game/icon.png", "game/logo.png",
              "game/gui/icon.png", "game/gui/window_icon.png",
              "gui/icon.png", "gui/window_icon.png")


def _logo_score(name):
    base = PurePosixPath(name).name.lower()
    if not base.endswith((".png", ".gif")):
        return -1
    if any(bad in base for bad in ("template", "splash", "titlecard",
                                    "background", "phone_", "demosplash")):
        return -1
    if base in ("icon.png", "icon.gif"):
        return 100
    if base in ("logo.png", "logo.gif"):
        return 95
    if "logo_fg" in base:
        return 90
    if "window_icon" in base:
        return 85
    if "logo" in base:
        return 70
    if base.startswith("icon"):
        return 60
    return -1


def _rpa_logo(root):
    game = Path(root) / "game"
    try:
        archives = sorted(
            (p for p in game.glob("*.rpa") if p.is_file()),
            key=lambda p: (0 if p.name == "mod_assets.rpa" else
                           1 if p.name == "images.rpa" else 2, p.name))
    except OSError:
        return ""
    best = None
    for archive in archives:
        try:
            for name, offset, length in rpa.list_images(archive):
                score = _logo_score(name)
                if score < 0:
                    continue
                key = (score, -name.count("/"), name.casefold())
                if best is None or key > best[0]:
                    best = (key, archive, name, offset, length)
        except OSError:
            continue
    if best is None:
        return ""
    _key, archive, name, offset, length = best
    suffix = PurePosixPath(name).suffix.lower()
    try:
        stamp = archive.stat()
        digest = hashlib.sha1(
            ("%s|%s|%s|%s" % (archive, stamp.st_mtime, stamp.st_size,
                              name)).encode("utf-8")).hexdigest()
    except OSError:
        return ""
    cache = DATA_DIR / "logo-cache" / (digest + suffix)
    if cache.is_file():
        return str(cache)
    try:
        extracted = rpa.extract(archive, offset, length, cache)
    except OSError:
        return ""
    return str(extracted) if extracted else ""


def _logo_for(root):
    root = Path(root)
    for rel in LOGO_NAMES:
        p = root / rel
        if p.is_file():
            return str(p)
    return _rpa_logo(root)


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
        try:
            mtime = root.stat().st_mtime
        except OSError:
            mtime = 0
        return {
            "path": str(root.resolve()),
            "name": root.name,
            "launcher": str(launcher.resolve()),
            "kind": kind,
            "logo": _logo_for(root),
            "mtime": mtime,
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
                        p.name not in SKIP_DIRS and
                        not p.name.startswith(STAGING_PREFIX)]
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


def _search_text(value):
    value = unicodedata.normalize("NFKD", value or "")
    return "".join(c for c in value
                   if not unicodedata.combining(c)).casefold()


def filter_entries(entries, query="", runtime="All"):
    query = _search_text(query.strip())
    result = []
    for entry in entries:
        kind = entry.get("kind", "")
        if runtime == "Other":
            if kind in ("Ren'Py 6", "Ren'Py 7", "Ren'Py 8",
                        "DDLC build"):
                continue
        elif runtime != "All" and kind != runtime:
            continue
        if query:
            haystack = _search_text(" ".join((
                entry.get("name", ""), entry.get("path", ""), kind)))
            if query not in haystack:
                continue
        result.append(entry)
    return result


def sort_entries(entries, mode="Name A-Z"):
    entries = list(entries)
    if mode == "Name Z-A":
        return sorted(entries, key=lambda e: e["name"].casefold(),
                      reverse=True)
    if mode == "Newest first":
        return sorted(entries, key=lambda e: e.get("mtime", 0),
                      reverse=True)
    if mode == "Oldest first":
        return sorted(entries, key=lambda e: e.get("mtime", 0))
    return sorted(entries, key=lambda e: e["name"].casefold())


def load_state():
    try:
        data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return [], []
    if not isinstance(data, dict):
        return [], []
    roots = data.get("external_roots", [])
    paths = data.get("mods", [])
    if not isinstance(roots, list):
        roots = []
    if not isinstance(paths, list):
        paths = []
    old_root = data.get("root")
    if isinstance(old_root, str) and old_root:
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
