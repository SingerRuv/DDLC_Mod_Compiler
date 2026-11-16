"""Compiler tab."""
import queue
import threading
import time
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from . import icons, theme
from .builder import compilar
from .config import (APP, LOG_PATH, MODS_ROOT, PHASE_COPY_ASSETS,
                     PHASE_COPY_BASE, PHASE_COPY_MOD, PHASE_COPY_OVERLAY,
                     PHASE_VERIFY, PHASE_ZIP, ensure_mods_root)
from .errors import BuildCancelada
from .mods import detectar_mod
from .platforms import open_path

LOG_QUEUE_LIMIT = 4096


def _escribir_logs(lineas):
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8", newline="\n") as fh:
            for linea in lineas:
                marca = time.strftime("%Y-%m-%d %H:%M:%S")
                fh.write("%s %s\n" % (marca, linea))
    except Exception:
        pass


class CompilerTab(ttk.Frame):
    def __init__(self, master, on_built=None, dark=False):
        super().__init__(master)
        self._on_built = on_built
        self.dark = dark
        self._icon_buttons = []
        self.base = tk.StringVar()
        self.overlay = tk.StringVar()
        self.output = tk.StringVar()
        self.modo = tk.StringVar(value="Mode: not detected")
        self.docs = tk.BooleanVar(value=True)
        self.zip = tk.BooleanVar(value=False)
        self.open_game = tk.BooleanVar(value=False)
        self.estado = tk.StringVar(value="Ready")
        self.spinner_var = tk.StringVar(value="")
        self._spin_job = None
        self._spin_idx = 0
        self._queue = queue.Queue(maxsize=LOG_QUEUE_LIMIT)
        self._cancel = threading.Event()
        self._worker = None
        self._mod_popup = None
        self._last_built = None
        self._build_ui()
        self.apply_theme(self.dark)
        self.overlay.trace_add("write", lambda *_: self._actualizar_modo())
        for variable in (self.base, self.overlay, self.output):
            variable.trace_add("write", lambda *_: self._clear_built())
        self.after(100, self._pump)

    def _clear_built(self):
        self._last_built = None

    def _button(self, parent, text, icon_name, command):
        button = ttk.Button(
            parent, text=text, image=icons.get_icon(icon_name, self.dark),
            compound="left", command=command)
        self._icon_buttons.append((button, icon_name))
        return button

    def _show_mod_menu(self):
        if self._mod_popup is not None:
            self._close_mod_menu()
            return
        p = theme.palette(self.dark)
        popup = tk.Toplevel(self)
        popup.overrideredirect(True)
        frame = tk.Frame(popup, bg=p["card"], bd=0,
                         highlightbackground=p["border"],
                         highlightthickness=1)
        frame.pack(fill="both", expand=True)
        for text, command in (("Folder...", self._elegir_overlay_dir),
                              ("ZIP...", self._elegir_overlay_zip)):
            row = tk.Label(frame, text=text, anchor="w", bg=p["card"],
                           fg=p["text"], font=("Segoe UI", 9),
                           padx=10, pady=5)
            row.pack(fill="x")
            row.bind("<Enter>",
                     lambda _e, widget=row: widget.configure(
                         bg=p["button_active"]))
            row.bind("<Leave>",
                     lambda _e, widget=row: widget.configure(bg=p["card"]))
            row.bind("<Button-1>",
                     lambda _e, action=command: self._choose_mod(action))
        popup.update_idletasks()
        width = self.mod_button.winfo_width()
        height = frame.winfo_reqheight()
        x = self.mod_button.winfo_rootx()
        y = self.mod_button.winfo_rooty() + self.mod_button.winfo_height()
        if x + width > popup.winfo_screenwidth():
            x = popup.winfo_screenwidth() - width
        if y + height > popup.winfo_screenheight():
            y = self.mod_button.winfo_rooty() - height
        popup.geometry("%dx%d+%d+%d" % (width, height, x, y))
        self._mod_popup = popup
        popup.bind("<Escape>", lambda _e: self._close_mod_menu())
        popup.bind("<FocusOut>", lambda _e: self._close_mod_menu())
        popup.focus_force()
        popup.lift()

    def _choose_mod(self, command):
        self._close_mod_menu()
        command()

    def _close_mod_menu(self):
        popup = self._mod_popup
        self._mod_popup = None
        if popup is not None:
            try:
                popup.destroy()
            except tk.TclError:
                pass

    def apply_theme(self, dark):
        self.dark = dark
        palette = theme.palette(dark)
        for button, icon_name in self._icon_buttons:
            button.configure(image=icons.get_icon(icon_name, dark))
        if hasattr(self, "log"):
            self.log.configure(
                bg=palette["entry"], fg=palette["text"],
                insertbackground=palette["text"])

    def _build_ui(self):
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(1, weight=1)

        controls = ttk.Frame(frm)
        controls.grid(row=0, column=0)
        controls.columnconfigure(0, weight=0)
        controls.columnconfigure(1, weight=0)
        controls.columnconfigure(2, weight=1)

        ttk.Label(controls, text="1. DDLC base").grid(
            row=0, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.base, width=64,
                  state="readonly").grid(
            row=1, column=0, sticky="w", pady=(2, 8))
        self._button(controls, "Choose folder...", "folder",
                     self._elegir_base).grid(
            row=1, column=1, padx=(8, 0), sticky="w")

        mod_header = ttk.Frame(controls)
        mod_header.grid(row=2, column=0, columnspan=3, sticky="w")
        ttk.Label(mod_header, text="2. Mod (folder or ZIP)").pack(
            side="left")
        ttk.Entry(controls, textvariable=self.overlay, width=64,
                  state="readonly").grid(
            row=3, column=0, sticky="w", pady=(2, 8))
        overlay_btns = ttk.Frame(controls)
        overlay_btns.grid(row=3, column=1, padx=(8, 0), sticky="w")
        self.mod_button = self._button(
            overlay_btns, "Choose...", "folder", self._show_mod_menu)
        self.mod_button.pack(side="left")

        ttk.Label(controls, text="3. Output folder").grid(
            row=4, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.output, state="readonly",
                  width=64).grid(row=5, column=0, sticky="w", pady=(2, 8))
        self._button(controls, "Open folder", "output-folder",
                     self._abrir_salida).grid(
            row=5, column=1, padx=(8, 0), sticky="w")

        checks = ttk.Frame(controls)
        checks.grid(row=6, column=0, columnspan=3, sticky="w",
                    pady=(14, 8))
        ttk.Checkbutton(checks, text="Include credits and README",
                        variable=self.docs).pack(side="left", padx=(0, 18))
        ttk.Checkbutton(checks, text="Create ZIP", variable=self.zip).pack(
            side="left", padx=(0, 18))
        ttk.Checkbutton(checks, text="Open game when finished",
                        variable=self.open_game).pack(side="left")
        self.modo_label = ttk.Label(checks, textvariable=self.modo,
                                    anchor="w")
        self.modo_label.pack(side="left", padx=(18, 0))

        bar = ttk.Frame(controls)
        bar.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(4, 8))
        self.boton = self._button(bar, "Build", "build", self._iniciar)
        self.boton.pack(side="left")
        self._button(bar, "Cancel", "cancel", self._cancelar).pack(
            side="left", padx=(8, 0))
        self.progress = ttk.Progressbar(bar, mode="determinate", maximum=100,
                                        value=0, length=220)
        self.progress.pack(side="left", padx=(12, 8))
        self.spinner = ttk.Label(bar, textvariable=self.spinner_var,
                                 width=3, anchor="center")
        self.spinner.pack(side="left")
        ttk.Label(bar, textvariable=self.estado, anchor="w").pack(
            side="left", padx=(4, 0))

        self.log = ScrolledText(frm, height=8, wrap="word", state="disabled")
        self.log.grid(row=1, column=0, sticky="nsew")

    def _elegir_base(self):
        p = filedialog.askdirectory(title="DDLC base folder")
        if p:
            self.base.set(p)

    def _elegir_overlay_dir(self):
        p = filedialog.askdirectory(title="Mod folder")
        if p:
            self.overlay.set(p)
            self._sugerir_salida(p)

    def _elegir_overlay_zip(self):
        p = filedialog.askopenfilename(title="Mod ZIP",
                                       filetypes=[("ZIP", "*.zip")])
        if p:
            self.overlay.set(p)
            self._sugerir_salida(p)

    def _actualizar_modo(self):
        p = self.overlay.get().strip()
        if not p:
            self.modo.set("Mode: not detected")
            self.modo_label.configure(foreground="")
            return
        try:
            tipo, version = detectar_mod(p)
        except Exception as e:
            self.modo.set("Mode: not recognized")
            self.modo_label.configure(foreground="#b00020")
            self._log("Unrecognized mod: %s" % e)
            return
        if tipo == "runtime":
            if version:
                self.modo.set("Mode: Runtime Ren'Py %s" % version)
            else:
                self.modo.set("Mode: Ren'Py runtime")
            self.modo_label.configure(foreground="#0b6b3a")
        elif tipo == "overlay":
            self.modo.set("Mode: DDLC overlay")
            self.modo_label.configure(foreground="#0b6b3a")
        else:
            self.modo.set("Mode: source project (unsupported)")
            self.modo_label.configure(foreground="#b00020")

    def _sugerir_salida(self, p):
        ensure_mods_root()
        path = Path(p)
        nombre = path.stem if path.is_file() else path.name
        self.output.set(str(MODS_ROOT / nombre))

    def _abrir_salida(self):
        ensure_mods_root()
        open_path(str(MODS_ROOT))

    def _resolver_salida(self, value):
        path = Path(value)
        if path.exists() and not path.is_dir():
            messagebox.showerror(APP, "Output exists and is not a folder.")
            return None, False
        zip_path = path.with_name(path.name + ".zip")
        zip_exists = bool(self.zip.get() and zip_path.exists())
        if (not path.exists() or not any(path.iterdir())) and not zip_exists:
            return path, False
        answer = messagebox.askyesnocancel(
            APP,
            "The output destination already exists:\n%s\n\n"
            "Yes: replace it\n"
            "No: create a numbered copy\n"
            "Cancel: stop" % path)
        if answer is None:
            return None, False
        if answer:
            return path, True
        base = path
        copy_number = 2
        while True:
            candidate = base.with_name("%s (%d)" % (base.name, copy_number))
            if not candidate.exists() and not (
                    self.zip.get() and
                    candidate.with_name(candidate.name + ".zip").exists()):
                return candidate, False
            copy_number += 1

    def _agregar_log(self, msg):
        self.log.configure(state="normal")
        try:
            self.log.insert("end", msg + "\n")
            self.log.see("end")
        finally:
            self.log.configure(state="disabled")

    def _log(self, msg):
        self._queue.put(("log", msg))

    def _status(self, msg):
        self._queue.put(("estado", msg))

    def _progress(self, etiqueta, hecho, total):
        self._queue.put(("progress", (etiqueta, hecho, total)))

    def _pump(self):
        lineas_log = []
        try:
            while True:
                tipo, msg = self._queue.get_nowait()
                if tipo == "log":
                    self._agregar_log(msg)
                    lineas_log.append(msg)
                elif tipo == "estado":
                    self.estado.set(msg)
                elif tipo == "progress":
                    etiqueta, hecho, total = msg
                    pct = int(hecho * 100 / total) if total else 0
                    if etiqueta == PHASE_COPY_MOD:
                        valor = int(pct * 0.8)
                    elif etiqueta == PHASE_COPY_ASSETS:
                        valor = 80 + int(pct * 0.1)
                    elif etiqueta == PHASE_COPY_BASE:
                        valor = int(pct * 0.8)
                    elif etiqueta == PHASE_COPY_OVERLAY:
                        valor = 80 + int(pct * 0.1)
                    elif etiqueta.startswith(PHASE_VERIFY):
                        valor = 95
                    elif etiqueta.startswith(PHASE_ZIP):
                        valor = 95 + int(pct * 0.05)
                    else:
                        valor = pct
                    self.progress.configure(value=max(0, min(100, valor)))
                    self.estado.set("%s... %d%%" % (etiqueta, pct))
                elif tipo == "done":
                    self._terminar(*msg)
        except queue.Empty:
            pass
        if lineas_log:
            _escribir_logs(lineas_log)
        self.after(100, self._pump)

    def _iniciar(self):
        if self._worker and self._worker.is_alive():
            return
        base, overlay, output = self.base.get().strip(), self.overlay.get().strip(), self.output.get().strip()
        if not base or not overlay or not output:
            messagebox.showwarning(APP, "Complete the base, mod, and output fields.")
            return
        try:
            tipo, version = detectar_mod(overlay)
        except Exception as e:
            messagebox.showwarning(APP, "Unrecognized mod:\n%s" % e)
            return
        if tipo == "fuente":
            messagebox.showwarning(
                APP, "This is a Ren'Py source project.\n\n"
                     "This compiler does not use the SDK: first create a "
                     "distribution with the included runtime.")
            return
        output_path, overwrite = self._resolver_salida(output)
        if output_path is None:
            return
        output = str(output_path)
        if output != self.output.get():
            self.output.set(output)
        suffix = ""
        if tipo == "runtime":
            suffix = (" Ren'Py " + version) if version else " Ren'Py runtime"
        self._log("Mode: %s%s" % (tipo, suffix))
        self._cancel.clear()
        self._last_built = None
        self.boton.config(state="disabled")
        self.progress.configure(value=0)
        self.estado.set("Starting...")
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self._worker = threading.Thread(
            target=self._worker_run,
            args=(base, overlay, output, self.docs.get(), self.zip.get(),
                  self.open_game.get(), overwrite, self._cancel),
            daemon=True)
        self._worker.start()
        self._spin_start()

    def _worker_run(self, base, overlay, output, docs, crear_zip, abrir,
                    overwrite, cancelar):
        try:
            carpeta, zpath = compilar(
                base, overlay, output, incluir_docs=docs, crear_zip=crear_zip,
                abrir_juego=abrir, log=self._log, status=self._status,
                progress=self._progress, cancelar=cancelar,
                overwrite=overwrite)
            self._queue.put(("done", (True, carpeta, zpath)))
        except BuildCancelada:
            self._queue.put(("done", (False, None, "Build cancelled.")))
        except Exception as e:
            self._log("ERROR: %s" % e)
            self._log(traceback.format_exc())
            self._queue.put(("done", (False, None, str(e))))

    def _terminar(self, ok, carpeta, zpath):
        self._spin_stop()
        self.boton.config(state="normal")
        if ok:
            self.progress.configure(value=100)
            self.estado.set("Ready")
            self._last_built = carpeta
            self._log("DONE: %s" % carpeta)
            if zpath:
                self._log("ZIP: %s" % zpath)
            if self._on_built:
                try:
                    self._on_built(carpeta)
                except Exception:
                    pass
            if messagebox.askyesno(APP, "Build complete.\nOpen the output folder?"):
                try:
                    open_path(carpeta)
                except Exception:
                    pass
        else:
            self.progress.configure(value=0)
            self.estado.set("Cancelled" if zpath and "cancelled" in str(zpath).lower()
                            else "Error")
            self._log("ERROR: %s" % (zpath or "could not build"))
            messagebox.showerror(APP, str(zpath or "Could not build."))

    def _cancelar(self):
        if self._worker and self._worker.is_alive():
            self._cancel.set()
            self.estado.set("Cancelling...")
            self._log("Cancelling...")

    def _spin_start(self):
        self._spin_idx = 0
        self._spin_tick()

    def _spin_tick(self):
        if not (self._worker and self._worker.is_alive()):
            self.spinner_var.set("")
            self._spin_job = None
            return
        frames = "|/-"
        self.spinner_var.set(frames[self._spin_idx % len(frames)])
        self._spin_idx += 1
        self._spin_job = self.after(100, self._spin_tick)

    def _spin_stop(self):
        if self._spin_job:
            try:
                self.after_cancel(self._spin_job)
            except Exception:
                pass
            self._spin_job = None
        self.spinner_var.set("")

    def is_building(self):
        return bool(self._worker and self._worker.is_alive())

    def guide_state(self):
        return {
            "base": self.base.get().strip(),
            "mod": self.overlay.get().strip(),
            "mode": self.modo.get(),
            "output": self.output.get().strip(),
            "built": bool(self._last_built),
            "building": self.is_building(),
        }

    def cancel_for_close(self):
        if self.is_building():
            self._cancel.set()
            self.estado.set("Cancelling and closing...")
            message = "Cancelling and closing..."
            self._agregar_log(message)
            _escribir_logs([message])
