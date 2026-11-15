"""DDLC Mod Compiler constants and paths."""
import json
from pathlib import Path
import sys

APP = "DDLC Mod Compiler"
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

PHASE_COPY_MOD = "Copying mod"
PHASE_COPY_ASSETS = "Copying assets"
PHASE_COPY_BASE = "Copying base"
PHASE_COPY_OVERLAY = "Copying overlay"
PHASE_VERIFY = "Verifying"
PHASE_ZIP = "Creating ZIP"


def ensure_mods_root():
    MODS_ROOT.mkdir(parents=True, exist_ok=True)
    return MODS_ROOT


def app_dir():
    """Tool folder (next to the executable or the source package)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def resource_path(nombre):
    """Path to a resource bundled by PyInstaller."""
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) / nombre if base else app_dir() / nombre


LOG_PATH = (app_dir() / "DDLCModCompiler.log" if sys.platform == "win32"
            else Path.home() / ".ddlc_mod_compiler" / "DDLCModCompiler.log")
SETTINGS_PATH = Path.home() / ".ddlc_mod_compiler" / "settings.json"


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
