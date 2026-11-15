"""DDLC Mod Compiler build pipeline."""
import shutil
import tempfile
import zipfile
from pathlib import Path

from .config import (BASE_ASSETS, BASE_PY, BASE_RPAS, DOCS, MARGEN_DISCO,
                     OVERLAY_RPAS, PHASE_COPY_ASSETS, PHASE_COPY_MOD,
                     PHASE_COPY_OVERLAY, PHASE_VERIFY, PHASE_ZIP)
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
            log("Kept %s from the mod." % rel)
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
                                  PHASE_COPY_ASSETS, max(total, 1), hechos)
        log("Copied %s." % rel)
    if not items:
        log("The mod already has all base assets.")


def _validar_salida(base, mod, output, needed, overwrite=False):
    output = Path(output)
    out_abs = Path(_norm(output))
    for origen in (base, mod):
        origen_abs = Path(_norm(origen))
        if out_abs == origen_abs or origen_abs in out_abs.parents:
            raise BuildError("Output cannot be the base, the mod, or "
                             "a folder inside them.")
    if output.exists() and not output.is_dir():
        raise BuildError("Output exists and is not a folder.")
    if _no_vacio(output) and not overwrite:
        raise BuildError("Output folder already exists and is not empty.")
    if output.parent == output:
        raise BuildError("Choose a valid output folder.")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not any(output.iterdir()):
        output.rmdir()
    libre = shutil.disk_usage(str(output.parent)).free
    if libre < needed:
        raise BuildError("Not enough free space: %.1f MB missing."
                         % ((needed - libre) / (1024 * 1024)))
    return output


def _instalar_salida(staging, output):
    """Swap a completed build into place, restoring the old one on failure."""
    backup = None
    if output.exists():
        backup = output.with_name(output.name + ".ddlc-backup")
        n = 2
        while backup.exists():
            backup = output.with_name("%s.ddlc-backup-%d" % (output.name, n))
            n += 1
        output.rename(backup)
    try:
        staging.replace(output)
    except Exception:
        if backup and not output.exists():
            backup.rename(output)
        raise
    if backup:
        shutil.rmtree(backup, ignore_errors=True)


def _crear_zip(output, log, status, progress, cancelar, overwrite=False):
    zip_final = output.with_name(output.name + ".zip")
    if zip_final.exists() and not overwrite:
        raise BuildError("ZIP already exists: %s" % zip_final)
    zip_tmp = zip_final.with_name(zip_final.name + ".tmp")
    if zip_tmp.exists():
        zip_tmp.unlink()
    log("Creating uncompressed ZIP...")
    status("Creating ZIP...")
    archivos_zip = sorted(p for p in output.rglob("*") if p.is_file())
    total_zip = len(archivos_zip)
    try:
        with zipfile.ZipFile(zip_tmp, "w", compression=zipfile.ZIP_STORED,
                             allowZip64=True) as z:
            for i, p in enumerate(archivos_zip, 1):
                if cancelar and cancelar.is_set():
                    raise BuildCancelada()
                arc = output.name + "/" + \
                    str(p.relative_to(output)).replace("\\", "/")
                z.write(p, arc)
                progress(PHASE_ZIP, i, max(total_zip, 1))
        if zip_final.exists():
            zip_final.unlink()
        zip_tmp.replace(zip_final)
        log("ZIP created: %s" % zip_final)
    except Exception:
        if zip_tmp.exists():
            zip_tmp.unlink()
        raise
    return zip_final


def _abrir_juego(output, log):
    exe = find_launcher(output)
    if exe:
        log("Opening %s..." % exe.name)
        try:
            open_launcher(exe, cwd=output)
        except Exception as exc:
            log("Could not open the game: %s" % exc)
    else:
        log("No launcher found to open.")


def _finalizar_build(output, staging, crear_zip, overwrite, abrir_juego,
                     log, status, progress, cancelar):
    if output.exists() and not overwrite:
        raise BuildError("Output appeared while building.")
    _instalar_salida(staging, output)
    log("Playable folder created: %s" % output)
    zip_final = _crear_zip(output, log, status, progress, cancelar,
                           overwrite=overwrite) if crear_zip else None
    status("Ready")
    progress("Ready", 1, 1)
    if abrir_juego:
        _abrir_juego(output, log)
    return output, zip_final


