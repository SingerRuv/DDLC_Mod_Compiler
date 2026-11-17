"""Platform helpers for launching games and opening folders."""
import os
import subprocess
import sys
from pathlib import Path

BAD_LAUNCHERS = ("unins", "uninstall", "updater", "setup", "installer")


def _bad_launcher(name):
    stem = Path(name).stem.lower()
    return any(marker in stem for marker in BAD_LAUNCHERS)


def platform_name():
    """Return the current platform name shown in the Launcher."""
    if sys.platform == "win32":
        return "Windows"
    if sys.platform == "darwin":
        return "macOS"
    return "Linux"


def find_launcher(root):
    """Return the main executable/app/script for a game or runtime."""
    r = Path(root)

    if sys.platform == "win32":
        for nombre in ("DDLC.exe", "renpy.exe"):
            if (r / nombre).is_file():
                return r / nombre
        try:
            exes = sorted(p for p in r.glob("*.exe")
                          if p.is_file() and
                          not p.stem.lower().endswith("-32") and
                          not _bad_launcher(p.name))
        except OSError:
            exes = []
        return exes[0] if exes else None

    if sys.platform == "darwin":
        try:
            apps = sorted(p for p in r.glob("*.app")
                          if p.is_dir() and not _bad_launcher(p.name))
        except OSError:
            apps = []
        if apps:
            return apps[0]

    for nombre in ("DDLC.sh", "renpy.sh"):
        if (r / nombre).is_file():
            return r / nombre

    try:
        scripts = sorted(p for p in r.glob("*.sh")
                         if p.is_file() and not _bad_launcher(p.name))
    except OSError:
        scripts = []
    if scripts:
        return scripts[0]

    try:
        for p in sorted(r.iterdir()):
            if (p.is_file() and not _bad_launcher(p.name) and
                    os.access(str(p), os.X_OK)):
                return p
    except OSError:
        pass
    return None


def open_launcher(path, cwd=None):
    """Open a launcher according to the platform."""
    path = Path(path)
    cwd = str(cwd) if cwd else None
    if sys.platform == "darwin" and path.is_dir() and path.suffix == ".app":
        return subprocess.Popen(["open", str(path)], cwd=cwd)
    if path.suffix.lower() in (".sh", ".command"):
        return subprocess.Popen(["sh", str(path)], cwd=cwd)
    return subprocess.Popen([str(path)], cwd=cwd)


def open_path(path):
    """Open a folder in the system file manager."""
    path = str(path)
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
