"""DDLC Mod Manager constants and paths."""
import json
from pathlib import Path
import shutil
import sys

APP = "DDLC Mod Manager"
MAX_ZIP_FILES = 200000
MAX_ZIP_BYTES = 4 * 1024 * 1024 * 1024
COPY_CHUNK = 1024 * 1024
MARGEN_DISCO = 200 * 1024 * 1024

DOCS = ("Credits.txt", "ThankYou.txt", "README.html")
BASE_RPAS = ("game/scripts.rpa", "game/images.rpa", "game/audio.rpa",
             "game/fonts.rpa")
BASE_ASSETS = ("game/images.rpa", "game/audio.rpa", "game/fonts.rpa")
BASE_PY = "game/python-packages"
OVERLAY_RPAS = ("game/scripts.rpa", "game/mod_assets.rpa")
MODS_ROOT = Path.home() / "DDLC Mods"
DATA_DIR = Path.home() / ".ddlc_mod_manager"
OLD_DATA_DIR = Path.home() / ".ddlc_mod_compiler"

PHASE_COPY_MOD = "Copying mod"
PHASE_COPY_ASSETS = "Copying assets"
PHASE_COPY_BASE = "Copying base"
PHASE_COPY_OVERLAY = "Copying overlay"
PHASE_VERIFY = "Verifying"
PHASE_ZIP = "Creating ZIP"


def ensure_mods_root():
    MODS_ROOT.mkdir(parents=True, exist_ok=True)
    return MODS_ROOT


def migrate_legacy_data(old_dir=None, new_dir=None):
    """Copy the old application data once, preserving it for rollback."""
    old_dir = Path(old_dir) if old_dir else OLD_DATA_DIR
    new_dir = Path(new_dir) if new_dir else DATA_DIR
    if new_dir.exists():
        return False
    if not old_dir.is_dir():
        return False
    try:
        shutil.copytree(old_dir, new_dir)
        return True
    except OSError:
        return False


def app_dir():
    """Tool folder (next to the executable or the source package)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def resource_path(nombre):
    """Path to a resource bundled by PyInstaller."""
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) / nombre if base else app_dir() / nombre


LOG_PATH = (app_dir() / "DDLCModManager.log" if sys.platform == "win32"
            else DATA_DIR / "DDLCModManager.log")
SETTINGS_PATH = DATA_DIR / "settings.json"


def load_theme():
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        return bool(data.get("dark", False))
    except Exception:
        return False


def save_theme(dark):
    try:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = SETTINGS_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps({"dark": bool(dark)}, indent=2),
                       encoding="utf-8")
        tmp.replace(SETTINGS_PATH)
    except OSError:
        pass
