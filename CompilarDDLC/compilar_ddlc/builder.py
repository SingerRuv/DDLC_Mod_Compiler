"""Build overlay y runtime de Compilar DDLC."""
import shutil
import tempfile
import zipfile
from pathlib import Path

from .config import (BASE_ASSETS, BASE_PY, BASE_RPAS, DOCS, MARGEN_DISCO,
                     OVERLAY_RPAS)
from .errors import BuildCancelada, BuildError
from .files import (_archivos_faltantes, _copiar_arbol, _copiar_archivo,
                    _ignorar_base, _ignorar_runtime, _no_vacio, _norm,
                    _rpa_ok, _sha256, _tam_arbol)
from .mods import (_buscar_raiz_mod, _version_renpy, validar_base,
                   validar_overlay, validar_runtime)
from .platforms import find_launcher, open_launcher


def _agregar_assets(base, staging, log, cancelar, progress):
    base = Path(base)
    staging = Path(staging)
    items = []
    for rel in BASE_ASSETS:
        src, dst = base / rel, staging / rel
        if dst.exists():
            log("Conservado %s del mod." % rel)
        else:
            items.append((src, dst, rel))
    py_src, py_dst = base / BASE_PY, staging / BASE_PY
    py_items = list(_archivos_faltantes(py_src, py_dst))
    items += [(src, dst, str(src.relative_to(base)).replace("\\", "/"))
              for src, dst in py_items]
    total = sum(src.stat().st_size for src, _dst, _rel in items)
    hechos = 0
    for src, dst, rel in items:
        if cancelar and cancelar.is_set():
            raise BuildCancelada()
        dst.parent.mkdir(parents=True, exist_ok=True)
        hechos += _copiar_archivo(src, dst, cancelar, progress,
                                  "Copiando assets", max(total, 1), hechos)
        log("Copiado %s." % rel)
    if not items:
        log("El mod ya tiene todos los assets base.")


def _validar_salida(base, mod, output, needed):
    output = Path(output)
    out_abs = Path(_norm(output))
    for origen in (base, mod):
        origen_abs = Path(_norm(origen))
        if out_abs == origen_abs or origen_abs in out_abs.parents:
            raise BuildError("La salida no puede ser la base, el mod ni "
                             "una carpeta dentro de ellos.")
    if output.exists() and not output.is_dir():
        raise BuildError("La salida existe y no es una carpeta.")
    if _no_vacio(output):
        raise BuildError("La carpeta de salida ya existe y no está vacía.")
    if output.parent == output:
        raise BuildError("Elegí una carpeta de salida válida.")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not any(output.iterdir()):
        output.rmdir()
    libre = shutil.disk_usage(str(output.parent)).free
    if libre < needed:
        raise BuildError("No hay espacio suficiente: faltan %.1f MB."
                         % ((needed - libre) / (1024 * 1024)))
    return output


def _crear_zip(output, log, status, progress, cancelar):
    zip_final = output.with_name(output.name + ".zip")
    if zip_final.exists():
        raise BuildError("Ya existe el ZIP: %s" % zip_final)
    log("Creando ZIP sin compresión...")
    status("Creando ZIP...")
    archivos_zip = sorted(p for p in output.rglob("*") if p.is_file())
    total_zip = len(archivos_zip)
    try:
        with zipfile.ZipFile(zip_final, "w", compression=zipfile.ZIP_STORED,
                             allowZip64=True) as z:
            for i, p in enumerate(archivos_zip, 1):
                if cancelar and cancelar.is_set():
                    raise BuildCancelada()
                arc = output.name + "/" + \
                    str(p.relative_to(output)).replace("\\", "/")
                z.write(p, arc)
                progress("Creando ZIP", i, max(total_zip, 1))
        log("ZIP creado: %s" % zip_final)
    except Exception:
        if zip_final.exists():
            zip_final.unlink()
        raise
    return zip_final


def _compilar_runtime(base, mod, output, incluir_docs=True, crear_zip=False,
                      abrir_juego=False, log=print, status=lambda _s: None,
                      progress=lambda *a: None, cancelar=None):
    base = validar_base(base, solo_assets=True)
    mod = validar_runtime(mod)
    output = Path(output)
    mod_bytes = _tam_arbol(mod, _ignorar_runtime)
    assets_bytes = sum((base / rel).stat().st_size for rel in BASE_ASSETS)
    assets_bytes += _tam_arbol(base / BASE_PY)
    needed = mod_bytes + assets_bytes + MARGEN_DISCO
    if crear_zip:
        needed *= 2
    output = _validar_salida(base, mod, output, needed)
    log("Validación correcta: runtime Ren'Py %s." % _version_renpy(mod))

    staging = Path(tempfile.mkdtemp(prefix=output.name + "-build-",
                                    dir=str(output.parent)))
    try:
        status("Copiando mod...")
        log("Copiando mod...")
        _copiar_arbol(mod, staging, log, cancelar, progress,
                      filtro=_ignorar_runtime, etiqueta="Copiando mod",
                      resumen="Mod copiado")
        if cancelar and cancelar.is_set():
            raise BuildCancelada()

        status("Copiando assets base...")
        log("Agregando assets base...")
        _agregar_assets(base, staging, log, cancelar, progress)

        status("Verificando build...")
        progress("Verificando build", 1, 1)
        for rel in BASE_ASSETS:
            p = staging / rel
            if not p.is_file() or not _rpa_ok(p):
                raise BuildError("Build incompleto: %s." % rel)
        if not (staging / BASE_PY).is_dir():
            raise BuildError("Build incompleto: falta game/python-packages/.")
        exe = find_launcher(staging)
        if exe is None:
            raise BuildError("Build incompleto: no encontré el lanzador del mod.")
        log("Lanzador del mod: %s" % exe.name)

        if output.exists():
            raise BuildError("La salida apareció mientras se compilaba.")
        staging.replace(output)
        log("Carpeta jugable creada: %s" % output)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    zip_final = _crear_zip(output, log, status, progress, cancelar) \
        if crear_zip else None
    status("Listo")
    progress("Listo", 1, 1)

    if abrir_juego:
        exe = find_launcher(output)
        if exe:
            log("Abriendo %s..." % exe.name)
            try:
                open_launcher(exe, cwd=output)
            except Exception as e:
                log("No se pudo abrir el juego: %s" % e)
        else:
            log("No encontré un lanzador para abrir.")

    return output, zip_final


