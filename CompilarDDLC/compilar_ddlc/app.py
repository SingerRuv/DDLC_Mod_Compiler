"""Interfaz gr?fica de Compilar DDLC."""
import queue
import sys
import threading
import time
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from .builder import compilar
from .config import APP, LOG_PATH, resource_path
from .errors import BuildCancelada
from .mods import detectar_mod
from .platforms import open_path


def _escribir_log(linea):
    marca = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8", newline="\n") as fh:
            fh.write("%s %s\n" % (marca, linea))
    except Exception:
        pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        try:
            if sys.platform == "win32":
                icono = resource_path("icono DDLC.ico")
                if icono.is_file():
                    self.iconbitmap(default=str(icono))
            else:
                icono = resource_path("icono.png")
                if icono.is_file():
                    self._icono = tk.PhotoImage(file=str(icono))
                    self.iconphoto(True, self._icono)
        except Exception:
            pass
        self.title(APP)
        self.geometry("900x680")
        self.minsize(760, 560)
        self.base = tk.StringVar()
        self.overlay = tk.StringVar()
        self.output = tk.StringVar()
        self.modo = tk.StringVar(value="Modo: sin detectar")
        self.docs = tk.BooleanVar(value=True)
        self.zip = tk.BooleanVar(value=False)
        self.open_game = tk.BooleanVar(value=False)
        self.estado = tk.StringVar(value="Listo")
        self.spinner_var = tk.StringVar(value="")
        self._spin_job = None
        self._spin_idx = 0
        self._queue = queue.Queue()
        self._cancel = threading.Event()
        self._worker = None
        self._build_ui()
        self.overlay.trace_add("write", lambda *_: self._actualizar_modo())
        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        self.after(100, self._pump)

    def _build_ui(self):
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="1. Base DDLC").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.base).grid(row=1, column=0, columnspan=3,
                                                     sticky="ew", pady=(2, 8))
        ttk.Button(frm, text="Elegir carpeta…", command=self._elegir_base).grid(
            row=1, column=3, padx=(8, 0))

        ttk.Label(frm, text="2. Mod (carpeta o ZIP)").grid(row=2, column=0,
                                                           sticky="w")
        self.modo_label = ttk.Label(frm, textvariable=self.modo, anchor="e")
        self.modo_label.grid(row=2, column=1, columnspan=3, sticky="e")
        ttk.Entry(frm, textvariable=self.overlay).grid(row=3, column=0,
                                                       columnspan=3, sticky="ew",
                                                       pady=(2, 8))
        overlay_btns = ttk.Frame(frm)
        overlay_btns.grid(row=3, column=3, padx=(8, 0))
        ttk.Button(overlay_btns, text="Carpeta…",
                   command=self._elegir_overlay_dir).pack(side="left")
        ttk.Button(overlay_btns, text="ZIP…",
                   command=self._elegir_overlay_zip).pack(side="left", padx=(4, 0))

        ttk.Label(frm, text="3. Carpeta de salida").grid(row=4, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.output).grid(row=5, column=0,
                                                      columnspan=3, sticky="ew",
                                                      pady=(2, 8))
        ttk.Button(frm, text="Elegir…", command=self._elegir_salida).grid(
            row=5, column=3, padx=(8, 0))

        checks = ttk.Frame(frm)
        checks.grid(row=6, column=0, columnspan=4, sticky="w", pady=(2, 8))
        ttk.Checkbutton(checks, text="Incluir créditos y README",
                        variable=self.docs).pack(side="left", padx=(0, 18))
        ttk.Checkbutton(checks, text="Crear ZIP", variable=self.zip).pack(
            side="left", padx=(0, 18))
        ttk.Checkbutton(checks, text="Abrir juego al finalizar",
                        variable=self.open_game).pack(side="left")

        bar = ttk.Frame(frm)
        bar.grid(row=7, column=0, columnspan=4, sticky="ew", pady=(4, 8))
        self.boton = ttk.Button(bar, text="Compilar", command=self._iniciar)
        self.boton.pack(side="left")
        ttk.Button(bar, text="Cancelar", command=self._cancelar).pack(
            side="left", padx=(8, 0))
        self.progress = ttk.Progressbar(bar, mode="determinate", maximum=100,
                                        value=0)
        self.progress.pack(side="left", fill="x", expand=True, padx=(12, 0))

        statusbar = ttk.Frame(frm)
        statusbar.grid(row=8, column=0, columnspan=4, sticky="ew", pady=(0, 6))
        self.spinner = ttk.Label(statusbar, textvariable=self.spinner_var,
                                 width=3, anchor="center")
        self.spinner.pack(side="left")
        ttk.Label(statusbar, textvariable=self.estado, anchor="w").pack(
            side="left", fill="x", expand=True, padx=(4, 0))

        self.log = ScrolledText(frm, height=18, wrap="word")
        self.log.grid(row=9, column=0, columnspan=4, sticky="nsew")
        frm.columnconfigure(0, weight=1)
        frm.columnconfigure(1, weight=1)
        frm.columnconfigure(2, weight=1)
        frm.rowconfigure(9, weight=1)

    def _elegir_base(self):
        p = filedialog.askdirectory(title="Carpeta base DDLC")
        if p:
            self.base.set(p)

    def _elegir_overlay_dir(self):
        p = filedialog.askdirectory(title="Carpeta del mod")
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
            self.modo.set("Modo: sin detectar")
            self.modo_label.configure(foreground="")
            return
        try:
            tipo, version = detectar_mod(p)
        except Exception as e:
            self.modo.set("Modo: no reconocido")
            self.modo_label.configure(foreground="#b00020")
            self._log("No reconozco el mod: %s" % e)
            return
        if tipo == "runtime":
            self.modo.set("Modo: Runtime Ren'Py %s" % version)
            self.modo_label.configure(foreground="#0b6b3a")
        elif tipo == "overlay":
            self.modo.set("Modo: Overlay DDLC")
            self.modo_label.configure(foreground="#0b6b3a")
        else:
            self.modo.set("Modo: proyecto fuente (no soportado)")
            self.modo_label.configure(foreground="#b00020")

    def _sugerir_salida(self, p):
        if not self.output.get() or self.output.get().endswith("(Compilado)"):
            path = Path(p)
            nombre = path.stem if path.is_file() else path.name
            self.output.set(str(path.parent / (nombre + " (Compilado)")))

    def _elegir_salida(self):
        p = filedialog.askdirectory(title="Carpeta de salida")
        if p:
            self.output.set(p)

    def _log(self, msg):
        self._queue.put(("log", msg))

    def _status(self, msg):
        self._queue.put(("estado", msg))

    def _progress(self, etiqueta, hecho, total):
        self._queue.put(("progress", (etiqueta, hecho, total)))

    def _pump(self):
        try:
            while True:
                tipo, msg = self._queue.get_nowait()
                if tipo == "log":
                    self.log.insert("end", msg + "\n")
                    self.log.see("end")
                    _escribir_log(msg)
                elif tipo == "estado":
                    self.estado.set(msg)
                elif tipo == "progress":
                    etiqueta, hecho, total = msg
                    pct = int(hecho * 100 / total) if total else 0
                    if etiqueta == "Copiando mod":
                        valor = int(pct * 0.8)
                    elif etiqueta == "Copiando assets":
                        valor = 80 + int(pct * 0.1)
                    elif etiqueta == "Copiando base":
                        valor = int(pct * 0.8)
                    elif etiqueta == "Copiando overlay":
                        valor = 80 + int(pct * 0.1)
                    elif etiqueta.startswith("Verificando"):
                        valor = 95
                    elif etiqueta.startswith("Creando ZIP"):
                        valor = 95 + int(pct * 0.05)
                    else:
                        valor = pct
                    self.progress.configure(value=max(0, min(100, valor)))
                    self.estado.set("%s… %d%%" % (etiqueta, pct))
                elif tipo == "done":
                    self._terminar(*msg)
        except queue.Empty:
            pass
        self.after(100, self._pump)

    def _iniciar(self):
        if self._worker and self._worker.is_alive():
            return
        base, overlay, output = self.base.get().strip(), self.overlay.get().strip(), self.output.get().strip()
        if not base or not overlay or not output:
            messagebox.showwarning(APP, "Completá base, mod y salida.")
            return
        try:
            tipo, version = detectar_mod(overlay)
        except Exception as e:
            messagebox.showwarning(APP, "No reconozco el mod:\n%s" % e)
            return
        if tipo == "fuente":
            messagebox.showwarning(
                APP, "Es un proyecto fuente de Ren'Py.\n\n"
                     "Este compilador no usa el SDK: armá primero una "
                     "distribución con el runtime incluido.")
            return
        self._log("Modo: %s%s" % (tipo, " Ren'Py " + version
                                  if tipo == "runtime" else ""))
        self._cancel.clear()
        self.boton.config(state="disabled")
        self.progress.configure(value=0)
        self.estado.set("Iniciando…")
        self.log.delete("1.0", "end")
        self._worker = threading.Thread(
            target=self._worker_run,
            args=(base, overlay, output, self.docs.get(), self.zip.get(),
                  self.open_game.get(), self._cancel),
            daemon=True)
        self._worker.start()
        self._spin_start()

    def _worker_run(self, base, overlay, output, docs, crear_zip, abrir, cancelar):
        try:
            carpeta, zpath = compilar(
                base, overlay, output, incluir_docs=docs, crear_zip=crear_zip,
                abrir_juego=abrir, log=self._log, status=self._status,
                progress=self._progress, cancelar=cancelar)
            self._queue.put(("done", (True, carpeta, zpath)))
        except BuildCancelada:
            self._queue.put(("done", (False, None, "Compilación cancelada.")))
        except Exception as e:
            self._log("ERROR: %s" % e)
            self._log(traceback.format_exc())
            self._queue.put(("done", (False, None, str(e))))

    def _terminar(self, ok, carpeta, zpath):
        self._spin_stop()
        self.boton.config(state="normal")
        if ok:
            self.progress.configure(value=100)
            self.estado.set("Listo")
            self._log("LISTO: %s" % carpeta)
            if zpath:
                self._log("ZIP: %s" % zpath)
            if messagebox.askyesno(APP, "Build terminado.\n¿Abrir la carpeta?"):
                try:
                    open_path(carpeta)
                except Exception:
                    pass
        else:
            self.progress.configure(value=0)
            self.estado.set("Cancelado" if zpath and "cancelada" in str(zpath).lower()
                            else "Error")
            self._log("ERROR: %s" % (zpath or "no se pudo compilar"))
            messagebox.showerror(APP, str(zpath or "No se pudo compilar."))

    def _cancelar(self):
        if self._worker and self._worker.is_alive():
            self._cancel.set()
            self.estado.set("Cancelando…")
            self._log("Cancelando…")

    def _spin_start(self):
        self._spin_idx = 0
        self._spin_tick()

    def _spin_tick(self):
        if not (self._worker and self._worker.is_alive()):
            self.spinner_var.set("")
            self._spin_job = None
            return
        frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
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

    def _cerrar(self):
        if self._worker and self._worker.is_alive():
            if not messagebox.askyesno(
                    APP, "Hay una compilación en curso.\n¿Cancelar y salir?"):
                return
            self._cancel.set()
            self.estado.set("Cancelando y cerrando…")
            self._log("Cancelando y cerrando…")
            self._cerrar_espera()
        else:
            self._spin_stop()
            self.destroy()

    def _cerrar_espera(self):
        if self._worker and self._worker.is_alive():
            self.after(200, self._cerrar_espera)
        else:
            self._spin_stop()
            self.destroy()


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
