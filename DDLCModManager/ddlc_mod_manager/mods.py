"""DDLC mod detection and validation."""
import os
import re
import zipfile
from pathlib import Path, PurePosixPath

from .config import BASE_ASSETS, BASE_PY, BASE_RPAS, OVERLAY_RPAS
from .errors import BuildError
from .files import _rpa_ok


def _version_from_text(text):
    match = re.search(r"version_tuple\s*=\s*\(\s*(\d+)", text)
    if match:
        return match.group(1)
    match = re.search(r"version\s*=\s*[\"']Ren'Py\s+(\d+)", text)
    return match.group(1) if match else ""


def _version_tuple(text):
    match = re.search(r"version_tuple\s*=\s*\(([^)]*)\)", text)
    if match:
        values = re.findall(r"\d+", match.group(1))
        return tuple(int(value) for value in values)
    match = re.search(r"version\s*=\s*[\"']Ren'Py\s+([\d.]+)", text)
    if match:
        return tuple(int(value) for value in match.group(1).split("."))
    return ()


def _version_renpy(root):
    root = Path(root)
    init_file = root / "renpy" / "__init__.py"
    try:
        version = _version_from_text(
            init_file.read_text(encoding="utf-8", errors="ignore"))
    except OSError:
        version = ""
    if version:
        return version

    lib = root / "lib"
    try:
        nombres = [p.name for p in lib.iterdir() if p.is_dir()]
    except OSError:
        nombres = []
    if any(n.startswith("py3-") for n in nombres):
        return "8"
    if any(n.startswith("py2-") for n in nombres):
        return "7"
    if any(n.startswith(("python2", "pythonlib2")) for n in nombres):
        return "6"
    return ""


DDLC_EDITIONS = {
    (6, 99, 12, 2): "DDLC 1.0.0",
    (6, 99, 12, 4): "DDLC 1.1.1",
}


def base_info(root):
    """Return (full Ren'Py version, DDLC edition) for a base folder."""
    root = Path(root)
    try:
        text = (root / "renpy" / "__init__.py").read_text(
            encoding="utf-8", errors="ignore")
    except OSError:
        text = ""
    values = _version_tuple(text)
    if values:
        version = ".".join(str(value) for value in values[:4])
        return version, DDLC_EDITIONS.get(values[:4], "")
    return _version_renpy(root), ""


def _runtime_ok(root):
    r = Path(root)
    if not ((r / "game").is_dir() and (r / "renpy").is_dir() and
            (r / "lib").is_dir()):
        return False
    return any((p.is_file() and p.suffix.lower() in (".exe", ".py", ".sh"))
               or (p.is_dir() and p.suffix.lower() == ".app")
               for p in r.iterdir())


def _fuente_ok(root):
    game = Path(root) / "game"
    try:
        return game.is_dir() and any(game.glob("*.rpy"))
    except OSError:
        return False


def _tipo_mod(root):
    if _runtime_ok(root):
        return "runtime"
    if (Path(root) / "game" / "scripts.rpa").is_file() and \
       (Path(root) / "game" / "mod_assets.rpa").is_file():
        return "overlay"
    if _fuente_ok(root):
        return "fuente"
    return None


def _buscar_raiz_mod(path):
    """Return (root, type) for a folder or an extracted ZIP."""
    p = Path(path)
    candidatos = [p]
    try:
        candidatos += [c for c in p.iterdir() if c.is_dir()]
    except OSError:
        pass
    for c in candidatos:
        tipo = _tipo_mod(c)
        if tipo:
            return c, tipo
    for base, dirs, _files in os.walk(p):
        dirs[:] = [d for d in dirs if d not in (".git", "__MACOSX")]
        c = Path(base)
        tipo = _tipo_mod(c)
        if tipo:
            return c, tipo
    return None, None


