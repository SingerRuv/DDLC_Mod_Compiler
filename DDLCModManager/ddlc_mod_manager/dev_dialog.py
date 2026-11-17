"""Developer tools dialog."""
import queue
import shutil
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import devtools, rpa, theme
from .config import DATA_DIR, MODS_ROOT
from .platforms import open_path
from .preflight import format_report, preflight

TEST_MODS = DATA_DIR / "dev-mods"


class DevToolsDialog(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self._closed = False
        self._extract_thread = None
        self._extract_queue = None
        self.rpa_folder = None
        self.overwrite = tk.BooleanVar(value=False)
        self.status = tk.StringVar()
        self.cache_label = tk.StringVar()
        self.test_status = tk.StringVar()
        self.rpa_label = tk.StringVar(value="No folder selected.")
        self.rpa_status = tk.StringVar()
        self.title("Developer tools")
        self.transient(app)
        self.resizable(False, False)
        self.configure(bg=theme.palette(app.dark)["bg"])
        self._build()
        self._refresh_status()
        self._cache_info()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.update_idletasks()
        width, height = self.winfo_reqwidth(), self.winfo_reqheight()
        x = app.winfo_rootx() + (app.winfo_width() - width) // 2
        y = app.winfo_rooty() + (app.winfo_height() - height) // 2
        self.geometry("+%d+%d" % (max(0, x), max(0, y)))

    def _build(self):
        p = theme.palette(self.app.dark)
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.columnconfigure(1, weight=1)

        top = ttk.Frame(outer)
        top.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(top, textvariable=self.status).pack(side="left")
        ttk.Button(top, text="Reload now", command=self.reload).pack(
            side="right")
        self.pause_button = ttk.Button(
            top, text="Pause", command=self.toggle_pause)
        self.pause_button.pack(side="right", padx=(0, 6))
        ttk.Button(top, text="Open log", command=self.open_log).pack(
            side="right", padx=(0, 6))

        diag = ttk.Frame(outer)
        diag.grid(row=1, column=0, sticky="nsew", padx=(0, 8), pady=(12, 0))
        ttk.Label(diag, text="Build diagnostics",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Button(diag, text="Check current build",
                   command=self.check_build).pack(anchor="w", pady=(4, 4))
        self.report = tk.Text(
            diag, height=10, width=46, wrap="word", state="disabled",
            bg=p["entry"], fg=p["text"], insertbackground=p["text"],
            relief="flat", bd=0)
        self.report.pack(fill="both", expand=True)

        right = ttk.Frame(outer)
        right.grid(row=1, column=1, sticky="nsew", pady=(12, 0))
        ttk.Label(right, text="Cache",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(right, textvariable=self.cache_label,
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 4))
        cache_buttons = ttk.Frame(right)
        cache_buttons.pack(anchor="w")
        ttk.Button(cache_buttons, text="Clear logo cache",
                   command=self.clear_cache).pack(side="left")
        ttk.Button(cache_buttons, text="Reset Launcher",
                   command=self.reset_launcher).pack(side="left", padx=(6, 0))

        tests = ttk.Frame(right)
        tests.pack(fill="x", pady=(14, 0))
        ttk.Label(tests, text="Test data",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(tests, text="Layout-only mods; not runnable.",
                  style="Muted.TLabel").pack(anchor="w")
        test_buttons = ttk.Frame(tests)
        test_buttons.pack(anchor="w", pady=(4, 0))
        ttk.Button(test_buttons, text="Generate test mods",
                   command=self.make_test_mods).pack(side="left")
        ttk.Button(test_buttons, text="Remove test mods",
                   command=self.remove_test_mods).pack(
            side="left", padx=(6, 0))
        ttk.Label(tests, textvariable=self.test_status,
                  wraplength=320).pack(anchor="w", pady=(4, 0))

        extract = ttk.Frame(outer)
        extract.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        ttk.Label(extract, text="Extract RPA (dev only)",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w")
        row = ttk.Frame(extract)
        row.pack(fill="x", pady=(4, 0))
        ttk.Button(row, text="Choose mod folder...",
                   command=self.choose_rpa_folder).pack(side="left")
        ttk.Label(row, textvariable=self.rpa_label,
                  style="Muted.TLabel").pack(side="left", padx=(8, 0))
        row = ttk.Frame(extract)
        row.pack(fill="x", pady=(4, 0))
        ttk.Checkbutton(row, text="Overwrite existing loose files",
                        variable=self.overwrite).pack(side="left")
        self.extract_button = ttk.Button(
            row, text="Extract RPAs", command=self.extract_rpas)
        self.extract_button.pack(side="left", padx=(8, 0))
        ttk.Button(row, text="Open folder",
                   command=self.open_rpa_folder).pack(
            side="left", padx=(6, 0))
        ttk.Label(extract, textvariable=self.rpa_status,
                  wraplength=720).pack(anchor="w", pady=(4, 0))
        ttk.Label(extract, text=(
            "The RPA files are kept, so the mod stays playable. "
            "Scripts are extracted as .rpyc; use a decompiler to edit them."),
            style="Muted.TLabel", wraplength=720).pack(
            anchor="w", pady=(2, 0))

        ttk.Button(outer, text="Close", command=self._close).grid(
            row=3, column=0, columnspan=2, pady=(14, 0))

    def _set_report(self, text):
        self.report.configure(state="normal")
        self.report.delete("1.0", "end")
        self.report.insert("1.0", text)
        self.report.configure(state="disabled")

    def _refresh_status(self):
        app = self.app
        if app._supervised:
            text = "Live Reload: external (dev_reload.py)"
            state = "disabled"
        elif not app._source_available:
            text = "Live Reload: unavailable (packaged)"
            state = "disabled"
        elif app._dev_paused:
            text = "Live Reload: paused"
            state = "normal"
        else:
            text = "Live Reload: watching"
            state = "normal"
        self.status.set(text)
        self.pause_button.configure(
            text="Resume" if app._dev_paused else "Pause", state=state)

    def reload(self):
        self.app._dev_reload_shortcut()
        self._refresh_status()

    def toggle_pause(self):
        self.app._dev_pause_shortcut()
        self._refresh_status()

    def open_log(self):
        self.app._open_log()

    def check_build(self):
        compiler = self.app.compiler
        base = compiler.base.get().strip()
        mod = compiler.overlay.get().strip()
        output = compiler.output.get().strip()
        if not (base and mod and output):
            self._set_report("Select the base, mod, and output first.")
            return
        try:
            report = preflight(base, mod, output,
                               crear_zip=compiler.zip.get(), overwrite=True)
        except Exception as exc:
            self._set_report("Cannot build:\n%s" % exc)
            return
        self._set_report(format_report(report, prompt=False))

    def _cache_info(self):
        cache = DATA_DIR / "logo-cache"
        files = []
        try:
            if cache.is_dir():
                files = [path for path in cache.rglob("*") if path.is_file()]
        except OSError:
            files = []
        size = 0
        for path in files:
            try:
                size += path.stat().st_size
            except OSError:
                pass
        self.cache_label.set("Logo cache: %d files, %.1f MB" % (
            len(files), size / (1024 * 1024)))

    def clear_cache(self):
        if not messagebox.askyesno(
                "Clear logo cache",
                "Delete the logo cache and rescan mods?", parent=self):
            return
        self.app.launcher.clear_logo_cache()
        self._cache_info()
        self.test_status.set("Logo cache cleared; rescanning.")

    def reset_launcher(self):
        if not messagebox.askyesno(
                "Reset Launcher",
                "Forget external folders and imported mods?", parent=self):
            return
        self.app.launcher.reset_state()
        self._cache_info()
        self.test_status.set("Launcher state reset; rescanning.")

    def make_test_mods(self):
        try:
            created = devtools.make_test_mods(TEST_MODS)
        except OSError as exc:
            messagebox.showerror("Test data", str(exc), parent=self)
            return
        self.app.launcher.add_root(TEST_MODS)
        self.test_status.set("Generated %d test mods in %s." % (
            len(created), TEST_MODS))

    def remove_test_mods(self):
        if not messagebox.askyesno(
                "Remove test mods", "Delete the test mods folder?",
                parent=self):
            return
        shutil.rmtree(TEST_MODS, ignore_errors=True)
        self.app.launcher.remove_root(TEST_MODS)
        self.test_status.set("Test mods removed.")

    def choose_rpa_folder(self):
        start = MODS_ROOT if MODS_ROOT.is_dir() else Path.home()
        path = filedialog.askdirectory(
            title="Mod folder to extract", parent=self,
            initialdir=str(start))
        if path:
            self.rpa_folder = Path(path)
            self.rpa_label.set(str(self.rpa_folder))

    def open_rpa_folder(self):
        if self.rpa_folder is not None:
            open_path(str(self.rpa_folder))

    def extract_rpas(self):
        if self._extract_thread is not None:
            return
        if self.rpa_folder is None or not self.rpa_folder.is_dir():
            messagebox.showwarning(
                "Extract RPA", "Choose a mod folder first.", parent=self)
            return
        game = self.rpa_folder / "game"
        root = game if game.is_dir() else self.rpa_folder
        archives = sorted(root.rglob("*.rpa"))
        if not archives:
            messagebox.showinfo(
                "Extract RPA", "No .rpa files found in that folder.",
                parent=self)
            return
        if not messagebox.askyesno(
                "Extract RPA",
                "Extract %d RPA file(s) next to their archives?\n"
                "The RPA files are kept." % len(archives), parent=self):
            return
        self.extract_button.configure(state="disabled")
        self.rpa_status.set("Extracting %d RPA file(s)..." % len(archives))
        self._extract_queue = queue.Queue()
        self._extract_thread = threading.Thread(
            target=self._extract_worker,
            args=(archives, self.overwrite.get()), daemon=True)
        self._extract_thread.start()
        self.after(100, self._poll_extract)

    def _extract_worker(self, archives, overwrite):
        total = {"files": 0, "skipped": 0, "bytes": 0}
        try:
            for archive in archives:
                result = rpa.extract_archive(
                    archive, archive.parent, overwrite=overwrite)
                for key in total:
                    total[key] += result[key]
            self._extract_queue.put(("done", total))
        except Exception as exc:
            self._extract_queue.put(("error", str(exc)))

    def _poll_extract(self):
        if self._closed:
            return
        try:
            kind, payload = self._extract_queue.get_nowait()
        except queue.Empty:
            self.after(100, self._poll_extract)
            return
        self._extract_thread = None
        self.extract_button.configure(state="normal")
        if kind == "error":
            self.rpa_status.set("Extraction failed: %s" % payload)
            messagebox.showerror("Extract RPA", payload, parent=self)
            return
        self.rpa_status.set(
            "Extracted %d file(s), skipped %d, %.1f MB." % (
                payload["files"], payload["skipped"],
                payload["bytes"] / (1024 * 1024)))

    def _close(self):
        self._closed = True
        self.app._dev_dialog = None
        self.destroy()