def _compilar_runtime(base, mod, output, incluir_docs=True, crear_zip=False,
                      abrir_juego=False, log=print, status=lambda _s: None,
                      progress=lambda *a: None, cancelar=None, overwrite=False):
    base = validar_base(base, solo_assets=True)
    mod = validar_runtime(mod)
    output = Path(output)
    mod_bytes = _tam_arbol(mod, _ignorar_runtime)
    assets_bytes = sum((base / rel).stat().st_size for rel in BASE_ASSETS)
    assets_bytes += _tam_arbol(base / BASE_PY)
    needed = mod_bytes + assets_bytes + MARGEN_DISCO
    if overwrite and output.exists():
        needed += _tam_arbol(output)
    if crear_zip:
        needed *= 2
    output = _validar_salida(base, mod, output, needed, overwrite)
    log("Validation OK: Ren'Py %s runtime." % _version_renpy(mod))

    staging = Path(tempfile.mkdtemp(prefix=output.name + "-build-",
                                    dir=str(output.parent)))
    try:
        status("Copying mod...")
        log("Copying mod...")
        _copiar_arbol(mod, staging, log, cancelar, progress,
                      filtro=_ignorar_runtime, etiqueta=PHASE_COPY_MOD,
                      resumen="Mod copied")
        if cancelar and cancelar.is_set():
            raise BuildCancelada()

        status("Copying base assets...")
        log("Adding base assets...")
        _agregar_assets(base, staging, log, cancelar, progress)

        status("Verifying build...")
        progress(PHASE_VERIFY, 1, 1)
        for rel in BASE_ASSETS:
            p = staging / rel
            if not p.is_file() or not _rpa_ok(p):
                raise BuildError("Incomplete build: %s." % rel)
        if not (staging / BASE_PY).is_dir():
            raise BuildError("Incomplete build: missing game/python-packages/.")
        exe = find_launcher(staging)
        if exe is None:
            raise BuildError("Incomplete build: mod launcher not found.")
        log("Mod launcher: %s" % exe.name)

        result = _finalizar_build(
            output, staging, crear_zip, overwrite, abrir_juego, log,
            status, progress, cancelar)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return result


def compilar(base, overlay, output, incluir_docs=True, crear_zip=False,
             abrir_juego=False, log=print, status=lambda _s: None,
             progress=lambda *a: None, cancelar=None, overwrite=False):
    """Return the final folder and, if requested, the ZIP."""
    status("Validating...")
    mod_original = Path(overlay)
    tmp_zip = None
    if mod_original.is_file():
        if mod_original.suffix.lower() != ".zip":
            raise BuildError("The mod must be a folder or .zip.")
        tmp_zip = Path(tempfile.mkdtemp(prefix="ddlc-mod-"))
        log("Extracting mod ZIP...")
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
        raise BuildError("Unrecognized mod: not an overlay or Ren'Py runtime.")
    try:
        if tipo == "fuente":
            raise BuildError("This is a Ren'Py source project. This mode does "
                             "not use the SDK; select a prebuilt distribution.")
        if tipo == "runtime":
            log("Ren'Py %s runtime detected." % _version_renpy(mod_root))
            return _compilar_runtime(
                base, mod_root, output, incluir_docs=incluir_docs,
                crear_zip=crear_zip, abrir_juego=abrir_juego, log=log,
                status=status, progress=progress, cancelar=cancelar,
                overwrite=overwrite)
        base = validar_base(base)
        overlay = validar_overlay(mod_root)

        output = Path(output)
        base_assets = {rel: _sha256(base / rel) for rel in BASE_RPAS[1:]}
        overlay_bytes = sum((overlay / rel).stat().st_size
                            for rel in OVERLAY_RPAS)
        needed = _tam_arbol(base, _ignorar_base) + overlay_bytes + MARGEN_DISCO
        if overwrite and output.exists():
            needed += _tam_arbol(output)
        if crear_zip:
            needed *= 2
        output = _validar_salida(base, overlay, output, needed, overwrite)

        log("Validation OK.")
        status("Copying DDLC base...")
        staging = Path(tempfile.mkdtemp(prefix=output.name + "-build-",
                                        dir=str(output.parent)))
        try:
            log("Copying DDLC base...")
            _copiar_arbol(base, staging, log, cancelar, progress)
            if cancelar and cancelar.is_set():
                raise BuildCancelada()

            firstrun = staging / "game" / "firstrun"
            if firstrun.exists():
                firstrun.unlink()
                log("firstrun removed.")

            status("Copying overlay...")
            overlay_done = 0
            for rel in OVERLAY_RPAS:
                src = overlay / rel
                dst = staging / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                overlay_done += _copiar_archivo(
                    src, dst, cancelar, progress, PHASE_COPY_OVERLAY,
                    max(overlay_bytes, 1), overlay_done)
                if cancelar and cancelar.is_set():
                    raise BuildCancelada()
                if _sha256(src) != _sha256(dst):
                    raise BuildError("Could not copy %s correctly." % rel)
                log("Copied %s." % rel)

            if incluir_docs:
                for nombre in DOCS:
                    src = overlay / nombre
                    if src.is_file():
                        shutil.copy2(src, staging / nombre)
                        log("Copied %s." % nombre)

            if (staging / "game" / "firstrun").exists():
                raise BuildError("firstrun is still present in the build.")
            log("Verifying build...")
            status("Verifying build...")
            progress(PHASE_VERIFY, 1, 1)
            for rel in BASE_RPAS:
                p = staging / rel
                if not p.is_file() or not _rpa_ok(p):
                    raise BuildError("Incomplete build: %s." % rel)
            for rel, hash_base in base_assets.items():
                if _sha256(staging / rel) != hash_base:
                    raise BuildError("A base asset was modified: %s." % rel)

            result = _finalizar_build(
                output, staging, crear_zip, overwrite, abrir_juego, log,
                status, progress, cancelar)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

        return result
    finally:
        if tmp_zip:
            shutil.rmtree(tmp_zip, ignore_errors=True)
