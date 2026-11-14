"""Constantes y rutas de Compilar DDLC."""
from pathlib import Path
import sys

APP = "Compilar DDLC"
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


def app_dir():
    """Carpeta de la herramienta (junto al .exe o al paquete fuente)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def resource_path(nombre):
    """Ruta de un recurso empaquetado por PyInstaller."""
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) / nombre if base else app_dir() / nombre


LOG_PATH = (app_dir() / "CompilarDDLC.log" if sys.platform == "win32"
            else Path.home() / ".compilar_ddlc" / "CompilarDDLC.log")
