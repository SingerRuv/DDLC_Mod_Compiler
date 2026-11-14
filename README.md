# DDLC Compiler

Cross-platform tool for building playable DDLC mods. It supports two mod structures:

- **Overlay:** a clean DDLC base plus `game/scripts.rpa` and `game/mod_assets.rpa`.
- **Prebuilt runtime:** a mod that already includes its own Ren'Py 7/8 runtime (`.exe`, `.app`, `lib/`, `renpy/`) and only needs the DDLC base assets.

The tool does not use the Ren'Py SDK. ZIP creation is optional and stored without compression.

## Download

The latest Windows, Linux, macOS Intel, and macOS Apple Silicon builds are available from GitHub Actions:

https://github.com/SingerRuv/DDLC_Compiler/actions

The Windows executable is also included at:

```text
DDLCCompiler/DDLCCompiler.exe
```

On macOS, the app is unsigned. Open it with right-click > Open.

## Features

- Automatic detection of DDLC overlays and prebuilt Ren'Py runtimes.
- Ren'Py 7 and Ren'Py 8 runtime detection.
- Optional output ZIP.
- Progress bar, status messages, spinner, cancellation, and logging.
- Safe ZIP extraction and free-space checks.
- No modification of the original base or mod.
- English interface and documentation.

## Requirements

- **Windows:** `DDLCCompiler.exe` does not require Python.
- **macOS:** `DDLCCompiler.app`; no signing or notarization.
- **Linux:** the `DDLCCompiler` binary; Tkinter is bundled by PyInstaller.
- **From source:** Python 3 with Tkinter.

DDLC base:

- **Overlay mode:** launcher (`DDLC.exe`, `DDLC.sh`, or `DDLC.app`), `game/scripts.rpa`, `images.rpa`, `audio.rpa`, `fonts.rpa`, `lib/`, and `renpy/`.
- **Runtime mode:** `game/images.rpa`, `game/audio.rpa`, `game/fonts.rpa`, and `game/python-packages/`. The base runtime is not copied.

Mod:

- **Overlay:** `game/scripts.rpa` plus `game/mod_assets.rpa`.
- **Runtime:** `game/`, `lib/`, `renpy/`, and the mod launcher. It can be a folder or a ZIP.

## Usage

1. Open the tool:
   - Windows: `DDLCCompiler/DDLCCompiler.exe` or `DDLCCompiler/DDLCCompiler.bat`.
   - macOS: `DDLCCompiler.app`.
   - Linux: `./DDLCCompiler`.
2. Select the DDLC base.
3. Select the mod folder or ZIP. The tool displays the detected mode:
   - `DDLC overlay`
   - `Runtime Ren'Py 7` / `Runtime Ren'Py 8`
   - `Source project (unsupported)`
4. Select the output folder. The default is `<mod> (Compiled)`.
5. Choose the options:
   - include `Credits.txt`, `ThankYou.txt`, and `README.html` (overlay only);
   - create an uncompressed ZIP;
   - open the game when finished.
6. Build.

## What It Does

### Overlay

- Copies the complete DDLC base.
- Excludes `saves`, `cache`, `firstrun`, and `*.rpyc` from the base.
- Replaces `game/scripts.rpa` and adds `game/mod_assets.rpa`.
- Copies documents when selected.
- Verifies base and overlay RPA hashes.

### Prebuilt Runtime

- Copies the **entire** mod folder: launcher, `lib/`, `renpy/`, and `game/`.
- Preserves `game/scripts.rpa`, `game/mod_assets.rpa`, docs, and the rest of the mod.
- Adds only the missing DDLC base assets:
  - `game/images.rpa`
  - `game/audio.rpa`
  - `game/fonts.rpa`
  - `game/python-packages/` (standard Ren'Py 7 name)
- Does not copy the base launcher, `scripts.rpa`, `lib/`, or `renpy/`.
- Detects Ren'Py 7/8 from `lib/py2-*` or `lib/py3-*`.
- Opens the mod launcher: `.exe`, `.app`, or `.sh` depending on the platform.

### General

- Validates the base and mod before copying.
- Rejects unsafe ZIP paths, symlinks, and oversized archives.
- Checks free disk space.
- Copies in chunks and supports cancellation.
- Shows a progress bar, status label, and spinner.
- Does not modify the original base or mod.
- If closed during a build, asks for confirmation and cleans the staging folder.

## Repository Layout

```text
DDLC_Compiler/
├── README.md
├── .github/workflows/build.yml
└── DDLCCompiler/
    ├── DDLCCompiler.exe
    ├── DDLCCompiler.bat
    ├── DDLCCompiler.py
    ├── DDLC.ico
    ├── icon.png
    ├── icon.icns
    ├── ddlc_compiler/
    │   ├── app.py
    │   ├── builder.py
    │   ├── config.py
    │   ├── errors.py
    │   ├── files.py
    │   ├── mods.py
    │   ├── platforms.py
    │   ├── __init__.py
    │   └── __main__.py
    └── build/
        ├── build_windows.ps1
        ├── build_linux.sh
        ├── build_macos.sh
        └── requirements-build.txt
```

## Build

Windows:

```powershell
.\DDLCCompiler\build\build_windows.ps1
```

Linux:

```sh
bash DDLCCompiler/build/build_linux.sh
```

macOS:

```sh
bash DDLCCompiler/build/build_macos.sh
```

Artifacts are written to `DDLCCompiler/dist/`.

GitHub Actions builds Windows, Linux, macOS Intel, and macOS Apple Silicon automatically and publishes the artifacts.

Native binaries must be built on their target operating system. Windows cannot cross-compile macOS or Linux.

## Notes

- Source projects (`game/*.rpy` without a runtime) are not built: they need the corresponding SDK.
- Build MySilverLining with `DDLC-1.1.1-pc` as the base and `MySilverLining-0.6d-Renpy7Mod` as the mod.
- MySilverLining's README mentions `python_packages`; the standard `python-packages` folder is used because that is what Ren'Py 7 loads.
- The optional ZIP is stored without compression, which is much faster for large builds.
- The log is written next to the executable on Windows and to `~/.ddlc_compiler/DDLCCompiler.log` on macOS/Linux.
- If the output folder exists and is not empty, the tool stops instead of overwriting files.
- macOS builds are unsigned and not notarized.
- Linux builds target Ubuntu 22.04; compatibility depends on the destination glibc version.

## License and Disclaimer

The source code of this project is licensed under the MIT License. See [LICENSE](LICENSE).

This is an unofficial, fan-made tool. It is not affiliated with, endorsed by, sponsored by, or associated with Team Salvato.

Doki Doki Literature Club! and related names, characters, and assets are the property of Team Salvato. This tool does not distribute DDLC game files. Mods and third-party assets remain subject to their respective authors' licenses.

Third-party components included in the packaged builds, including Python, Tkinter, and PyInstaller, retain their own licenses.
