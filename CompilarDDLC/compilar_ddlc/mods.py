"""Detección y validación de mods DDLC."""
import os
import zipfile
from pathlib import Path, PurePosixPath

from .config import BASE_ASSETS, BASE_PY, BASE_RPAS, OVERLAY_RPAS
from .errors import BuildError
from .files import _rpa_ok


def _version_renpy(root):
    lib = Path(root) / "lib"
    try:
        nombres = [p.name for p in lib.iterdir() if p.is_dir()]
    except OSError:
        nombres = []
    if any(n.startswith("py3-") for n in nombres):
        return "8"
    if any(n.startswith("py2-") for n in nombres):
        return "7"
    return "?"


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
    """Devuelve (raíz, tipo) para una carpeta o un ZIP ya extraído."""
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


def _tipo_zip(path):
    """Detecta el tipo mirando los nombres del ZIP, sin extraerlo."""
    with zipfile.ZipFile(path, "r") as z:
        partes = [PurePosixPath(i.filename.replace("\\", "/")).parts
                  for i in z.infolist()]
    tiene = lambda nombre: any(nombre in p[:-1] for p in partes)
    if tiene("renpy") and tiene("lib") and tiene("game"):
        if any(n.startswith("py3-") for p in partes for n in p):
            return "runtime", "8"
        if any(n.startswith("py2-") for p in partes for n in p):
            return "runtime", "7"
        return "runtime", "?"
    if any(p[-2:] == ("game", "scripts.rpa") for p in partes) and \
       any(p[-2:] == ("game", "mod_assets.rpa") for p in partes):
        return "overlay", ""
    if any(p and p[-1].endswith(".rpy") for p in partes):
        return "fuente", ""
    raise BuildError("No reconozco el mod: no es overlay ni runtime Ren'Py.")


def detectar_mod(path):
    """Devuelve (tipo, versión) para mostrar el modo en la GUI."""
    p = Path(path)
    if p.is_file():
        if p.suffix.lower() != ".zip":
            raise BuildError("El mod debe ser una carpeta o un .zip.")
        return _tipo_zip(p)
    if not p.is_dir():
        raise BuildError("La carpeta del mod no existe.")
    root, tipo = _buscar_raiz_mod(p)
    if not tipo:
        raise BuildError("No reconozco el mod: no es overlay ni runtime Ren'Py.")
    return tipo, (_version_renpy(root) if tipo == "runtime" else "")


def validar_base(base, solo_assets=False):
    b = Path(base)
    if not b.is_dir():
        raise BuildError("La carpeta base DDLC no existe.")
    if solo_assets:
        for rel in BASE_ASSETS:
            p = b / rel
            if not p.is_file() or not _rpa_ok(p):
                raise BuildError("La base no tiene un %s válido." % rel)
        if not (b / BASE_PY).is_dir():
            raise BuildError("La base no tiene game/python-packages/.")
        return b
    if not any((b / n).is_file() or
               (n == "DDLC.app" and (b / n).is_dir())
               for n in ("DDLC.exe", "DDLC.sh", "DDLC.py", "DDLC.app")):
        raise BuildError("La base no parece DDLC: falta DDLC.exe/DDLC.sh/DDLC.py/DDLC.app.")
    for rel in ("lib", "renpy"):
        if not (b / rel).is_dir():
            raise BuildError("La base no parece DDLC: falta %s/." % rel)
    for rel in BASE_RPAS:
        p = b / rel
        if not p.is_file() or not _rpa_ok(p):
            raise BuildError("La base no tiene un %s válido." % rel)
    return b


def validar_overlay(root):
    r = Path(root)
    for rel in OVERLAY_RPAS:
        p = r / rel
        if not p.is_file() or not _rpa_ok(p):
            raise BuildError("El overlay no tiene un %s válido." % rel)
    return r


def validar_runtime(root):
    r = Path(root)
    if not _runtime_ok(r):
        raise BuildError("El mod no parece un runtime Ren'Py completo "
                         "(faltan game/, lib/, renpy/ o el ejecutable).")
    return r
