"""Cheap pre-build checks and a summary for the UI."""
import shutil
from pathlib import Path

from .builder import validar_rutas
from .errors import BuildError
from .files import _no_vacio
from .mods import (_buscar_raiz_mod, _version_renpy, base_info, detectar_mod,
                   validar_base, validar_overlay, validar_runtime)


def _free_space(path):
    path = Path(path)
    while not path.exists() and path.parent != path:
        path = path.parent
    try:
        return shutil.disk_usage(str(path)).free
    except OSError:
        return 0


def format_report(report, prompt=True):
    """Format a preflight report for the build dialog or dev tools."""
    mode = ("DDLC overlay" if report["mode"] == "overlay"
            else "Ren'Py runtime")
    if report["mode"] == "runtime" and report["version"]:
        mode += " " + report["version"]
    base = report["base_edition"] or "Unknown base"
    if report["base_version"]:
        base += " (Ren'Py %s)" % report["base_version"]
    action = ("Replace the existing build (temporary backup)"
              if report["replace"] else "Create a new build")
    lines = [
        "Build summary" if prompt else "Build diagnostics",
        "",
        "Mode: %s" % mode,
        "Base: %s" % base,
        "Output: %s" % report["output"],
        "Action: %s" % action,
    ]
    if report["zip"]:
        lines.append("ZIP: %s" % (
            "replace existing" if report["zip_replace"] else "create"))
    lines.append("Free space: %.1f GB" % (
        report["free"] / (1024 ** 3)))
    if report["warnings"]:
        lines += ["", "Warnings:"] + [
            "- %s" % warning for warning in report["warnings"]]
    if prompt:
        lines += ["", "Continue?"]
    return "\n".join(lines)


def preflight(base, mod, output, crear_zip=False, overwrite=False):
    """Return a build summary; raise BuildError on clear problems."""
    base = Path(base)
    mod = Path(mod)
    output = validar_rutas(base, mod, output)
    tipo, version = detectar_mod(mod)
    if tipo == "fuente":
        raise BuildError("This is a Ren'Py source project. This mode does "
                         "not use the SDK; select a prebuilt distribution.")
    if tipo == "overlay":
        validar_base(base)
        if mod.is_dir():
            root, _tipo = _buscar_raiz_mod(mod)
            if root is not None:
                validar_overlay(root)
    else:
        validar_base(base, solo_assets=True)
        if mod.is_dir():
            root, _tipo = _buscar_raiz_mod(mod)
            if root is not None:
                validar_runtime(root)

    warnings = []
    if tipo == "overlay":
        major = _version_renpy(base)
        if not major:
            warnings.append("Could not detect the base Ren'Py version; "
                            "overlay compatibility is unknown.")
        elif major != "6":
            raise BuildError("This overlay targets DDLC 1.x (Ren'Py 6), "
                             "but the base is Ren'Py %s." % major)

    if _no_vacio(output) and not overwrite:
        raise BuildError("Output folder already exists and is not empty.")
    zip_path = output.with_name(output.name + ".zip") if crear_zip else None
    zip_replace = bool(zip_path and zip_path.exists())
    if zip_replace and not overwrite:
        raise BuildError("ZIP already exists: %s" % zip_path)
    if zip_replace:
        warnings.append("The existing ZIP will be replaced.")

    version_base, edition = base_info(base)
    return {
        "mode": tipo,
        "version": version,
        "base_version": version_base,
        "base_edition": edition,
        "output": str(output),
        "replace": bool(overwrite and _no_vacio(output)),
        "zip": str(zip_path) if zip_path else "",
        "zip_replace": zip_replace,
        "free": _free_space(output.parent),
        "warnings": warnings,
    }