def _zip_version(path):
    try:
        with zipfile.ZipFile(path, "r") as z:
            for info in z.infolist():
                name = info.filename.replace("\\", "/")
                if name.endswith("renpy/__init__.py"):
                    text = z.read(info).decode("utf-8", errors="ignore")
                    return _version_from_text(text)
    except (OSError, zipfile.BadZipFile):
        pass
    return ""


def _tipo_zip(path):
    """Detect the type from ZIP entry names without extracting."""
    with zipfile.ZipFile(path, "r") as z:
        partes = [PurePosixPath(i.filename.replace("\\", "/")).parts
                  for i in z.infolist()]
    tiene = lambda nombre: any(nombre in p[:-1] for p in partes)
    if tiene("renpy") and tiene("lib") and tiene("game"):
        version = _zip_version(path)
        if version:
            return "runtime", version
        if any(n.startswith("py3-") for p in partes for n in p):
            return "runtime", "8"
        if any(n.startswith("py2-") for p in partes for n in p):
            return "runtime", "7"
        if any(n.startswith(("python2", "pythonlib2"))
               for p in partes for n in p):
            return "runtime", "6"
        return "runtime", ""
    if any(p[-2:] == ("game", "scripts.rpa") for p in partes) and \
       any(p[-2:] == ("game", "mod_assets.rpa") for p in partes):
        return "overlay", ""
    if any(p and p[-1].endswith(".rpy") for p in partes):
        return "fuente", ""
    raise BuildError("Unrecognized mod: not an overlay or Ren'Py runtime.")


def detectar_mod(path):
    """Return (type, version) for the GUI mode indicator."""
    p = Path(path)
    if p.is_file():
        if p.suffix.lower() != ".zip":
            raise BuildError("The mod must be a folder or .zip.")
        return _tipo_zip(p)
    if not p.is_dir():
        raise BuildError("Mod folder does not exist.")
    root, tipo = _buscar_raiz_mod(p)
    if not tipo:
        raise BuildError("Unrecognized mod: not an overlay or Ren'Py runtime.")
    return tipo, (_version_renpy(root) if tipo == "runtime" else "")


def mod_kind(root):
    """Return a short human-readable kind for a runnable mod."""
    r = Path(root)
    game = r / "game"
    if ((game / "scripts.rpa").is_file() and
            (game / "mod_assets.rpa").is_file()):
        return "DDLC build"
    if _runtime_ok(r):
        version = _version_renpy(r)
        return "Ren'Py %s" % version if version else "Ren'Py runtime"
    return "Runnable mod"


def validar_base(base, solo_assets=False):
    b = Path(base)
    if not b.is_dir():
        raise BuildError("DDLC base folder does not exist.")
    if solo_assets:
        for rel in BASE_ASSETS:
            p = b / rel
            if not p.is_file() or not _rpa_ok(p):
                raise BuildError("The base is missing a valid %s." % rel)
        if not (b / BASE_PY).is_dir():
            raise BuildError("The base is missing game/python-packages/.")
        return b
    if not any((b / n).is_file() or
               (n == "DDLC.app" and (b / n).is_dir())
               for n in ("DDLC.exe", "DDLC.sh", "DDLC.py", "DDLC.app")):
        raise BuildError("The base does not look like DDLC: missing DDLC.exe/DDLC.sh/DDLC.py/DDLC.app.")
    for rel in ("lib", "renpy"):
        if not (b / rel).is_dir():
            raise BuildError("The base does not look like DDLC: missing %s/." % rel)
    for rel in BASE_RPAS:
        p = b / rel
        if not p.is_file() or not _rpa_ok(p):
            raise BuildError("The base is missing a valid %s." % rel)
    return b


def validar_overlay(root):
    r = Path(root)
    for rel in OVERLAY_RPAS:
        p = r / rel
        if not p.is_file() or not _rpa_ok(p):
            raise BuildError("The overlay is missing a valid %s." % rel)
    return r


def validar_runtime(root):
    r = Path(root)
    if not _runtime_ok(r):
        raise BuildError("The mod does not look like a complete Ren'Py runtime "
                         "(missing game/, lib/, renpy/, or a launcher).")
    return r
