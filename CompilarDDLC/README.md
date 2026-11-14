# Compilar DDLC

Herramienta multiplataforma para armar una copia jugable de mods DDLC. Soporta dos estructuras:

- **Overlay:** base DDLC limpia + `game/scripts.rpa` + `game/mod_assets.rpa`.
- **Runtime prearmado:** mod que ya trae su propio Ren’Py 7 u 8 (`.exe`, `.app`, `lib/`, `renpy/`) y solo necesita los assets base de DDLC.

No usa el SDK de Ren’Py. El ZIP es opcional y se guarda sin comprimir.

## Requisitos

- **Windows:** `CompilarDDLC.exe` no necesita Python.
- **macOS:** `CompilarDDLC.app`; al no estar firmada, se abre con clic derecho > Abrir.
- **Linux:** binario `CompilarDDLC`; requiere Tkinter empaquetado por PyInstaller.
- Para ejecutar desde código: Python 3 con Tkinter.

Base DDLC:

- **Modo overlay:** lanzador (`DDLC.exe`, `DDLC.sh` o `DDLC.app`), `game/scripts.rpa`, `images.rpa`, `audio.rpa`, `fonts.rpa`, `lib/` y `renpy/`.
- **Modo runtime:** los assets `game/images.rpa`, `game/audio.rpa`, `game/fonts.rpa` y `game/python-packages/`. No se copia el runtime de la base.

Mod:

- **Overlay:** `game/scripts.rpa` + `game/mod_assets.rpa`.
- **Runtime:** `game/`, `lib/`, `renpy/` y el lanzador del mod. Puede venir en carpeta o ZIP.

## Uso

1. Abrí la herramienta:
   - Windows: `CompilarDDLC.exe` o `Compilar DDLC.bat`.
   - macOS: `CompilarDDLC.app`.
   - Linux: `./CompilarDDLC`.
2. Elegí la base DDLC.
3. Elegí el mod: carpeta o ZIP. La herramienta detecta y muestra el modo:
   - `Overlay DDLC`
   - `Runtime Ren’Py 7` / `Runtime Ren’Py 8`
   - `proyecto fuente (no soportado)`
4. Elegí la salida. Por defecto se propone `<mod> (Compilado)`.
5. Opciones:
   - incluir `Credits.txt`, `ThankYou.txt` y `README.html` (solo overlay);
   - crear un ZIP sin compresión;
   - abrir el juego al finalizar.
6. Compilar.

## Qué hace

### Overlay

- Copia la base DDLC completa.
- Excluye `saves`, `cache`, `firstrun` y `*.rpyc` de la base.
- Reemplaza `game/scripts.rpa` y agrega `game/mod_assets.rpa`.
- Copia los documentos si están tildados.
- Verifica hashes de los RPA base y del overlay.

### Runtime prearmado

- Copia **toda** la carpeta del mod: lanzador, `lib/`, `renpy/` y `game/`.
- Conserva `game/scripts.rpa`, `game/mod_assets.rpa`, docs y demás archivos del mod.
- Agrega desde la base DDLC solo lo que falte:
  - `game/images.rpa`
  - `game/audio.rpa`
  - `game/fonts.rpa`
  - `game/python-packages/` (nombre estándar de Ren’Py 7)
- No copia el lanzador, `scripts.rpa`, `lib/` ni `renpy/` de la base.
- Detecta Ren’Py 7/8 por `lib/py2-*` o `lib/py3-*`.
- Abre el lanzador del mod: `.exe`, `.app` o `.sh` según el sistema.

### General

- Valida la base y el mod antes de copiar.
- Detecta ZIPs con rutas peligrosas, symlinks y tamaños excesivos.
- Comprueba espacio libre.
- Copia por bloques y permite cancelar.
- Muestra barra de progreso, estado y spinner.
- No modifica la base ni el mod originales.
- Si cerrás durante el build, pide confirmación y limpia el staging.

## Estructura

```text
CompilarDDLC/
├── CompilarDDLC.exe
├── Compilar DDLC.bat
├── CompilarDDLC.py          # lanzador
├── icono DDLC.ico
├── icono.png                # Linux/macOS
├── icono.icns               # macOS
├── README.md
├── compilar_ddlc/
│   ├── app.py               # GUI
│   ├── builder.py           # builds overlay/runtime
│   ├── config.py            # constantes y rutas
│   ├── errors.py
│   ├── files.py             # copia, hashes y ZIP
│   ├── mods.py              # detección y validación
│   ├── platforms.py         # lanzadores y apertura por SO
│   ├── __init__.py
│   └── __main__.py
├── build/
│   ├── build_windows.ps1
│   ├── build_linux.sh
│   ├── build_macos.sh
│   └── requirements-build.txt
└── .github/workflows/build.yml
```

## Build

Windows:

```powershell
.\build\build_windows.ps1
```

Linux:

```sh
bash build/build_linux.sh
```

macOS:

```sh
bash build/build_macos.sh
```

Los artefactos quedan en `dist/`.

GitHub Actions compila automáticamente Windows, Linux, macOS Intel y macOS Apple Silicon, y publica los artefactos.

Los binarios nativos se generan en cada sistema operativo: Windows no puede cross-compilar macOS/Linux.

## Notas

- Proyectos fuente (`game/*.rpy` sin runtime) no se compilan: requieren el SDK correspondiente.
- MySilverLining se arma eligiendo `DDLC-1.1.1-pc` como base y `MySilverLining-0.6d-Renpy7Mod` como mod.
- El README de MySilverLining pide `python_packages`; se usa el nombre estándar `python-packages`, que es el que carga Ren’Py 7.
- El ZIP opcional se guarda sin compresión; para builds grandes tarda mucho menos.
- El log queda en `CompilarDDLC.log` junto al ejecutable en Windows, y en `~/.compilar_ddlc/CompilarDDLC.log` en macOS/Linux.
- Si la salida existe y no está vacía, la herramienta se detiene para no pisar archivos.
- Los builds de macOS no están firmados ni notarizados.
- Los builds de Linux se generan en Ubuntu 22.04; la compatibilidad depende de la glibc del sistema destino.
