"""File operations, hashes, copies, and ZIP."""
import hashlib
import os
import shutil
import zipfile
from pathlib import Path, PurePosixPath

from .config import COPY_CHUNK, MAX_ZIP_BYTES, MAX_ZIP_FILES
from .errors import BuildCancelada, BuildError


def _norm(p):
    return str(Path(p).resolve())


def _rpa_ok(path):
    try:
        with open(path, "rb") as fh:
            return fh.read(8).startswith(b"RPA-3.0")
    except Exception:
        return False


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _no_vacio(path):
    p = Path(path)
    try:
        return p.is_dir() and any(p.iterdir())
    except OSError:
        return True


def _extraer_zip(zip_path, destino, cancelar=None):
    total_archivos = 0
    total_bytes = 0
    with zipfile.ZipFile(zip_path, "r") as z:
        for info in z.infolist():
            if cancelar and cancelar.is_set():
                raise BuildCancelada()
            nombre = info.filename.replace("\\", "/")
            partes = PurePosixPath(nombre).parts
            if not partes or PurePosixPath(nombre).is_absolute() or \
               ".." in partes or ":" in partes[0]:
                raise BuildError("The ZIP contains a disallowed path: %s" % nombre)
            if ((info.external_attr >> 16) & 0o170000) == 0o120000:
                raise BuildError("The ZIP contains a symbolic link: %s" % nombre)
            total_archivos += 1
            total_bytes += info.file_size
            if total_archivos > MAX_ZIP_FILES:
                raise BuildError("The ZIP has too many files.")
            if total_bytes > MAX_ZIP_BYTES:
                raise BuildError("The extracted ZIP exceeds the allowed size.")
            destino_archivo = Path(destino).joinpath(*partes)
            if info.is_dir():
                destino_archivo.mkdir(parents=True, exist_ok=True)
            else:
                destino_archivo.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as origen, open(destino_archivo, "wb") as salida:
                    shutil.copyfileobj(origen, salida)


def _ignorar_base(rel):
    rel = rel.replace("\\", "/")
    partes = rel.split("/")
    if rel.startswith("game/saves/") or rel.startswith("game/cache/"):
        return True
    if "__pycache__" in partes:
        return True
    if rel.endswith((".rpyc", ".rpyb")):
        return True
    return partes[-1] in ("log.txt", "errors.txt", "traceback.txt", "firstrun")


def _ignorar_runtime(rel):
    rel = rel.replace("\\", "/")
    partes = rel.split("/")
    if rel.startswith("game/saves/") or rel.startswith("game/cache/"):
        return True
    if "__pycache__" in partes or ".git" in partes:
        return True
    return partes[-1].lower() in ("log.txt", "errors.txt", "traceback.txt",
                                  ".ds_store")


def _tam_arbol(origen, filtro=None):
    total = 0
    for dirpath, _dirnames, filenames in os.walk(origen):
        for nombre in filenames:
            p = Path(dirpath) / nombre
            try:
                rel = str(p.relative_to(origen)).replace("\\", "/")
            except ValueError:
                continue
            if filtro and filtro(rel):
                continue
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return total


def _copiar_archivo(origen, destino, cancelar, progress, etiqueta, total,
                    inicio=0):
    hecho = 0
    ultimo = -1
    with open(origen, "rb") as fi, open(destino, "wb") as fo:
        while True:
            if cancelar and cancelar.is_set():
                raise BuildCancelada()
            trozo = fi.read(COPY_CHUNK)
            if not trozo:
                break
            fo.write(trozo)
            hecho += len(trozo)
            if total:
                pct = int((inicio + hecho) * 100 / total)
                if pct != ultimo:
                    progress(etiqueta, inicio + hecho, total)
                    ultimo = pct
    try:
        shutil.copystat(origen, destino)
    except OSError:
        pass
    return hecho


def _copiar_arbol(origen, destino, log, cancelar, progress,
                  filtro=_ignorar_base, etiqueta="Copying base",
                  resumen="Base copied"):
    origen = Path(origen)
    destino = Path(destino)
    total_bytes = _tam_arbol(origen, filtro)
    hechos = 0
    copiados_bytes = 0
    for dirpath, dirnames, filenames in os.walk(origen):
        if cancelar and cancelar.is_set():
            raise BuildCancelada()
        rel_dir = Path(dirpath).relative_to(origen)
        dirnames[:] = [
            d for d in dirnames
            if not filtro(str(rel_dir / d).replace("\\", "/") + "/")
        ]
        dst_dir = destino / rel_dir
        dst_dir.mkdir(parents=True, exist_ok=True)
        for nombre in filenames:
            if cancelar and cancelar.is_set():
                raise BuildCancelada()
            src = Path(dirpath) / nombre
            rel = str(src.relative_to(origen)).replace("\\", "/")
            if filtro(rel):
                continue
            dst = dst_dir / nombre
            copiados_bytes += _copiar_archivo(
                src, dst, cancelar, progress, etiqueta,
                max(total_bytes, 1), copiados_bytes)
            hechos += 1
    log("%s: %d files." % (resumen, hechos))


def _archivos_faltantes(origen, destino):
    origen = Path(origen)
    destino = Path(destino)
    if origen.is_file():
        if not destino.exists():
            yield origen, destino
        return
    for dirpath, _dirnames, filenames in os.walk(origen):
        for nombre in filenames:
            src = Path(dirpath) / nombre
            rel = src.relative_to(origen)
            dst = destino / rel
            if not dst.exists():
                yield src, dst