def compilar(base, overlay, output, incluir_docs=True, crear_zip=False,
             abrir_juego=False, log=print, status=lambda _s: None,
             progress=lambda *a: None, cancelar=None):
    """Devuelve la carpeta final y, si se pidió, el ZIP."""
    status("Validando...")
    mod_original = Path(overlay)
    tmp_zip = None
    if mod_original.is_file():
        if mod_original.suffix.lower() != ".zip":
            raise BuildError("El mod debe ser una carpeta o un .zip.")
        tmp_zip = Path(tempfile.mkdtemp(prefix="ddlc-mod-"))
        log("Extrayendo mod ZIP...")
        try:
            from .files import _extraer_zip
            _extraer_zip(mod_original, tmp_zip, cancelar)
            mod_root, tipo = _buscar_raiz_mod(tmp_zip)
        except Exception:
            shutil.rmtree(tmp_zip, ignore_errors=True)
            raise
    else:
        mod_root, tipo = _buscar_raiz_mod(mod_original)
    if tipo is None:
        if tmp_zip:
            shutil.rmtree(tmp_zip, ignore_errors=True)
        raise BuildError("No reconozco el mod: no es overlay ni runtime Ren'Py.")
    try:
        if tipo == "fuente":
            raise BuildError("Es un proyecto fuente Ren'Py. Este modo no usa "
                             "el SDK; seleccioná una distribución ya armada.")
        if tipo == "runtime":
            log("Runtime Ren'Py %s detectado." % _version_renpy(mod_root))
            return _compilar_runtime(
                base, mod_root, output, incluir_docs=incluir_docs,
                crear_zip=crear_zip, abrir_juego=abrir_juego, log=log,
                status=status, progress=progress, cancelar=cancelar)
        base = validar_base(base)
        overlay = validar_overlay(mod_root)

        output = Path(output)
        base_assets = {rel: _sha256(base / rel) for rel in BASE_RPAS[1:]}
        overlay_bytes = sum((overlay / rel).stat().st_size
                            for rel in OVERLAY_RPAS)
        needed = _tam_arbol(base, _ignorar_base) + overlay_bytes + MARGEN_DISCO
        if crear_zip:
            needed *= 2
        output = _validar_salida(base, overlay, output, needed)

        log("Validación correcta.")
        status("Copiando base DDLC...")
        staging = Path(tempfile.mkdtemp(prefix=output.name + "-build-",
                                        dir=str(output.parent)))
        try:
            log("Copiando base DDLC...")
            _copiar_arbol(base, staging, log, cancelar, progress)
            if cancelar and cancelar.is_set():
                raise BuildCancelada()

            firstrun = staging / "game" / "firstrun"
            if firstrun.exists():
                firstrun.unlink()
                log("firstrun eliminado.")

            status("Copiando overlay...")
            overlay_done = 0
            for rel in OVERLAY_RPAS:
                src = overlay / rel
                dst = staging / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                overlay_done += _copiar_archivo(
                    src, dst, cancelar, progress, "Copiando overlay",
                    max(overlay_bytes, 1), overlay_done)
                if cancelar and cancelar.is_set():
                    raise BuildCancelada()
                if _sha256(src) != _sha256(dst):
                    raise BuildError("No se copió bien %s." % rel)
                log("Copiado %s." % rel)

            if incluir_docs:
                for nombre in DOCS:
                    src = overlay / nombre
                    if src.is_file():
                        shutil.copy2(src, staging / nombre)
                        log("Copiado %s." % nombre)

            if (staging / "game" / "firstrun").exists():
                raise BuildError("firstrun sigue presente en el build.")
            log("Verificando build...")
            status("Verificando build...")
            progress("Verificando build", 1, 1)
            for rel in BASE_RPAS:
                p = staging / rel
                if not p.is_file() or not _rpa_ok(p):
                    raise BuildError("Build incompleto: %s." % rel)
            for rel, hash_base in base_assets.items():
                if _sha256(staging / rel) != hash_base:
                    raise BuildError("Se modificó un asset base: %s." % rel)

            if output.exists():
                raise BuildError("La salida apareció mientras se compilaba.")
            staging.replace(output)
            log("Carpeta jugable creada: %s" % output)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

        zip_final = _crear_zip(
            output, log, status, progress, cancelar) if crear_zip else None
        status("Listo")
        progress("Listo", 1, 1)

        if abrir_juego:
            exe = find_launcher(output)
            if exe:
                log("Abriendo %s..." % exe.name)
                try:
                    open_launcher(exe, cwd=output)
                except Exception as e:
                    log("No se pudo abrir el juego: %s" % e)
            else:
                log("No encontré un lanzador para abrir.")

        return output, zip_final
    finally:
        if tmp_zip:
            shutil.rmtree(tmp_zip, ignore_errors=True)
